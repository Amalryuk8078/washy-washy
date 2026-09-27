"""Integration tests for OrderService — creation, ownership, itemization,
and price finalization — against a real PostgreSQL database. The state
machine's own transition/authorization/concurrency behavior is covered
separately in test_order_state_machine.py.
"""

import uuid
from decimal import Decimal

import pytest

from core.exceptions import BusinessRuleException, NotFoundException
from core.models.order import OrderStatus
from core.models.pricing_rule import PricingModel
from washy_washy.services.address_service import AddressService
from washy_washy.services.auth_service import AuthService
from washy_washy.services.catalog_service import CatalogService
from washy_washy.services.order_service import OrderItemInput, OrderService
from washy_washy.services.pricing_service import PricingService
from washy_washy.services.service_area_service import ServiceAreaService


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


def _unique_postal_code() -> str:
    return str(uuid.uuid4().int)[:10]


async def _make_customer(db_session):
    return await AuthService(db_session).register(
        email=f"{_unique('customer')}@example.com", password="longenough1", first_name="Cust"
    )


async def _make_priced_service(db_session, *, pricing_model=PricingModel.PER_ITEM.value):
    catalog = CatalogService(db_session)
    service = await catalog.create_service(_unique("Wash"))
    material = await catalog.create_material(_unique("Cotton"))
    await PricingService(db_session).set_service_pricing(
        service.id, pricing_model, Decimal("5.00"), Decimal("2.00")
    )
    return service, material


async def _make_serviceable_address(db_session, customer):
    postal_code = _unique_postal_code()
    await ServiceAreaService(db_session).create_service_area(_unique("Area"), [postal_code])

    return await AddressService(db_session).create_address(
        customer.id,
        address_line_1="1 Main St",
        city="Metropolis",
        state="State",
        postal_code=postal_code,
        country="Country",
        label="HOME",
    )


@pytest.mark.asyncio
async def test_create_order_computes_estimated_total(db_session) -> None:
    customer = await _make_customer(db_session)
    service, material = await _make_priced_service(db_session)
    address = await _make_serviceable_address(db_session, customer)

    order = await OrderService(db_session).create_order(
        customer.id,
        pickup_address_id=address.id,
        delivery_address_id=address.id,
        items=[
            OrderItemInput(
                service_id=service.id, declared_material_id=material.id, declared_quantity=3
            )
        ],
    )

    # base 5.00 + unit_price 2.00 * quantity 3 = 5.00 + 6.00 = 11.00
    assert order.estimated_total == Decimal("11.00")
    assert order.status == OrderStatus.DRAFT.value


@pytest.mark.asyncio
async def test_create_order_with_rush_and_tax(db_session) -> None:
    customer = await _make_customer(db_session)
    service, material = await _make_priced_service(db_session)
    address = await _make_serviceable_address(db_session, customer)

    order = await OrderService(db_session).create_order(
        customer.id,
        pickup_address_id=address.id,
        delivery_address_id=address.id,
        items=[
            OrderItemInput(
                service_id=service.id, declared_material_id=material.id, declared_quantity=1
            )
        ],
        rush_charge=Decimal("3.00"),
        tax=Decimal("1.00"),
        discount=Decimal("0.50"),
    )

    # item subtotal = 5.00 + 2.00 = 7.00; total = 7.00 + 3.00 + 1.00 - 0.50
    assert order.estimated_total == Decimal("10.50")


@pytest.mark.asyncio
async def test_create_order_requires_at_least_one_item(db_session) -> None:
    customer = await _make_customer(db_session)
    address = await _make_serviceable_address(db_session, customer)

    with pytest.raises(BusinessRuleException):
        await OrderService(db_session).create_order(
            customer.id,
            pickup_address_id=address.id,
            delivery_address_id=address.id,
            items=[],
        )


@pytest.mark.asyncio
async def test_create_order_rejects_non_serviceable_address(db_session) -> None:
    customer = await _make_customer(db_session)
    service, material = await _make_priced_service(db_session)

    address = await AddressService(db_session).create_address(
        customer.id,
        address_line_1="1 Nowhere",
        city="Nowhere",
        state="State",
        postal_code=_unique_postal_code(),
        country="Country",
        label="HOME",
    )

    with pytest.raises(BusinessRuleException):
        await OrderService(db_session).create_order(
            customer.id,
            pickup_address_id=address.id,
            delivery_address_id=address.id,
            items=[
                OrderItemInput(
                    service_id=service.id, declared_material_id=material.id, declared_quantity=1
                )
            ],
        )


@pytest.mark.asyncio
async def test_create_order_rejects_address_owned_by_another_customer(db_session) -> None:
    customer = await _make_customer(db_session)
    other_customer = await _make_customer(db_session)
    service, material = await _make_priced_service(db_session)
    other_address = await _make_serviceable_address(db_session, other_customer)

    with pytest.raises(NotFoundException):
        await OrderService(db_session).create_order(
            customer.id,
            pickup_address_id=other_address.id,
            delivery_address_id=other_address.id,
            items=[
                OrderItemInput(
                    service_id=service.id, declared_material_id=material.id, declared_quantity=1
                )
            ],
        )


@pytest.mark.asyncio
async def test_get_order_for_viewer_ownership(db_session) -> None:
    customer = await _make_customer(db_session)
    other_customer = await _make_customer(db_session)
    service, material = await _make_priced_service(db_session)
    address = await _make_serviceable_address(db_session, customer)
    service_layer = OrderService(db_session)
    order = await service_layer.create_order(
        customer.id,
        pickup_address_id=address.id,
        delivery_address_id=address.id,
        items=[
            OrderItemInput(
                service_id=service.id, declared_material_id=material.id, declared_quantity=1
            )
        ],
    )

    fetched = await service_layer.get_order_for_viewer(order.id, customer.id, is_staff=False)
    assert fetched.id == order.id

    with pytest.raises(NotFoundException):
        await service_layer.get_order_for_viewer(order.id, other_customer.id, is_staff=False)

    # Staff can view regardless of ownership.
    staff_view = await service_layer.get_order_for_viewer(
        order.id, other_customer.id, is_staff=True
    )
    assert staff_view.id == order.id


@pytest.mark.asyncio
async def test_list_own_orders_excludes_other_customers(db_session) -> None:
    customer = await _make_customer(db_session)
    other_customer = await _make_customer(db_session)
    service, material = await _make_priced_service(db_session)
    address = await _make_serviceable_address(db_session, customer)
    other_address = await _make_serviceable_address(db_session, other_customer)
    service_layer = OrderService(db_session)
    await service_layer.create_order(
        customer.id,
        pickup_address_id=address.id,
        delivery_address_id=address.id,
        items=[
            OrderItemInput(
                service_id=service.id, declared_material_id=material.id, declared_quantity=1
            )
        ],
    )
    await service_layer.create_order(
        other_customer.id,
        pickup_address_id=other_address.id,
        delivery_address_id=other_address.id,
        items=[
            OrderItemInput(
                service_id=service.id, declared_material_id=material.id, declared_quantity=1
            )
        ],
    )

    own_orders = await service_layer.list_own_orders(customer.id)
    assert all(o.customer_id == customer.id for o in own_orders)
    assert len(own_orders) == 1


@pytest.mark.asyncio
async def test_itemize_order_item_records_verified_fields(db_session) -> None:
    customer = await _make_customer(db_session)
    service, material = await _make_priced_service(db_session)
    verified_material = await CatalogService(db_session).create_material(_unique("Silk"))
    address = await _make_serviceable_address(db_session, customer)
    service_layer = OrderService(db_session)
    order = await service_layer.create_order(
        customer.id,
        pickup_address_id=address.id,
        delivery_address_id=address.id,
        items=[
            OrderItemInput(
                service_id=service.id, declared_material_id=material.id, declared_quantity=2
            )
        ],
    )
    items = await service_layer.list_items(order.id)
    item = items[0]

    updated = await service_layer.itemize_order_item(
        order.id, item.id, verified_material_id=verified_material.id, verified_quantity=3
    )

    assert updated.verified_material_id == verified_material.id
    assert updated.verified_quantity == 3
    # Declared values are preserved, not overwritten.
    assert updated.declared_quantity == 2
    assert updated.declared_material_id == material.id


@pytest.mark.asyncio
async def test_itemize_order_item_wrong_order_id_raises_not_found(db_session) -> None:
    customer = await _make_customer(db_session)
    service, material = await _make_priced_service(db_session)
    address = await _make_serviceable_address(db_session, customer)
    service_layer = OrderService(db_session)
    order = await service_layer.create_order(
        customer.id,
        pickup_address_id=address.id,
        delivery_address_id=address.id,
        items=[
            OrderItemInput(
                service_id=service.id, declared_material_id=material.id, declared_quantity=1
            )
        ],
    )
    items = await service_layer.list_items(order.id)

    with pytest.raises(NotFoundException):
        await service_layer.itemize_order_item(uuid.uuid4(), items[0].id, verified_quantity=5)


async def _advance_to(service_layer, order_id, customer_id, statuses: list[OrderStatus]) -> None:
    for status in statuses:
        await service_layer.transition(
            order_id,
            status,
            requester_user_id=customer_id,
            requester_is_staff=True,
            changed_by_role="ADMIN",
        )


@pytest.mark.asyncio
async def test_finalize_pricing_uses_verified_values_and_transitions(db_session) -> None:
    customer = await _make_customer(db_session)
    service, material = await _make_priced_service(db_session)
    verified_material = await CatalogService(db_session).create_material(_unique("Silk"))
    address = await _make_serviceable_address(db_session, customer)
    service_layer = OrderService(db_session)
    order = await service_layer.create_order(
        customer.id,
        pickup_address_id=address.id,
        delivery_address_id=address.id,
        items=[
            OrderItemInput(
                service_id=service.id, declared_material_id=material.id, declared_quantity=2
            )
        ],
    )
    items = await service_layer.list_items(order.id)
    await service_layer.itemize_order_item(
        order.id, items[0].id, verified_material_id=verified_material.id, verified_quantity=4
    )
    await _advance_to(
        service_layer,
        order.id,
        customer.id,
        [
            OrderStatus.PENDING_PAYMENT,
            OrderStatus.CONFIRMED,
            OrderStatus.PICKUP_SCHEDULED,
            OrderStatus.PICKUP_ASSIGNED,
            OrderStatus.PICKUP_IN_PROGRESS,
            OrderStatus.PICKED_UP,
            OrderStatus.RECEIVED_AT_FACILITY,
            OrderStatus.INSPECTION,
            OrderStatus.ITEMIZED,
        ],
    )

    finalized = await service_layer.finalize_pricing(
        order.id, customer.id, requester_is_staff=True, changed_by_role="ADMIN"
    )

    # verified quantity (4) * unit_price 2.00 + base 5.00 = 13.00
    assert finalized.final_total == Decimal("13.00")
    assert finalized.status == OrderStatus.PRICE_FINALIZED.value
    final_item = (await service_layer.list_items(order.id))[0]
    assert final_item.final_line_total == Decimal("13.00")
