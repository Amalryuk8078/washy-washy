"""Payment/refund business logic: initiating and charging a payment
against an invoice, processing gateway webhooks idempotently, and
issuing refunds that can never exceed what was actually captured.

Depends only on ``PaymentGateway`` (see ``payment_gateway.py``), never
a concrete provider — the domain logic here would be identical whether
``ManualPaymentGateway`` or a real Stripe/Razorpay adapter is injected.

**Webhooks are authoritative for final status** (the spec's own
words): ``handle_webhook`` can move a payment to ``CAPTURED``/``FAILED``
independent of whatever ``charge_payment``'s own synchronous gateway
response already set, modeling the real-world case where a gateway's
webhook confirms (or corrects) a payment's outcome after the initial
API call returns. A client-side "it succeeded" is never trusted as the
source of truth on its own.
"""

import uuid
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import BusinessRuleException, NotFoundException
from core.models.invoice import InvoiceStatus
from core.models.payment import Payment, PaymentStatus
from core.models.payment_attempt import PaymentAttempt
from core.models.payment_event import PaymentEvent
from core.models.refund import Refund, RefundStatus
from washy_washy.constants import error_codes, error_messages
from washy_washy.repositories.invoice_repo import InvoiceRepository
from washy_washy.repositories.payment_attempt_repo import PaymentAttemptRepository
from washy_washy.repositories.payment_event_repo import PaymentEventRepository
from washy_washy.repositories.payment_repo import PaymentRepository
from washy_washy.repositories.refund_repo import RefundRepository
from washy_washy.services.payment_gateway import ManualPaymentGateway, PaymentGateway

ZERO = Decimal("0")


class PaymentService:
    def __init__(self, session: AsyncSession, gateway: PaymentGateway | None = None) -> None:
        self._session = session
        self._invoices = InvoiceRepository(session)
        self._payments = PaymentRepository(session)
        self._attempts = PaymentAttemptRepository(session)
        self._events = PaymentEventRepository(session)
        self._refunds = RefundRepository(session)
        self._gateway = gateway or ManualPaymentGateway()

    # -- Initiating & charging ----------------------------------------------

    async def get_payment(self, payment_id: uuid.UUID) -> Payment:
        return await self._get_payment(payment_id)

    async def initiate_payment(
        self, invoice_id: uuid.UUID, amount: Decimal, *, currency: str = "INR"
    ) -> Payment:
        invoice = await self._invoices.get_by_id(invoice_id)
        if invoice is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        if invoice.status not in (
            InvoiceStatus.FINALIZED.value,
            InvoiceStatus.PARTIALLY_PAID.value,
        ):
            raise BusinessRuleException(
                error_messages.INVOICE_NOT_PAYABLE, error_codes.INVOICE_NOT_PAYABLE
            )
        remaining = invoice.total - invoice.amount_paid
        if amount <= ZERO or amount > remaining:
            raise BusinessRuleException(
                error_messages.PAYMENT_AMOUNT_EXCEEDS_BALANCE,
                error_codes.PAYMENT_AMOUNT_EXCEEDS_BALANCE,
            )
        return await self._payments.create(
            Payment(invoice_id=invoice_id, amount=amount, currency=currency)
        )

    async def charge_payment(self, payment_id: uuid.UUID) -> Payment:
        payment = await self._get_payment(payment_id)
        if payment.status != PaymentStatus.PENDING.value:
            raise BusinessRuleException(
                error_messages.PAYMENT_NOT_CHARGEABLE, error_codes.PAYMENT_NOT_CHARGEABLE
            )

        attempt = await self._attempts.create(
            PaymentAttempt(payment_id=payment_id, status=PaymentStatus.PENDING.value)
        )
        result = await self._gateway.charge(payment.amount, payment.currency)

        if result.success:
            attempt.status = PaymentStatus.CAPTURED.value
            attempt.provider_reference = result.provider_reference
            await self._attempts.update(attempt)

            payment.provider_reference = result.provider_reference
            await self._payments.update(payment)
            await self._payments.try_capture(payment_id, payment.amount)
            payment.status = PaymentStatus.CAPTURED.value
            payment.captured_amount = payment.amount
            await self._payments.update(payment)

            await self._invoices.try_apply_payment(payment.invoice_id, payment.amount)
            await self._recompute_invoice_status(payment.invoice_id)
        else:
            attempt.status = PaymentStatus.FAILED.value
            attempt.failure_reason = str(result.raw.get("error", "Charge failed"))
            await self._attempts.update(attempt)
            payment.status = PaymentStatus.FAILED.value
            await self._payments.update(payment)

        return payment

    # -- Webhooks -------------------------------------------------------

    async def handle_webhook(self, payload: dict) -> None:
        """Idempotent: a duplicate ``event_id`` (the same webhook
        delivered twice, which every real gateway does) is a silent
        no-op, checked both up front and against the database's own
        unique constraint in case two deliveries race each other.
        """
        event_id = payload["event_id"]
        event_type = payload["event_type"]
        provider_reference = payload["provider_reference"]

        if await self._events.get_by_provider_event_id(event_id) is not None:
            return

        payment = await self._payments.get_by_provider_reference(provider_reference)
        if payment is None:
            raise NotFoundException(
                error_messages.UNKNOWN_PAYMENT_REFERENCE, error_codes.UNKNOWN_PAYMENT_REFERENCE
            )

        try:
            await self._events.create(
                PaymentEvent(
                    payment_id=payment.id,
                    event_type=event_type,
                    provider_event_id=event_id,
                    raw_payload=payload,
                )
            )
        except IntegrityError:
            await self._session.rollback()
            return

        if event_type == "payment.captured":
            if payment.status != PaymentStatus.CAPTURED.value:
                newly_captured = payment.amount - payment.captured_amount
                await self._payments.try_capture(payment.id, newly_captured)
                payment.status = PaymentStatus.CAPTURED.value
                payment.captured_amount = payment.amount
                await self._payments.update(payment)
                await self._invoices.try_apply_payment(payment.invoice_id, newly_captured)
                await self._recompute_invoice_status(payment.invoice_id)
        elif event_type == "payment.failed":
            payment.status = PaymentStatus.FAILED.value
            await self._payments.update(payment)

    # -- Refunds ----------------------------------------------------------

    async def refund_payment(
        self, payment_id: uuid.UUID, amount: Decimal, *, reason: str | None = None
    ) -> Refund:
        payment = await self._get_payment(payment_id)
        if payment.captured_amount <= ZERO:
            raise BusinessRuleException(
                error_messages.PAYMENT_NOT_REFUNDABLE, error_codes.PAYMENT_NOT_REFUNDABLE
            )

        reserved = await self._payments.try_refund(payment_id, amount)
        if not reserved:
            raise BusinessRuleException(
                error_messages.REFUND_EXCEEDS_CAPTURED_AMOUNT,
                error_codes.REFUND_EXCEEDS_CAPTURED_AMOUNT,
            )

        result = await self._gateway.refund(payment.provider_reference or "", amount)
        if result.success:
            refund = await self._refunds.create(
                Refund(
                    payment_id=payment_id,
                    amount=amount,
                    status=RefundStatus.PROCESSED.value,
                    provider_reference=result.provider_reference,
                    reason=reason,
                )
            )
            await self._invoices.release_payment(payment.invoice_id, amount)
            await self._recompute_invoice_status(payment.invoice_id)
            return refund

        # Gateway declined -- release the reservation we took before
        # calling it, so a failed refund never permanently locks up
        # capacity to refund.
        await self._payments.release_refund(payment_id, amount)
        return await self._refunds.create(
            Refund(
                payment_id=payment_id,
                amount=amount,
                status=RefundStatus.FAILED.value,
                reason=reason,
            )
        )

    async def list_refunds(self, payment_id: uuid.UUID) -> list[Refund]:
        return await self._refunds.list_for_payment(payment_id)

    # -- Helpers ------------------------------------------------------------

    async def _get_payment(self, payment_id: uuid.UUID) -> Payment:
        payment = await self._payments.get_by_id(payment_id)
        if payment is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        return payment

    async def _recompute_invoice_status(self, invoice_id: uuid.UUID) -> None:
        invoice = await self._invoices.get_by_id(invoice_id)
        if invoice is None or invoice.status == InvoiceStatus.VOID.value:
            return
        if invoice.amount_paid >= invoice.total and invoice.total > ZERO:
            invoice.status = InvoiceStatus.PAID.value
        elif invoice.amount_paid > ZERO:
            invoice.status = InvoiceStatus.PARTIALLY_PAID.value
        else:
            invoice.status = InvoiceStatus.FINALIZED.value
        await self._invoices.update(invoice)
