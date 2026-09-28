"""Request-level orchestration for invoice/payment/refund endpoints.

Ownership for an invoice/payment is always resolved through the order
behind it (``Invoice.order_id`` / ``Payment.invoice_id.invoice.order_id``)
— there's no separate ownership concept on invoices/payments
themselves, since they belong to whoever the order belongs to.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.models.invoice import Invoice
from core.models.payment import Payment
from core.models.role import RoleName
from core.models.user import User
from washy_washy.schemas.payments import (
    CreateInvoiceRequest,
    InitiatePaymentRequest,
    InvoiceResponse,
    InvoiceWithItemsResponse,
    PaymentResponse,
    PaymentWebhookPayload,
    RefundRequest,
    RefundResponse,
)
from washy_washy.services.invoice_service import InvoiceService
from washy_washy.services.order_service import OrderService
from washy_washy.services.payment_service import PaymentService
from washy_washy.services.rbac_service import RBACService

_STAFF_ROLES = [RoleName.ADMIN.value, RoleName.SUPERVISOR.value, RoleName.LAUNDRY_PARTNER.value]


async def _is_staff(db_session: AsyncSession, user_id: uuid.UUID) -> bool:
    return await RBACService(db_session).has_any_role(user_id, _STAFF_ROLES)


async def _invoice_for_viewer(
    db_session: AsyncSession, invoice_id: uuid.UUID, current_user: User
) -> Invoice:
    invoice = await InvoiceService(db_session).get_invoice(invoice_id)
    is_staff = await _is_staff(db_session, current_user.id)
    await OrderService(db_session).get_order_for_viewer(
        invoice.order_id, current_user.id, is_staff=is_staff
    )
    return invoice


async def _payment_for_viewer(
    db_session: AsyncSession, payment_id: uuid.UUID, current_user: User
) -> Payment:
    payment = await PaymentService(db_session).get_payment(payment_id)
    await _invoice_for_viewer(db_session, payment.invoice_id, current_user)
    return payment


async def create_invoice(
    order_id: uuid.UUID, request: CreateInvoiceRequest, db_session: AsyncSession
) -> InvoiceWithItemsResponse:
    service = InvoiceService(db_session)
    invoice = await service.create_invoice_from_order(
        order_id, tax=request.tax, discount=request.discount
    )
    items = await service.list_items(invoice.id)
    await db_session.commit()
    return InvoiceWithItemsResponse.model_validate(
        {**InvoiceResponse.model_validate(invoice).model_dump(), "items": items}
    )


async def get_invoice_for_order(
    order_id: uuid.UUID, current_user: User, db_session: AsyncSession
) -> InvoiceWithItemsResponse:
    service = InvoiceService(db_session)
    is_staff = await _is_staff(db_session, current_user.id)
    await OrderService(db_session).get_order_for_viewer(
        order_id, current_user.id, is_staff=is_staff
    )
    invoice = await service.get_invoice_for_order(order_id)
    items = await service.list_items(invoice.id)
    return InvoiceWithItemsResponse.model_validate(
        {**InvoiceResponse.model_validate(invoice).model_dump(), "items": items}
    )


async def get_invoice(
    invoice_id: uuid.UUID, current_user: User, db_session: AsyncSession
) -> InvoiceWithItemsResponse:
    invoice = await _invoice_for_viewer(db_session, invoice_id, current_user)
    items = await InvoiceService(db_session).list_items(invoice.id)
    return InvoiceWithItemsResponse.model_validate(
        {**InvoiceResponse.model_validate(invoice).model_dump(), "items": items}
    )


async def finalize_invoice(invoice_id: uuid.UUID, db_session: AsyncSession) -> InvoiceResponse:
    invoice = await InvoiceService(db_session).finalize_invoice(invoice_id)
    await db_session.commit()
    return InvoiceResponse.model_validate(invoice)


async def void_invoice(invoice_id: uuid.UUID, db_session: AsyncSession) -> InvoiceResponse:
    invoice = await InvoiceService(db_session).void_invoice(invoice_id)
    await db_session.commit()
    return InvoiceResponse.model_validate(invoice)


async def initiate_payment(
    invoice_id: uuid.UUID,
    current_user: User,
    request: InitiatePaymentRequest,
    db_session: AsyncSession,
) -> PaymentResponse:
    await _invoice_for_viewer(db_session, invoice_id, current_user)
    payment = await PaymentService(db_session).initiate_payment(
        invoice_id, request.amount, currency=request.currency
    )
    await db_session.commit()
    return PaymentResponse.model_validate(payment)


async def charge_payment(
    payment_id: uuid.UUID, current_user: User, db_session: AsyncSession
) -> PaymentResponse:
    await _payment_for_viewer(db_session, payment_id, current_user)
    payment = await PaymentService(db_session).charge_payment(payment_id)
    await db_session.commit()
    return PaymentResponse.model_validate(payment)


async def get_payment(
    payment_id: uuid.UUID, current_user: User, db_session: AsyncSession
) -> PaymentResponse:
    payment = await _payment_for_viewer(db_session, payment_id, current_user)
    return PaymentResponse.model_validate(payment)


async def refund_payment(
    payment_id: uuid.UUID, request: RefundRequest, db_session: AsyncSession
) -> RefundResponse:
    refund = await PaymentService(db_session).refund_payment(
        payment_id, request.amount, reason=request.reason
    )
    await db_session.commit()
    return RefundResponse.model_validate(refund)


async def list_refunds(
    payment_id: uuid.UUID, current_user: User, db_session: AsyncSession
) -> list[RefundResponse]:
    await _payment_for_viewer(db_session, payment_id, current_user)
    refunds = await PaymentService(db_session).list_refunds(payment_id)
    return [RefundResponse.model_validate(r) for r in refunds]


async def handle_webhook(payload: PaymentWebhookPayload, db_session: AsyncSession) -> None:
    await PaymentService(db_session).handle_webhook(payload.model_dump())
    await db_session.commit()
