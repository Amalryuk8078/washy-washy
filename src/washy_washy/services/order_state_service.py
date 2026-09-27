"""The order state machine: the one place a transition is validated,
authorized, executed, and recorded.

**Concurrency safety** mirrors Phase 7's capacity reservation exactly:
``OrderRepository.try_transition`` is a single atomic conditional
``UPDATE`` (``WHERE status = :from_status``), not a read-then-write
from Python. Two concurrent requests trying to move the same order
never both "win" — whichever commits first changes the row; the
other's ``WHERE`` clause matches zero rows and gets a clean
``ORDER_STATE_CONFLICT`` instead of silently clobbering the first
request's transition. This is verified under genuine concurrent load in
``tests/integration/test_order_state_machine.py``, the same way Phase 7's
``test_availability_concurrency.py`` proved its own atomic ``UPDATE``.

**Two authorization tiers, not just "authenticated or not"**: most of
the pipeline (``PICKUP_ASSIGNED`` onward) is staff-driven and requires
the caller to hold ``ADMIN``/``SUPERVISOR``/``LAUNDRY_PARTNER``. A plain
customer may still request a narrow set of transitions on their *own*
order — submitting it (``DRAFT`` -> ``PENDING_PAYMENT``) and cancelling
it from any state where cancellation is still meaningful
(``_CUSTOMER_ALLOWED_TRANSITIONS`` below). A transition that's legal in
the state graph but not permitted for a non-staff caller raises
``ForbiddenException`` (403) — the caller knows the order exists and
is theirs, they're just not allowed to move it *there*. A caller who
doesn't own the order at all (and isn't staff) gets ``NotFoundException``
(404) instead, same posture as ``AddressService``.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import (
    BusinessRuleException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from core.models.order import Order, OrderStatus
from core.models.order_status_history import OrderStatusHistory
from washy_washy.constants import error_codes, error_messages
from washy_washy.repositories.order_repo import OrderRepository
from washy_washy.repositories.order_status_history_repo import OrderStatusHistoryRepository

# The full legal transition graph. Terminal states (COMPLETED, CANCELLED)
# map to an empty set -- there is deliberately no way back from either,
# which is what actually enforces the spec's example rule ("do not allow
# COMPLETED -> DRAFT") and every other backwards move, not just that one.
ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.DRAFT: frozenset({OrderStatus.PENDING_PAYMENT, OrderStatus.CANCELLED}),
    OrderStatus.PENDING_PAYMENT: frozenset(
        {OrderStatus.CONFIRMED, OrderStatus.PAYMENT_FAILED, OrderStatus.CANCELLED}
    ),
    OrderStatus.PAYMENT_FAILED: frozenset({OrderStatus.PENDING_PAYMENT, OrderStatus.CANCELLED}),
    OrderStatus.CONFIRMED: frozenset({OrderStatus.PICKUP_SCHEDULED, OrderStatus.CANCELLED}),
    OrderStatus.PICKUP_SCHEDULED: frozenset(
        {OrderStatus.PICKUP_ASSIGNED, OrderStatus.RESCHEDULED, OrderStatus.CANCELLED}
    ),
    OrderStatus.RESCHEDULED: frozenset({OrderStatus.PICKUP_SCHEDULED, OrderStatus.CANCELLED}),
    OrderStatus.PICKUP_ASSIGNED: frozenset(
        {OrderStatus.PICKUP_IN_PROGRESS, OrderStatus.PICKUP_FAILED, OrderStatus.CANCELLED}
    ),
    OrderStatus.PICKUP_FAILED: frozenset(
        {OrderStatus.PICKUP_ASSIGNED, OrderStatus.RESCHEDULED, OrderStatus.CANCELLED}
    ),
    OrderStatus.PICKUP_IN_PROGRESS: frozenset({OrderStatus.PICKED_UP, OrderStatus.PICKUP_FAILED}),
    OrderStatus.PICKED_UP: frozenset({OrderStatus.RECEIVED_AT_FACILITY}),
    OrderStatus.RECEIVED_AT_FACILITY: frozenset({OrderStatus.INSPECTION}),
    OrderStatus.INSPECTION: frozenset({OrderStatus.ITEMIZED}),
    OrderStatus.ITEMIZED: frozenset(
        {OrderStatus.PRICE_FINALIZED, OrderStatus.PRICE_ADJUSTMENT_REQUIRED}
    ),
    OrderStatus.PRICE_ADJUSTMENT_REQUIRED: frozenset(
        {OrderStatus.PRICE_FINALIZED, OrderStatus.CANCELLED}
    ),
    OrderStatus.PRICE_FINALIZED: frozenset({OrderStatus.PROCESSING}),
    OrderStatus.PROCESSING: frozenset({OrderStatus.QUALITY_CHECK}),
    # QUALITY_CHECK -> PROCESSING is the rework loop for a failed QC pass.
    OrderStatus.QUALITY_CHECK: frozenset({OrderStatus.READY_FOR_DELIVERY, OrderStatus.PROCESSING}),
    OrderStatus.READY_FOR_DELIVERY: frozenset({OrderStatus.DELIVERY_ASSIGNED}),
    OrderStatus.DELIVERY_ASSIGNED: frozenset(
        {OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERY_FAILED}
    ),
    OrderStatus.DELIVERY_FAILED: frozenset(
        {OrderStatus.DELIVERY_ASSIGNED, OrderStatus.RESCHEDULED}
    ),
    OrderStatus.OUT_FOR_DELIVERY: frozenset({OrderStatus.DELIVERED, OrderStatus.DELIVERY_FAILED}),
    OrderStatus.DELIVERED: frozenset({OrderStatus.COMPLETED}),
    OrderStatus.COMPLETED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}

# Once physical pickup has actually started (PICKUP_IN_PROGRESS or
# later), cancellation is no longer offered through this generic
# mechanism -- by then the customer/staff have to route through a
# different domain concept (a refund/rework flow, not implemented until
# later phases), not a plain status flip.
_CUSTOMER_ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.DRAFT: frozenset({OrderStatus.PENDING_PAYMENT, OrderStatus.CANCELLED}),
    OrderStatus.PENDING_PAYMENT: frozenset({OrderStatus.CANCELLED}),
    OrderStatus.PAYMENT_FAILED: frozenset({OrderStatus.CANCELLED}),
    OrderStatus.CONFIRMED: frozenset({OrderStatus.CANCELLED}),
    OrderStatus.PICKUP_SCHEDULED: frozenset({OrderStatus.CANCELLED}),
    OrderStatus.RESCHEDULED: frozenset({OrderStatus.CANCELLED}),
    OrderStatus.PICKUP_ASSIGNED: frozenset({OrderStatus.CANCELLED}),
    OrderStatus.PRICE_ADJUSTMENT_REQUIRED: frozenset({OrderStatus.CANCELLED}),
}


class OrderStateService:
    def __init__(self, session: AsyncSession) -> None:
        self._orders = OrderRepository(session)
        self._history = OrderStatusHistoryRepository(session)

    async def get_history(self, order_id: uuid.UUID) -> list[OrderStatusHistory]:
        return await self._history.list_for_order(order_id)

    async def transition(
        self,
        order_id: uuid.UUID,
        to_status: OrderStatus,
        *,
        requester_user_id: uuid.UUID,
        requester_is_staff: bool,
        changed_by_role: str | None = None,
        reason: str | None = None,
        extra_data: dict | None = None,
    ) -> Order:
        order = await self._orders.get_by_id(order_id)
        if order is None or (not requester_is_staff and order.customer_id != requester_user_id):
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)

        current_status = OrderStatus(order.status)
        if to_status not in ALLOWED_TRANSITIONS.get(current_status, frozenset()):
            raise BusinessRuleException(
                error_messages.INVALID_ORDER_STATE_TRANSITION,
                error_codes.INVALID_ORDER_STATE_TRANSITION,
            )

        if not requester_is_staff:
            customer_allowed = _CUSTOMER_ALLOWED_TRANSITIONS.get(current_status, frozenset())
            if to_status not in customer_allowed:
                raise ForbiddenException(error_messages.FORBIDDEN, error_codes.FORBIDDEN)

        transitioned = await self._orders.try_transition(
            order_id, current_status.value, to_status.value
        )
        if not transitioned:
            raise ConflictException(
                error_messages.ORDER_STATE_CONFLICT, error_codes.ORDER_STATE_CONFLICT
            )
        order.status = to_status.value

        history_entry = OrderStatusHistory(
            order_id=order_id,
            from_status=current_status.value,
            to_status=to_status.value,
            changed_by_user_id=requester_user_id,
            changed_by_role=changed_by_role,
            reason=reason,
            extra_data=extra_data,
        )
        await self._history.create(history_entry)
        return order
