"""Integration tests for AssignmentService — facility/operator
assignment and reassignment, the operator-drives-transition behavior,
and the Phase 9 facility-inspection additions to itemization — against
a real PostgreSQL database.
"""

import uuid
from decimal import Decimal

import pytest

from core.exceptions import BusinessRuleException, NotFoundException
from core.models.order import OrderStatus
from core.models.pricing_rule import PricingModel
from core.models.role import RoleName
from washy_washy.repositories.role_repo import RoleRepository
from washy_washy.repositories.user_role_repo import UserRoleRepository
from washy_washy.services.address_service import AddressService
from washy_washy.services.assignment_service import AssignmentService
from washy_washy.services.auth_service import AuthService
from washy_washy.services.catalog_service import CatalogService
from washy_washy.services.facility_service import PartnerFacilityService
from washy_washy.services.order_service import OrderItemInput, OrderService
from washy_washy.services.order_state_service import OrderStateService
from washy_washy.services.pricing_service import PricingService
from washy_washy.services.profile_service import ProfileService
from washy_washy.services.service_area_service import ServiceAreaService


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


def _unique_postal_code() -> str:
    return str(uuid.uuid4().int)[:10]


async def _make_customer(db_session):
    return await AuthService(db_session).register(
        email=f"{_unique('customer')}@example.com", password="longenough1", first_name="Cust"
    )


async def _make_staff_user(db_session, role_name: str = RoleName.LAUNDRY_PARTNER.value):
    user = await AuthService(db_session).register(
        email=f"{_unique('staff')}@example.com", password="longenough1", first_name="Staff"
    )
    role = await RoleRepository(db_session).get_by_name(role_name)
    await UserRoleRepository(db_session).assign_role(user.id, role.id)
    return user


async def _make_order(db_session):
    customer = await _make_customer(db_session)
    catalog = CatalogService(db_session)
    service = await catalog.create_service(_unique("Wash"))
    material = await catalog.create_material(_unique("Cotton"))
    await PricingService(db_session).set_service_pricing(
        service.id, PricingModel.PER_ITEM.value, Decimal("5.00"), Decimal("2.00")
    )
    postal_code = _unique_postal_code()
    area = await ServiceAreaService(db_session).create_service_area(_unique("Area"), [postal_code])
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
    return order, customer, area


async def _make_facility(db_session, service_area_id):
    partner_user = await AuthService(db_session).register(
        email=f"{_unique('partner')}@example.com", password="longenough1", first_name="Partner"
    )
    partner_profile = await ProfileService(db_session).create_partner_profile(
        partner_user.id, business_name=_unique("Laundry")
    )
    return await PartnerFacilityService(db_session).create_facility(
        partner_profile.id,
        service_area_id,
        name=_unique("Site"),
        address_line_1="1 Wash St",
        city="Metropolis",
        state="State",
        postal_code="00000",
        country="Country",
    )


@pytest.mark.asyncio
async def test_assign_facility_success_records_history(db_session) -> None:
    order, _customer, area = await _make_order(db_session)
    facility = await _make_facility(db_session, area.id)
    staff = await _make_staff_user(db_session)
    service = AssignmentService(db_session)

    updated = await service.assign_facility(
        order.id, facility.id, changed_by_user_id=staff.id, reason="Nearest site"
    )

    assert updated.assigned_facility_id == facility.id
    history = await service.get_history(order.id)
    assert len(history) == 1
    assert history[0].assignment_role == "FACILITY"
    assert history[0].previous_assignee_id is None
    assert history[0].new_assignee_id == facility.id
    assert history[0].changed_by_user_id == staff.id


@pytest.mark.asyncio
async def test_reassign_facility_records_previous_value(db_session) -> None:
    order, _customer, area = await _make_order(db_session)
    facility_one = await _make_facility(db_session, area.id)
    facility_two = await _make_facility(db_session, area.id)
    staff = await _make_staff_user(db_session)
    service = AssignmentService(db_session)
    await service.assign_facility(order.id, facility_one.id, changed_by_user_id=staff.id)

    updated = await service.assign_facility(
        order.id, facility_two.id, changed_by_user_id=staff.id, reason="Reassigned"
    )

    assert updated.assigned_facility_id == facility_two.id
    history = await service.get_history(order.id)
    assert len(history) == 2
    assert history[1].previous_assignee_id == facility_one.id
    assert history[1].new_assignee_id == facility_two.id


@pytest.mark.asyncio
async def test_assign_facility_outside_service_area_rejected(db_session) -> None:
    order, _customer, _area = await _make_order(db_session)
    other_area = await ServiceAreaService(db_session).create_service_area(_unique("Other"), [])
    facility = await _make_facility(db_session, other_area.id)
    staff = await _make_staff_user(db_session)

    with pytest.raises(BusinessRuleException):
        await AssignmentService(db_session).assign_facility(
            order.id, facility.id, changed_by_user_id=staff.id
        )


@pytest.mark.asyncio
async def test_assign_facility_nonexistent_raises_not_found(db_session) -> None:
    order, _customer, _area = await _make_order(db_session)
    staff = await _make_staff_user(db_session)

    with pytest.raises(NotFoundException):
        await AssignmentService(db_session).assign_facility(
            order.id, uuid.uuid4(), changed_by_user_id=staff.id
        )


@pytest.mark.asyncio
async def test_assign_pickup_operator_requires_staff_role(db_session) -> None:
    order, _customer, _area = await _make_order(db_session)
    non_staff = await _make_customer(db_session)
    staff = await _make_staff_user(db_session)

    with pytest.raises(BusinessRuleException):
        await AssignmentService(db_session).assign_pickup_operator(
            order.id, non_staff.id, changed_by_user_id=staff.id
        )


@pytest.mark.asyncio
async def test_assign_pickup_operator_drives_transition_on_first_assignment(db_session) -> None:
    order, customer, _area = await _make_order(db_session)
    staff = await _make_staff_user(db_session)
    operator = await _make_staff_user(db_session)
    state_service = OrderStateService(db_session)
    await state_service.transition(
        order.id,
        OrderStatus.PENDING_PAYMENT,
        requester_user_id=customer.id,
        requester_is_staff=False,
    )
    await state_service.transition(
        order.id,
        OrderStatus.CONFIRMED,
        requester_user_id=staff.id,
        requester_is_staff=True,
    )
    await state_service.transition(
        order.id,
        OrderStatus.PICKUP_SCHEDULED,
        requester_user_id=staff.id,
        requester_is_staff=True,
    )

    updated = await AssignmentService(db_session).assign_pickup_operator(
        order.id, operator.id, changed_by_user_id=staff.id
    )

    assert updated.pickup_operator_user_id == operator.id
    assert updated.status == OrderStatus.PICKUP_ASSIGNED.value


@pytest.mark.asyncio
async def test_reassigning_pickup_operator_does_not_regress_status(db_session) -> None:
    order, customer, _area = await _make_order(db_session)
    staff = await _make_staff_user(db_session)
    operator_one = await _make_staff_user(db_session)
    operator_two = await _make_staff_user(db_session)
    state_service = OrderStateService(db_session)
    for status in (
        OrderStatus.PENDING_PAYMENT,
        OrderStatus.CONFIRMED,
        OrderStatus.PICKUP_SCHEDULED,
    ):
        await state_service.transition(
            order.id,
            status,
            requester_user_id=staff.id,
            requester_is_staff=True,
        )
    assignment_service = AssignmentService(db_session)
    await assignment_service.assign_pickup_operator(
        order.id, operator_one.id, changed_by_user_id=staff.id
    )

    # Order is now PICKUP_ASSIGNED. Move it forward, then reassign the
    # operator -- this must not try to re-fire the PICKUP_ASSIGNED
    # transition (which would no longer be legal from PICKUP_IN_PROGRESS).
    await state_service.transition(
        order.id,
        OrderStatus.PICKUP_IN_PROGRESS,
        requester_user_id=staff.id,
        requester_is_staff=True,
    )

    updated = await assignment_service.assign_pickup_operator(
        order.id, operator_two.id, changed_by_user_id=staff.id, reason="Operator swap"
    )

    assert updated.pickup_operator_user_id == operator_two.id
    assert updated.status == OrderStatus.PICKUP_IN_PROGRESS.value


@pytest.mark.asyncio
async def test_itemize_records_condition_and_damage(db_session) -> None:
    order, _customer, _area = await _make_order(db_session)
    service = OrderService(db_session)
    items = await service.list_items(order.id)

    updated = await service.itemize_order_item(
        order.id,
        items[0].id,
        condition_notes="Small tear on sleeve",
        damage_reported=True,
    )

    assert updated.condition_notes == "Small tear on sleeve"
    assert updated.damage_reported is True
