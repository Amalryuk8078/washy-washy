"""Request/response schemas for invoice/payment/refund endpoints."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

ZERO = Decimal("0")


class CreateInvoiceRequest(BaseModel):
    tax: Decimal = ZERO
    discount: Decimal = ZERO


class InvoiceItemResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    invoice_id: uuid.UUID
    order_item_id: uuid.UUID
    description: str
    amount: Decimal
    created_at: datetime


class InvoiceResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    order_id: uuid.UUID
    status: str
    subtotal: Decimal
    tax: Decimal
    discount: Decimal
    total: Decimal
    amount_paid: Decimal
    finalized_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InvoiceWithItemsResponse(InvoiceResponse):
    items: list[InvoiceItemResponse] = []


class InitiatePaymentRequest(BaseModel):
    amount: Decimal
    currency: str = "USD"


class PaymentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: Decimal
    currency: str
    captured_amount: Decimal
    refunded_amount: Decimal
    status: str
    provider_reference: str | None
    created_at: datetime
    updated_at: datetime


class PaymentAttemptResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    payment_id: uuid.UUID
    status: str
    provider_reference: str | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


class PaymentWebhookPayload(BaseModel):
    event_id: str
    event_type: str
    provider_reference: str


class RefundRequest(BaseModel):
    amount: Decimal
    reason: str | None = None


class RefundResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    payment_id: uuid.UUID
    amount: Decimal
    status: str
    provider_reference: str | None
    reason: str | None
    created_at: datetime
    updated_at: datetime
