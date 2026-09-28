"""Invoice/payment/refund endpoints.

Creating/finalizing/voiding an invoice and issuing a refund are
staff-only (``ADMIN``/``SUPERVISOR``/``LAUNDRY_PARTNER``) — a customer
never generates their own bill or refunds themselves. Viewing an
invoice/payment and initiating/charging a payment only require
ownership of the underlying order (or staff), enforced in the
controller layer via ``OrderService.get_order_for_viewer`` — the same
posture as every other order-adjacent resource in this project.

The webhook endpoint is deliberately **not** behind the normal
``Authorization: Bearer`` flow — a payment gateway has no user account
here. It's authenticated instead by a shared secret header
(``X-Webhook-Secret``, checked against ``settings.payment_webhook_secret``),
a deliberately simple stand-in for whatever a real provider's
signature-verification scheme would be (e.g. Stripe's
``Stripe-Signature`` HMAC) — this project integrates no real gateway,
so a shared secret is the simplest mechanism that still satisfies the
spec's "webhook processing must be ... authenticated."
"""

import uuid

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.exceptions import UnauthorizedException
from core.models.role import RoleName
from core.models.user import User
from washy_washy.api.v1.controllers import payments as payments_controller
from washy_washy.config import get_settings
from washy_washy.constants import error_codes, error_messages
from washy_washy.dependencies.auth import get_current_user
from washy_washy.dependencies.rbac import require_any_role
from washy_washy.schemas.common import SuccessResponse
from washy_washy.schemas.payments import (
    CreateInvoiceRequest,
    InitiatePaymentRequest,
    PaymentWebhookPayload,
    RefundRequest,
)

router = APIRouter(tags=["payments"])
_staff_only = Depends(
    require_any_role(
        RoleName.ADMIN.value, RoleName.SUPERVISOR.value, RoleName.LAUNDRY_PARTNER.value
    )
)


async def _verify_webhook_secret(x_webhook_secret: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if x_webhook_secret != settings.payment_webhook_secret:
        raise UnauthorizedException(
            error_messages.WEBHOOK_UNAUTHORIZED, error_codes.WEBHOOK_UNAUTHORIZED
        )


@router.post(
    "/orders/{order_id}/invoice",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_user), _staff_only],
)
async def create_invoice(
    order_id: uuid.UUID,
    request: CreateInvoiceRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    invoice = await payments_controller.create_invoice(order_id, request, db_session)
    return SuccessResponse(message="Invoice created", data=invoice)


@router.get(
    "/orders/{order_id}/invoice",
    response_model=SuccessResponse,
    dependencies=[Depends(get_current_user)],
)
async def get_invoice_for_order(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    invoice = await payments_controller.get_invoice_for_order(order_id, current_user, db_session)
    return SuccessResponse(message="Invoice", data=invoice)


@router.get(
    "/invoices/{invoice_id}",
    response_model=SuccessResponse,
    dependencies=[Depends(get_current_user)],
)
async def get_invoice(
    invoice_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    invoice = await payments_controller.get_invoice(invoice_id, current_user, db_session)
    return SuccessResponse(message="Invoice", data=invoice)


@router.post(
    "/invoices/{invoice_id}/finalize",
    response_model=SuccessResponse,
    dependencies=[Depends(get_current_user), _staff_only],
)
async def finalize_invoice(
    invoice_id: uuid.UUID, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    invoice = await payments_controller.finalize_invoice(invoice_id, db_session)
    return SuccessResponse(message="Invoice finalized", data=invoice)


@router.post(
    "/invoices/{invoice_id}/void",
    response_model=SuccessResponse,
    dependencies=[Depends(get_current_user), _staff_only],
)
async def void_invoice(
    invoice_id: uuid.UUID, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    invoice = await payments_controller.void_invoice(invoice_id, db_session)
    return SuccessResponse(message="Invoice voided", data=invoice)


@router.post(
    "/invoices/{invoice_id}/payments",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_user)],
)
async def initiate_payment(
    invoice_id: uuid.UUID,
    request: InitiatePaymentRequest,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    payment = await payments_controller.initiate_payment(
        invoice_id, current_user, request, db_session
    )
    return SuccessResponse(message="Payment initiated", data=payment)


@router.post(
    "/payments/{payment_id}/charge",
    response_model=SuccessResponse,
    dependencies=[Depends(get_current_user)],
)
async def charge_payment(
    payment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    payment = await payments_controller.charge_payment(payment_id, current_user, db_session)
    return SuccessResponse(message="Payment charged", data=payment)


@router.get(
    "/payments/{payment_id}",
    response_model=SuccessResponse,
    dependencies=[Depends(get_current_user)],
)
async def get_payment(
    payment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    payment = await payments_controller.get_payment(payment_id, current_user, db_session)
    return SuccessResponse(message="Payment", data=payment)


@router.post(
    "/payments/{payment_id}/refunds",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_user), _staff_only],
)
async def refund_payment(
    payment_id: uuid.UUID,
    request: RefundRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    refund = await payments_controller.refund_payment(payment_id, request, db_session)
    return SuccessResponse(message="Refund processed", data=refund)


@router.get(
    "/payments/{payment_id}/refunds",
    response_model=SuccessResponse,
    dependencies=[Depends(get_current_user)],
)
async def list_refunds(
    payment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    refunds = await payments_controller.list_refunds(payment_id, current_user, db_session)
    return SuccessResponse(message="Refunds", data=refunds)


@router.post(
    "/webhooks/payments",
    response_model=SuccessResponse,
    dependencies=[Depends(_verify_webhook_secret)],
)
async def payment_webhook(
    payload: PaymentWebhookPayload, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    await payments_controller.handle_webhook(payload, db_session)
    return SuccessResponse(message="Webhook processed")
