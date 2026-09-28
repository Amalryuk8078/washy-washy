"""Integration tests for InvoiceService — creating an invoice from a
priced order, and the DRAFT -> FINALIZED/VOID lifecycle — against a
real PostgreSQL database.
"""

import uuid
from decimal import Decimal

import pytest

from core.exceptions import BusinessRuleException, ConflictException, NotFoundException
from core.models.invoice import InvoiceStatus
from core.models.order import OrderStatus
from core.models.pricing_rule import PricingModel
from washy_washy.services.address_service import AddressService
from washy_washy.services.auth_service import AuthService
from washy_washy.services.catalog_service import CatalogService
from washy_washy.services.invoice_service import InvoiceService
from washy_washy.services.order_service import OrderItemInput, OrderService
from washy_washy.services.order_state_service import OrderStateService
from washy_washy.services.pricing_service import PricingService
from washy_washy.services.service_area_service import ServiceAreaService


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


def _unique_postal_code() -> str:
    return str(uuid.uuid4().int)[:10]


async def _make_finalized_order(db_session, *, quantity: int = 2):
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
    return order, customer


@pytest.mark.asyncio
async def test_create_invoice_from_finalized_order(db_session) -> None:
    order, _customer = await _make_finalized_order(db_session, quantity=2)

    invoice = await InvoiceService(db_session).create_invoice_from_order(order.id)

    # base 5.00 + unit_price 2.00 * 2 = 9.00
    assert invoice.subtotal == Decimal("9.00")
    assert invoice.total == Decimal("9.00")
    assert invoice.status == InvoiceStatus.DRAFT.value
    assert invoice.amount_paid == Decimal("0")


@pytest.mark.asyncio
async def test_create_invoice_snapshots_items(db_session) -> None:
    order, _customer = await _make_finalized_order(db_session, quantity=3)

    service = InvoiceService(db_session)
    invoice = await service.create_invoice_from_order(order.id)
    items = await service.list_items(invoice.id)

    assert len(items) == 1
    assert items[0].amount == invoice.subtotal


@pytest.mark.asyncio
async def test_create_invoice_with_tax_and_discount(db_session) -> None:
    order, _customer = await _make_finalized_order(db_session, quantity=1)

    invoice = await InvoiceService(db_session).create_invoice_from_order(
        order.id, tax=Decimal("1.00"), discount=Decimal("0.50")
    )

    # subtotal 7.00 (5.00 + 2.00) + tax 1.00 - discount 0.50
    assert invoice.subtotal == Decimal("7.00")
    assert invoice.total == Decimal("7.50")


@pytest.mark.asyncio
async def test_create_invoice_requires_price_finalized_order(db_session) -> None:
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
    order = await OrderService(db_session).create_order(
        customer.id,
        pickup_address_id=address.id,
        delivery_address_id=address.id,
        items=[
            OrderItemInput(
                service_id=service.id, declared_material_id=material.id, declared_quantity=1
            )
        ],
    )

    with pytest.raises(BusinessRuleException):
        await InvoiceService(db_session).create_invoice_from_order(order.id)


@pytest.mark.asyncio
async def test_create_invoice_twice_rejected(db_session) -> None:
    order, _customer = await _make_finalized_order(db_session)
    service = InvoiceService(db_session)
    await service.create_invoice_from_order(order.id)

    with pytest.raises(ConflictException):
        await service.create_invoice_from_order(order.id)


@pytest.mark.asyncio
async def test_finalize_invoice(db_session) -> None:
    order, _customer = await _make_finalized_order(db_session)
    service = InvoiceService(db_session)
    invoice = await service.create_invoice_from_order(order.id)

    finalized = await service.finalize_invoice(invoice.id)

    assert finalized.status == InvoiceStatus.FINALIZED.value
    assert finalized.finalized_at is not None


@pytest.mark.asyncio
async def test_finalize_invoice_twice_rejected(db_session) -> None:
    order, _customer = await _make_finalized_order(db_session)
    service = InvoiceService(db_session)
    invoice = await service.create_invoice_from_order(order.id)
    await service.finalize_invoice(invoice.id)

    with pytest.raises(BusinessRuleException):
        await service.finalize_invoice(invoice.id)


@pytest.mark.asyncio
async def test_void_invoice_with_no_payments(db_session) -> None:
    order, _customer = await _make_finalized_order(db_session)
    service = InvoiceService(db_session)
    invoice = await service.create_invoice_from_order(order.id)
    await service.finalize_invoice(invoice.id)

    voided = await service.void_invoice(invoice.id)

    assert voided.status == InvoiceStatus.VOID.value


@pytest.mark.asyncio
async def test_get_invoice_nonexistent_raises_not_found(db_session) -> None:
    with pytest.raises(NotFoundException):
        await InvoiceService(db_session).get_invoice(uuid.uuid4())
