"""Integration tests for PaymentService — charging, webhook handling,
and refunds — against a real PostgreSQL database.

Uses a small ``FakePaymentGateway`` (implementing the same
``PaymentGateway`` interface ``ManualPaymentGateway`` does) wherever a
test needs to force a *failed* charge/refund — proving
``PaymentService`` only ever depends on the abstraction, never a
concrete provider's behavior.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

import pytest

from core.exceptions import BusinessRuleException
from core.models.invoice import InvoiceStatus
from core.models.order import OrderStatus
from core.models.payment import PaymentStatus
from core.models.pricing_rule import PricingModel
from core.models.refund import RefundStatus
from washy_washy.repositories.payment_attempt_repo import PaymentAttemptRepository
from washy_washy.repositories.payment_repo import PaymentRepository
from washy_washy.services.address_service import AddressService
from washy_washy.services.auth_service import AuthService
from washy_washy.services.catalog_service import CatalogService
from washy_washy.services.invoice_service import InvoiceService
from washy_washy.services.order_service import OrderItemInput, OrderService
from washy_washy.services.order_state_service import OrderStateService
from washy_washy.services.payment_gateway import GatewayResult, PaymentGateway
from washy_washy.services.payment_service import PaymentService
from washy_washy.services.pricing_service import PricingService
from washy_washy.services.service_area_service import ServiceAreaService


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


def _unique_postal_code() -> str:
    return str(uuid.uuid4().int)[:10]


@dataclass
class FakePaymentGateway(PaymentGateway):
    """Deterministic, test-controlled gateway -- succeeds or fails on
    command, exactly the kind of substitutable implementation the
    ``PaymentGateway`` abstraction exists for.
    """

    charge_succeeds: bool = True
    refund_succeeds: bool = True

    async def charge(self, amount: Decimal, currency: str) -> GatewayResult:
        if self.charge_succeeds:
            return GatewayResult(
                success=True, provider_reference=f"fake_ch_{uuid.uuid4().hex}", raw={}
            )
        return GatewayResult(success=False, provider_reference="", raw={"error": "card_declined"})

    async def refund(self, provider_reference: str, amount: Decimal) -> GatewayResult:
        if self.refund_succeeds:
            return GatewayResult(
                success=True, provider_reference=f"fake_re_{uuid.uuid4().hex}", raw={}
            )
        return GatewayResult(success=False, provider_reference="", raw={"error": "refund_declined"})


async def _make_finalized_invoice(db_session, *, quantity: int = 2, finalize: bool = True):
    customer = await AuthService(db_session).register(
        email=f"{_unique('customer')}@example.com", password="longenough1", first_name="Cust"
    )
    catalog = CatalogService(db_session)
    service = await catalog.create_service(_unique("Wash"))
    material = await catalog.create_material(_unique("Cotton"))
    await PricingService(db_session).set_service_pricing(
        service.id, PricingModel.PER_ITEM.value, Decimal("5.00"), Decimal("2.00")
    )
    postal_code = _unique_postal_code()
    await ServiceAreaService(db_session).create_service_area(_unique("Area"), [postal_code])
    address = await AddressService(db_session).create_address(
        customer.id,
        address_line_1="1 Main St",
        city="Metropolis",
        state="State",
        postal_code=postal_code,
        country="Country",
        label="HOME",
    )
    order_service = OrderService(db_session)
    order = await order_service.create_order(
        customer.id,
        pickup_address_id=address.id,
        delivery_address_id=address.id,
        items=[
            OrderItemInput(
                service_id=service.id, declared_material_id=material.id, declared_quantity=quantity
            )
        ],
    )
    state_service = OrderStateService(db_session)
    for status in (
        OrderStatus.PENDING_PAYMENT,
        OrderStatus.CONFIRMED,
        OrderStatus.PICKUP_SCHEDULED,
        OrderStatus.PICKUP_ASSIGNED,
        OrderStatus.PICKUP_IN_PROGRESS,
        OrderStatus.PICKED_UP,
        OrderStatus.RECEIVED_AT_FACILITY,
        OrderStatus.INSPECTION,
        OrderStatus.ITEMIZED,
    ):
        await state_service.transition(
            order.id, status, requester_user_id=customer.id, requester_is_staff=True
        )
    order = await order_service.finalize_pricing(order.id, customer.id, requester_is_staff=True)

    invoice_service = InvoiceService(db_session)
    invoice = await invoice_service.create_invoice_from_order(order.id)
    if finalize:
        invoice = await invoice_service.finalize_invoice(invoice.id)
    return invoice, customer


@pytest.mark.asyncio
async def test_payment_success_marks_invoice_paid(db_session) -> None:
    invoice, _customer = await _make_finalized_invoice(db_session)
    service = PaymentService(db_session, gateway=FakePaymentGateway())
    payment = await service.initiate_payment(invoice.id, invoice.total)

    charged = await service.charge_payment(payment.id)

    assert charged.status == PaymentStatus.CAPTURED.value
    assert charged.captured_amount == invoice.total
    assert charged.provider_reference is not None
    updated_invoice = await InvoiceService(db_session).get_invoice(invoice.id)
    assert updated_invoice.status == InvoiceStatus.PAID.value
    assert updated_invoice.amount_paid == invoice.total


@pytest.mark.asyncio
async def test_payment_failure_does_not_touch_invoice(db_session) -> None:
    invoice, _customer = await _make_finalized_invoice(db_session)
    service = PaymentService(db_session, gateway=FakePaymentGateway(charge_succeeds=False))
    payment = await service.initiate_payment(invoice.id, invoice.total)

    failed = await service.charge_payment(payment.id)

    assert failed.status == PaymentStatus.FAILED.value
    assert failed.captured_amount == Decimal("0")
    updated_invoice = await InvoiceService(db_session).get_invoice(invoice.id)
    assert updated_invoice.status == InvoiceStatus.FINALIZED.value
    assert updated_invoice.amount_paid == Decimal("0")


@pytest.mark.asyncio
async def test_partial_payment_marks_invoice_partially_paid(db_session) -> None:
    invoice, _customer = await _make_finalized_invoice(db_session, quantity=4)
    # subtotal = 5.00 + 2.00*4 = 13.00
    service = PaymentService(db_session, gateway=FakePaymentGateway())
    payment = await service.initiate_payment(invoice.id, Decimal("5.00"))

    await service.charge_payment(payment.id)

    updated_invoice = await InvoiceService(db_session).get_invoice(invoice.id)
    assert updated_invoice.status == InvoiceStatus.PARTIALLY_PAID.value
    assert updated_invoice.amount_paid == Decimal("5.00")

    # A second payment for the remainder completes it.
    remaining = updated_invoice.total - updated_invoice.amount_paid
    payment_two = await service.initiate_payment(invoice.id, remaining)
    await service.charge_payment(payment_two.id)

    final_invoice = await InvoiceService(db_session).get_invoice(invoice.id)
    assert final_invoice.status == InvoiceStatus.PAID.value
    assert final_invoice.amount_paid == final_invoice.total


@pytest.mark.asyncio
async def test_initiate_payment_rejects_amount_exceeding_balance(db_session) -> None:
    invoice, _customer = await _make_finalized_invoice(db_session)
    service = PaymentService(db_session, gateway=FakePaymentGateway())

    with pytest.raises(BusinessRuleException):
        await service.initiate_payment(invoice.id, invoice.total + Decimal("100.00"))


@pytest.mark.asyncio
async def test_invoice_totals_are_immutable_after_payment(db_session) -> None:
    invoice, _customer = await _make_finalized_invoice(db_session)
    original_subtotal, original_total = invoice.subtotal, invoice.total
    service = PaymentService(db_session, gateway=FakePaymentGateway())
    payment = await service.initiate_payment(invoice.id, invoice.total)
    await service.charge_payment(payment.id)

    updated_invoice = await InvoiceService(db_session).get_invoice(invoice.id)
    # amount_paid changed; the billed amounts never did.
    assert updated_invoice.subtotal == original_subtotal
    assert updated_invoice.total == original_total


@pytest.mark.asyncio
async def test_webhook_confirms_capture(db_session) -> None:
    invoice, _customer = await _make_finalized_invoice(db_session)
    gateway = FakePaymentGateway()
    service = PaymentService(db_session, gateway=gateway)
    payment = await service.initiate_payment(invoice.id, invoice.total)
    # Simulate the payment having a provider reference already (e.g. an
    # authorize-only flow) without the synchronous charge path having
    # captured it yet.
    payment.provider_reference = "webhook_ref_1"
    await PaymentRepository(db_session).update(payment)

    await service.handle_webhook(
        {
            "event_id": str(uuid.uuid4()),
            "event_type": "payment.captured",
            "provider_reference": "webhook_ref_1",
        }
    )

    refreshed = await PaymentRepository(db_session).get_by_id(payment.id)
    assert refreshed.status == PaymentStatus.CAPTURED.value
    assert refreshed.captured_amount == payment.amount
    updated_invoice = await InvoiceService(db_session).get_invoice(invoice.id)
    assert updated_invoice.status == InvoiceStatus.PAID.value


@pytest.mark.asyncio
async def test_duplicate_webhook_is_idempotent(db_session) -> None:
    invoice, _customer = await _make_finalized_invoice(db_session)
    service = PaymentService(db_session, gateway=FakePaymentGateway())
    payment = await service.initiate_payment(invoice.id, invoice.total)
    payment.provider_reference = "webhook_ref_dup"
    await PaymentRepository(db_session).update(payment)

    event = {
        "event_id": "evt_same_id",
        "event_type": "payment.captured",
        "provider_reference": "webhook_ref_dup",
    }
    await service.handle_webhook(event)
    # Replaying the exact same event a second (and third) time must not
    # double-apply the capture.
    await service.handle_webhook(event)
    await service.handle_webhook(event)

    refreshed = await PaymentRepository(db_session).get_by_id(payment.id)
    assert refreshed.captured_amount == payment.amount
    updated_invoice = await InvoiceService(db_session).get_invoice(invoice.id)
    assert updated_invoice.amount_paid == invoice.total


@pytest.mark.asyncio
async def test_refund_success_releases_invoice_amount_paid(db_session) -> None:
    invoice, _customer = await _make_finalized_invoice(db_session)
    service = PaymentService(db_session, gateway=FakePaymentGateway())
    payment = await service.initiate_payment(invoice.id, invoice.total)
    await service.charge_payment(payment.id)

    refund = await service.refund_payment(payment.id, invoice.total, reason="Customer request")

    assert refund.status == RefundStatus.PROCESSED.value
    updated_invoice = await InvoiceService(db_session).get_invoice(invoice.id)
    assert updated_invoice.amount_paid == Decimal("0")
    assert updated_invoice.status == InvoiceStatus.FINALIZED.value


@pytest.mark.asyncio
async def test_partial_refund(db_session) -> None:
    invoice, _customer = await _make_finalized_invoice(db_session, quantity=4)
    service = PaymentService(db_session, gateway=FakePaymentGateway())
    payment = await service.initiate_payment(invoice.id, invoice.total)
    await service.charge_payment(payment.id)

    refund = await service.refund_payment(payment.id, Decimal("3.00"))

    assert refund.amount == Decimal("3.00")
    updated_invoice = await InvoiceService(db_session).get_invoice(invoice.id)
    assert updated_invoice.amount_paid == invoice.total - Decimal("3.00")
    assert updated_invoice.status == InvoiceStatus.PARTIALLY_PAID.value


@pytest.mark.asyncio
async def test_over_refund_prevented(db_session) -> None:
    invoice, _customer = await _make_finalized_invoice(db_session)
    service = PaymentService(db_session, gateway=FakePaymentGateway())
    payment = await service.initiate_payment(invoice.id, invoice.total)
    await service.charge_payment(payment.id)

    await service.refund_payment(payment.id, invoice.total)

    with pytest.raises(BusinessRuleException):
        await service.refund_payment(payment.id, Decimal("0.01"))


@pytest.mark.asyncio
async def test_refund_without_capture_rejected(db_session) -> None:
    invoice, _customer = await _make_finalized_invoice(db_session)
    service = PaymentService(db_session, gateway=FakePaymentGateway())
    payment = await service.initiate_payment(invoice.id, invoice.total)

    with pytest.raises(BusinessRuleException):
        await service.refund_payment(payment.id, Decimal("1.00"))


@pytest.mark.asyncio
async def test_reconciliation_records_are_complete(db_session) -> None:
    """Every financial fact -- the attempt, the event, and the refund --
    is independently queryable with its own provider reference and
    amount, per the spec's "make financial records auditable."
    """
    invoice, _customer = await _make_finalized_invoice(db_session)
    service = PaymentService(db_session, gateway=FakePaymentGateway())
    payment = await service.initiate_payment(invoice.id, invoice.total)
    await service.charge_payment(payment.id)
    await service.refund_payment(payment.id, invoice.total, reason="Full refund")

    attempts = await PaymentAttemptRepository(db_session).list_for_payment(payment.id)
    assert len(attempts) == 1
    assert attempts[0].status == PaymentStatus.CAPTURED.value
    assert attempts[0].provider_reference is not None

    refunds = await service.list_refunds(payment.id)
    assert len(refunds) == 1
    assert refunds[0].provider_reference is not None
    assert refunds[0].amount == invoice.total
