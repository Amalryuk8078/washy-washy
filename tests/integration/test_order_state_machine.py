"""Integration tests for the order state machine — legal/illegal
transitions, the customer-vs-staff authorization split, and history
recording — against a real PostgreSQL database.

The concurrency test at the bottom deliberately bypasses the shared
savepoint-based ``db_session`` fixture (a genuine race needs
independent connections, not one connection's savepoints) — the exact
same reasoning and structure as Phase 7's
``test_availability_concurrency.py``, applied here to
``OrderRepository.try_transition`` instead of
``PickupSlotRepository.try_reserve_capacity``.
"""

import asyncio
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import delete, text

from core.database.engine import get_engine
from core.database.session import get_session_factory
from core.exceptions import (
    BusinessRuleException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from core.models.order import Order, OrderStatus
from core.models.pricing_rule import PricingModel
from core.models.service_area import ServiceArea
from core.models.user import User
from washy_washy.services.address_service import AddressService
from washy_washy.services.auth_service import AuthService
from washy_washy.services.catalog_service import CatalogService
from washy_washy.services.order_service import OrderItemInput, OrderService
from washy_washy.services.order_state_service import OrderStateService
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


async def _make_order(db_session, customer=None):
    customer = customer or await _make_customer(db_session)
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
    return order, customer


@pytest.mark.asyncio
async def test_legal_transition_updates_status_and_records_history(db_session) -> None:
    order, customer = await _make_order(db_session)
    state_service = OrderStateService(db_session)

    updated = await state_service.transition(
        order.id,
        OrderStatus.PENDING_PAYMENT,
        requester_user_id=customer.id,
        requester_is_staff=False,
    )

    assert updated.status == OrderStatus.PENDING_PAYMENT.value
    history = await state_service.get_history(order.id)
    assert [h.to_status for h in history] == [
        OrderStatus.DRAFT.value,
        OrderStatus.PENDING_PAYMENT.value,
    ]
    assert history[-1].from_status == OrderStatus.DRAFT.value
    assert history[-1].changed_by_user_id == customer.id


@pytest.mark.asyncio
async def test_illegal_transition_raises_business_rule_error(db_session) -> None:
    order, customer = await _make_order(db_session)
    state_service = OrderStateService(db_session)

    with pytest.raises(BusinessRuleException):
        await state_service.transition(
            order.id,
            OrderStatus.PROCESSING,
            requester_user_id=customer.id,
            requester_is_staff=True,
        )


@pytest.mark.asyncio
async def test_completed_to_draft_is_rejected(db_session) -> None:
    order, customer = await _make_order(db_session)
    state_service = OrderStateService(db_session)
    # Force the order straight to a terminal state for this check --
    # legality of reaching COMPLETED via the normal pipeline is exercised
    # by the full-pipeline test in test_orders.py.
    order.status = OrderStatus.COMPLETED.value
    await db_session.flush()

    with pytest.raises(BusinessRuleException):
        await state_service.transition(
            order.id,
            OrderStatus.DRAFT,
            requester_user_id=customer.id,
            requester_is_staff=True,
        )


@pytest.mark.asyncio
async def test_customer_can_submit_and_cancel_own_order(db_session) -> None:
    order, customer = await _make_order(db_session)
    state_service = OrderStateService(db_session)

    submitted = await state_service.transition(
        order.id,
        OrderStatus.PENDING_PAYMENT,
        requester_user_id=customer.id,
        requester_is_staff=False,
    )
    cancelled = await state_service.transition(
        submitted.id,
        OrderStatus.CANCELLED,
        requester_user_id=customer.id,
        requester_is_staff=False,
    )

    assert cancelled.status == OrderStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_customer_cannot_perform_staff_only_transition(db_session) -> None:
    order, customer = await _make_order(db_session)
    state_service = OrderStateService(db_session)
    await state_service.transition(
        order.id,
        OrderStatus.PENDING_PAYMENT,
        requester_user_id=customer.id,
        requester_is_staff=False,
    )

    # PENDING_PAYMENT -> CONFIRMED is legal in the graph, but a plain
    # customer isn't permitted to perform it (that's staff/payment-gateway
    # territory).
    with pytest.raises(ForbiddenException):
        await state_service.transition(
            order.id,
            OrderStatus.CONFIRMED,
            requester_user_id=customer.id,
            requester_is_staff=False,
        )


@pytest.mark.asyncio
async def test_non_owner_non_staff_gets_not_found(db_session) -> None:
    order, _customer = await _make_order(db_session)
    intruder = await _make_customer(db_session)
    state_service = OrderStateService(db_session)

    with pytest.raises(NotFoundException):
        await state_service.transition(
            order.id,
            OrderStatus.CANCELLED,
            requester_user_id=intruder.id,
            requester_is_staff=False,
        )


@pytest.mark.asyncio
async def test_staff_can_transition_any_order(db_session) -> None:
    order, _customer = await _make_order(db_session)
    staff_user = await _make_customer(db_session)
    state_service = OrderStateService(db_session)

    updated = await state_service.transition(
        order.id,
        OrderStatus.PENDING_PAYMENT,
        requester_user_id=staff_user.id,
        requester_is_staff=True,
        changed_by_role="ADMIN",
    )

    assert updated.status == OrderStatus.PENDING_PAYMENT.value


async def _db_reachable() -> bool:
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.mark.asyncio
async def test_concurrent_transitions_never_both_succeed() -> None:
    """Several concurrent requests all try to make the *same* transition
    (cancelling the same DRAFT order) at once. Exactly one may actually
    change the row; every other attempt must fail closed — either with
    ``ORDER_STATE_CONFLICT`` (it raced the winner's ``UPDATE`` at the
    database level) or ``INVALID_ORDER_STATE_TRANSITION`` (it read the
    order only after the winner had already committed, so ``CANCELLED``
    was no longer a legal move from ``CANCELLED`` itself) — never a
    second, silently-accepted cancellation.

    Both outcomes are correct depending on how the attempts happened to
    interleave; what must never happen is more than one success, or the
    order ending up with more than one ``to_status=CANCELLED`` history
    row.
    """
    if not await _db_reachable():
        pytest.skip("PostgreSQL is not reachable")

    session_factory = get_session_factory()
    area_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None

    try:
        async with session_factory() as setup_session:
            order, customer = await _make_order(setup_session)
            await setup_session.commit()
            order_id = order.id
            area_id = order.service_area_id
            customer_id = customer.id

        async def attempt() -> bool:
            async with session_factory() as session:
                try:
                    await OrderStateService(session).transition(
                        order_id,
                        OrderStatus.CANCELLED,
                        requester_user_id=customer_id,
                        requester_is_staff=True,
                    )
                    await session.commit()
                    return True
                except (ConflictException, BusinessRuleException):
                    await session.rollback()
                    return False

        results = await asyncio.gather(*(attempt() for _ in range(8)))

        assert sum(results) == 1

        async with session_factory() as check_session:
            refreshed = await check_session.get(Order, order_id)
            assert refreshed.status == OrderStatus.CANCELLED.value

            history = await OrderStateService(check_session).get_history(order_id)
            cancel_entries = [h for h in history if h.to_status == OrderStatus.CANCELLED.value]
            assert len(cancel_entries) == 1
    finally:
        async with session_factory() as cleanup_session:
            # The user must go first: orders.customer_id cascades, which
            # takes the order (and its items/history) with it. orders.*
            # references to the address/service area deliberately do
            # *not* cascade (see Order's docstring), so deleting the
            # service area first would fail with a FK violation while
            # the order (now gone) used to reference it.
            if customer_id is not None:
                await cleanup_session.execute(delete(User).where(User.id == customer_id))
            if area_id is not None:
                await cleanup_session.execute(delete(ServiceArea).where(ServiceArea.id == area_id))
            await cleanup_session.commit()
