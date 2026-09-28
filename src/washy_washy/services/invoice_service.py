"""Invoice business logic: creating an immutable billing snapshot from
a priced order, and the DRAFT -> FINALIZED/VOID lifecycle.

Deliberately independent of ``OrderService``/``OrderStateService`` —
this only reads an order's already-finalized items
(``OrderItem.final_line_total``, set by Phase 8's
``OrderService.finalize_pricing``); it never recomputes a price itself
and never changes the order's own status. The strict separation the
Phase 10 spec draws (``ORDER`` is operational workflow, ``INVOICE`` is
amount owed) is enforced by this module simply having no dependency on
``OrderStateService`` at all.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import BusinessRuleException, ConflictException, NotFoundException
from core.models.invoice import Invoice, InvoiceStatus
from core.models.invoice_item import InvoiceItem
from core.models.order import OrderStatus
from washy_washy.constants import error_codes, error_messages
from washy_washy.repositories.invoice_item_repo import InvoiceItemRepository
from washy_washy.repositories.invoice_repo import InvoiceRepository
from washy_washy.repositories.order_item_repo import OrderItemRepository
from washy_washy.repositories.order_repo import OrderRepository

ZERO = Decimal("0")


class InvoiceService:
    def __init__(self, session: AsyncSession) -> None:
        self._invoices = InvoiceRepository(session)
        self._invoice_items = InvoiceItemRepository(session)
        self._orders = OrderRepository(session)
        self._order_items = OrderItemRepository(session)

    async def create_invoice_from_order(
        self,
        order_id: uuid.UUID,
        *,
        tax: Decimal = ZERO,
        discount: Decimal = ZERO,
    ) -> Invoice:
        """Snapshots each item's ``final_line_total`` into an
        ``InvoiceItem`` and sums them into ``subtotal``. Requires the
        order to already be ``PRICE_FINALIZED`` -- an invoice bills
        what pricing already settled, it never triggers that
        settlement itself.
        """
        order = await self._orders.get_by_id(order_id)
        if order is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        if order.status != OrderStatus.PRICE_FINALIZED.value:
            raise BusinessRuleException(
                error_messages.ORDER_NOT_PRICE_FINALIZED, error_codes.ORDER_NOT_PRICE_FINALIZED
            )
        if await self._invoices.get_by_order_id(order_id) is not None:
            raise ConflictException(
                error_messages.INVOICE_ALREADY_EXISTS, error_codes.INVOICE_ALREADY_EXISTS
            )

        order_items = await self._order_items.list_for_order(order_id)
        subtotal = ZERO
        invoice = await self._invoices.create(
            Invoice(
                order_id=order_id,
                subtotal=ZERO,
                tax=tax,
                discount=discount,
                total=ZERO,
            )
        )
        for item in order_items:
            amount = item.final_line_total or ZERO
            await self._invoice_items.create(
                InvoiceItem(
                    invoice_id=invoice.id,
                    order_item_id=item.id,
                    description=f"Service {item.service_id} / material {item.declared_material_id}",
                    amount=amount,
                )
            )
            subtotal += amount

        invoice.subtotal = subtotal
        invoice.total = subtotal + tax - discount
        return await self._invoices.update(invoice)

    async def get_invoice(self, invoice_id: uuid.UUID) -> Invoice:
        invoice = await self._invoices.get_by_id(invoice_id)
        if invoice is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        return invoice

    async def get_invoice_for_order(self, order_id: uuid.UUID) -> Invoice:
        invoice = await self._invoices.get_by_order_id(order_id)
        if invoice is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        return invoice

    async def list_items(self, invoice_id: uuid.UUID) -> list[InvoiceItem]:
        return await self._invoice_items.list_for_invoice(invoice_id)

    async def finalize_invoice(self, invoice_id: uuid.UUID) -> Invoice:
        """DRAFT -> FINALIZED. After this, no method in this service
        (or anywhere else) can alter ``subtotal``/``tax``/``discount``/
        ``total`` -- there simply isn't one. That's what "immutable
        after finalization" means concretely here.
        """
        invoice = await self.get_invoice(invoice_id)
        if invoice.status != InvoiceStatus.DRAFT.value:
            raise BusinessRuleException(
                error_messages.INVOICE_NOT_DRAFT, error_codes.INVOICE_NOT_DRAFT
            )
        invoice.status = InvoiceStatus.FINALIZED.value
        invoice.finalized_at = datetime.now(UTC)
        return await self._invoices.update(invoice)

    async def void_invoice(self, invoice_id: uuid.UUID) -> Invoice:
        """Only allowed while nothing has been paid yet -- once any
        payment has applied, correcting an invoice goes through a
        refund, never a silent void.
        """
        invoice = await self.get_invoice(invoice_id)
        if invoice.amount_paid > ZERO:
            raise BusinessRuleException(
                error_messages.INVOICE_HAS_PAYMENTS, error_codes.INVOICE_HAS_PAYMENTS
            )
        invoice.status = InvoiceStatus.VOID.value
        return await self._invoices.update(invoice)
