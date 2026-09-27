"""Order assignment: who is handling an order (facility, pickup
operator, delivery operator) — kept deliberately separate from
scheduling (Phase 8's ``pickup_slot_id``/``delivery_slot_id``), per the
Phase 9 spec's own instruction that *who* and *when* are independent
concerns.

Assigning a pickup/delivery operator for the **first** time also drives
the corresponding ``OrderStatus`` transition (``PICKUP_SCHEDULED ->
PICKUP_ASSIGNED`` / ``READY_FOR_DELIVERY -> DELIVERY_ASSIGNED``) —
the same "one call changes data and moves status" pattern as
``OrderService.schedule_pickup``/``finalize_pricing`` (Phase 8).
Reassigning an order that's already past that status only updates who
is assigned; it never regresses the order's own status.

Every assignment/reassignment is recorded in
``OrderAssignmentHistory``, mirroring ``OrderStatusHistory`` exactly —
nothing here silently overwrites who was previously assigned.

Authorization for *who may call this* (staff-only) is enforced at the
route layer, the same as Phase 8's itemize/finalize-price; what's
validated here is a business rule about the *target*: an operator
being assigned must actually hold a staff role, so a plain customer
can never end up as a pickup/delivery operator.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import BusinessRuleException, NotFoundException
from core.models.order import Order, OrderStatus
from core.models.order_assignment_history import AssignmentRole, OrderAssignmentHistory
from core.models.role import RoleName
from washy_washy.constants import error_codes, error_messages
from washy_washy.repositories.order_assignment_history_repo import (
    OrderAssignmentHistoryRepository,
)
from washy_washy.repositories.order_repo import OrderRepository
from washy_washy.repositories.partner_facility_repo import PartnerFacilityRepository
from washy_washy.services.order_state_service import OrderStateService
from washy_washy.services.rbac_service import RBACService

STAFF_ROLES = [RoleName.ADMIN.value, RoleName.SUPERVISOR.value, RoleName.LAUNDRY_PARTNER.value]


class AssignmentService:
    def __init__(self, session: AsyncSession) -> None:
        self._orders = OrderRepository(session)
        self._facilities = PartnerFacilityRepository(session)
        self._history = OrderAssignmentHistoryRepository(session)
        self._rbac = RBACService(session)
        self._order_state = OrderStateService(session)

    async def get_history(self, order_id: uuid.UUID) -> list[OrderAssignmentHistory]:
        return await self._history.list_for_order(order_id)

    async def assign_facility(
        self,
        order_id: uuid.UUID,
        facility_id: uuid.UUID,
        *,
        changed_by_user_id: uuid.UUID,
        reason: str | None = None,
    ) -> Order:
        order = await self._get_order(order_id)
        facility = await self._facilities.get_by_id(facility_id)
        if facility is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        if facility.service_area_id != order.service_area_id:
            raise BusinessRuleException(
                error_messages.FACILITY_OUTSIDE_SERVICE_AREA,
                error_codes.FACILITY_OUTSIDE_SERVICE_AREA,
            )

        previous = order.assigned_facility_id
        order.assigned_facility_id = facility_id
        await self._orders.update(order)
        await self._record(
            order_id, AssignmentRole.FACILITY, previous, facility_id, changed_by_user_id, reason
        )
        return order

    async def assign_pickup_operator(
        self,
        order_id: uuid.UUID,
        operator_user_id: uuid.UUID,
        *,
        changed_by_user_id: uuid.UUID,
        reason: str | None = None,
    ) -> Order:
        order = await self._get_order(order_id)
        await self._validate_staff(operator_user_id)

        previous = order.pickup_operator_user_id
        order.pickup_operator_user_id = operator_user_id
        await self._orders.update(order)
        await self._record(
            order_id,
            AssignmentRole.PICKUP_OPERATOR,
            previous,
            operator_user_id,
            changed_by_user_id,
            reason,
        )

        if OrderStatus(order.status) == OrderStatus.PICKUP_SCHEDULED:
            order = await self._order_state.transition(
                order_id,
                OrderStatus.PICKUP_ASSIGNED,
                requester_user_id=changed_by_user_id,
                requester_is_staff=True,
                reason="Pickup operator assigned",
            )
        return order

    async def assign_delivery_operator(
        self,
        order_id: uuid.UUID,
        operator_user_id: uuid.UUID,
        *,
        changed_by_user_id: uuid.UUID,
        reason: str | None = None,
    ) -> Order:
        order = await self._get_order(order_id)
        await self._validate_staff(operator_user_id)

        previous = order.delivery_operator_user_id
        order.delivery_operator_user_id = operator_user_id
        await self._orders.update(order)
        await self._record(
            order_id,
            AssignmentRole.DELIVERY_OPERATOR,
            previous,
            operator_user_id,
            changed_by_user_id,
            reason,
        )

        if OrderStatus(order.status) == OrderStatus.READY_FOR_DELIVERY:
            order = await self._order_state.transition(
                order_id,
                OrderStatus.DELIVERY_ASSIGNED,
                requester_user_id=changed_by_user_id,
                requester_is_staff=True,
                reason="Delivery operator assigned",
            )
        return order

    async def _get_order(self, order_id: uuid.UUID) -> Order:
        order = await self._orders.get_by_id(order_id)
        if order is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        return order

    async def _validate_staff(self, user_id: uuid.UUID) -> None:
        if not await self._rbac.has_any_role(user_id, STAFF_ROLES):
            raise BusinessRuleException(
                error_messages.OPERATOR_MUST_BE_STAFF, error_codes.OPERATOR_MUST_BE_STAFF
            )

    async def _record(
        self,
        order_id: uuid.UUID,
        role: AssignmentRole,
        previous: uuid.UUID | None,
        new: uuid.UUID | None,
        changed_by_user_id: uuid.UUID,
        reason: str | None,
    ) -> None:
        await self._history.create(
            OrderAssignmentHistory(
                order_id=order_id,
                assignment_role=role.value,
                previous_assignee_id=previous,
                new_assignee_id=new,
                changed_by_user_id=changed_by_user_id,
                reason=reason,
            )
        )
