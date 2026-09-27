"""Concurrency test for slot capacity reservation — proves the atomic
conditional ``UPDATE`` in ``PickupSlotRepository.try_reserve_capacity``
actually prevents overbooking under simultaneous requests, not just in
sequential logic.

Uses its own real, *committed* data and one independent connection per
concurrent task, deliberately bypassing the shared ``db_session``
fixture: a real race only exists if every task sees the same
already-committed slot row, and true concurrency needs separate
connections (asyncpg can't run concurrent statements on one connection,
which the shared savepoint-per-test fixture is). Cleans up everything
it commits in a ``finally`` block, since nothing here is rolled back
automatically the way the rest of the suite is.
"""

import asyncio
import uuid
from datetime import date, time
from decimal import Decimal

import pytest
from sqlalchemy import delete, text

from core.database.engine import get_engine
from core.database.session import get_session_factory
from core.models.service_area import ServiceArea
from core.models.user import User
from washy_washy.repositories.pickup_slot_repo import PickupSlotRepository
from washy_washy.services.auth_service import AuthService
from washy_washy.services.availability_service import AvailabilityService
from washy_washy.services.service_area_service import ServiceAreaService


async def _db_reachable() -> bool:
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.mark.asyncio
async def test_concurrent_bookings_never_exceed_capacity() -> None:
    """10 concurrent booking attempts, each for 1 unit, against a slot
    with capacity for exactly 3. Exactly 3 must succeed; the slot's
    ``capacity_reserved`` must land exactly on ``capacity_total``,
    never over it, regardless of how the 10 attempts interleaved.
    """
    if not await _db_reachable():
        pytest.skip("PostgreSQL is not reachable")

    session_factory = get_session_factory()
    area_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None

    try:
        async with session_factory() as setup_session:
            area = await ServiceAreaService(setup_session).create_service_area(
                f"ConcurrencyArea-{uuid.uuid4()}", []
            )
            slot = await AvailabilityService(setup_session).create_pickup_slot(
                area.id, date.today(), time(9, 0), time(10, 0), "ORDERS", Decimal("3")
            )
            customer = await AuthService(setup_session).register(
                email=f"concurrency-{uuid.uuid4()}@example.com",
                password="longenough1",
                first_name="Concurrency",
            )
            await setup_session.commit()
            area_id = area.id
            slot_id = slot.id
            customer_id = customer.id

        async def attempt_booking() -> bool:
            async with session_factory() as session:
                try:
                    await AvailabilityService(session).book_pickup_slot(
                        slot_id, customer_id, Decimal("1")
                    )
                    await session.commit()
                    return True
                except Exception:
                    await session.rollback()
                    return False

        results = await asyncio.gather(*(attempt_booking() for _ in range(10)))

        assert sum(results) == 3

        async with session_factory() as check_session:
            refreshed_slot = await PickupSlotRepository(check_session).get_by_id(slot_id)
            assert refreshed_slot.capacity_reserved == Decimal("3")
    finally:
        async with session_factory() as cleanup_session:
            if area_id is not None:
                await cleanup_session.execute(delete(ServiceArea).where(ServiceArea.id == area_id))
            if customer_id is not None:
                await cleanup_session.execute(delete(User).where(User.id == customer_id))
            await cleanup_session.commit()
