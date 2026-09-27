"""Request-level orchestration for the order endpoints.

``_is_staff``/``_acting_role`` are the one place that resolves "is this
caller staff, and under which role are they acting" — every handler
below calls through them rather than re-querying RBAC itself.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.models.order import OrderStatus
from core.models.role import RoleName
from core.models.user import User
from washy_washy.schemas.orders import (
    AssignFacilityRequest,
    AssignOperatorRequest,
    CreateOrderRequest,
    FinalizePriceRequest,
    ItemizeOrderItemRequest,
    OrderAssignmentHistoryResponse,
    OrderItemResponse,
    OrderResponse,
    OrderStatusHistoryResponse,
    OrderWithItemsResponse,
    SchedulePickupRequest,
    TransitionOrderRequest,
)
from washy_washy.services.assignment_service import AssignmentService
from washy_washy.services.order_service import OrderItemInput, OrderService
from washy_washy.services.rbac_service import RBACService

_STAFF_ROLES = [RoleName.ADMIN.value, RoleName.SUPERVISOR.value, RoleName.LAUNDRY_PARTNER.value]


async def _is_staff(db_session: AsyncSession, user_id: uuid.UUID) -> bool:
    return await RBACService(db_session).has_any_role(user_id, _STAFF_ROLES)


async def _acting_role(db_session: AsyncSession, user_id: uuid.UUID) -> str | None:
    roles = await RBACService(db_session).get_user_roles(user_id)
    return roles[0].name if roles else None


async def create_order(
    current_user: User, request: CreateOrderRequest, db_session: AsyncSession
) -> OrderWithItemsResponse:
    service = OrderService(db_session)
    order = await service.create_order(
        current_user.id,
        pickup_address_id=request.pickup_address_id,
        delivery_address_id=request.delivery_address_id,
        items=[
            OrderItemInput(
                service_id=item.service_id,
                declared_material_id=item.declared_material_id,
                declared_quantity=item.declared_quantity,
                declared_weight_kg=item.declared_weight_kg,
            )
            for item in request.items
        ],
        rush_charge=request.rush_charge,
        delivery_charge=request.delivery_charge,
        tax=request.tax,
        discount=request.discount,
    )
    items = await service.list_items(order.id)
    await db_session.commit()
    return OrderWithItemsResponse.model_validate(
        {**OrderResponse.model_validate(order).model_dump(), "items": items}
    )


async def list_own_orders(current_user: User, db_session: AsyncSession) -> list[OrderResponse]:
    service = OrderService(db_session)
    orders = await service.list_own_orders(current_user.id)
    return [OrderResponse.model_validate(o) for o in orders]


async def get_order(
    order_id: uuid.UUID, current_user: User, db_session: AsyncSession
) -> OrderWithItemsResponse:
    service = OrderService(db_session)
    is_staff = await _is_staff(db_session, current_user.id)
    order = await service.get_order_for_viewer(order_id, current_user.id, is_staff=is_staff)
    items = await service.list_items(order.id)
    return OrderWithItemsResponse.model_validate(
        {**OrderResponse.model_validate(order).model_dump(), "items": items}
    )


async def get_order_history(
    order_id: uuid.UUID, current_user: User, db_session: AsyncSession
) -> list[OrderStatusHistoryResponse]:
    service = OrderService(db_session)
    is_staff = await _is_staff(db_session, current_user.id)
    await service.get_order_for_viewer(order_id, current_user.id, is_staff=is_staff)
    history = await service.get_history(order_id)
    return [OrderStatusHistoryResponse.model_validate(h) for h in history]


async def transition_order(
    order_id: uuid.UUID,
    current_user: User,
    request: TransitionOrderRequest,
    db_session: AsyncSession,
) -> OrderResponse:
    service = OrderService(db_session)
    is_staff = await _is_staff(db_session, current_user.id)
    role = await _acting_role(db_session, current_user.id)
    order = await service.transition(
        order_id,
        OrderStatus(request.to_status),
        requester_user_id=current_user.id,
        requester_is_staff=is_staff,
        changed_by_role=role,
        reason=request.reason,
    )
    await db_session.commit()
    return OrderResponse.model_validate(order)


async def schedule_pickup(
    order_id: uuid.UUID,
    current_user: User,
    request: SchedulePickupRequest,
    db_session: AsyncSession,
) -> OrderResponse:
    service = OrderService(db_session)
    is_staff = await _is_staff(db_session, current_user.id)
    role = await _acting_role(db_session, current_user.id)
    order = await service.schedule_pickup(
        order_id,
        current_user.id,
        requester_is_staff=is_staff,
        pickup_slot_id=request.pickup_slot_id,
        capacity_used=request.capacity_used,
        changed_by_role=role,
    )
    await db_session.commit()
    return OrderResponse.model_validate(order)


async def itemize_order_item(
    order_id: uuid.UUID,
    item_id: uuid.UUID,
    request: ItemizeOrderItemRequest,
    db_session: AsyncSession,
) -> OrderItemResponse:
    service = OrderService(db_session)
    item = await service.itemize_order_item(
        order_id,
        item_id,
        verified_material_id=request.verified_material_id,
        verified_quantity=request.verified_quantity,
        verified_weight_kg=request.verified_weight_kg,
        condition_notes=request.condition_notes,
        damage_reported=request.damage_reported,
    )
    await db_session.commit()
    return OrderItemResponse.model_validate(item)


async def finalize_price(
    order_id: uuid.UUID,
    current_user: User,
    request: FinalizePriceRequest,
    db_session: AsyncSession,
) -> OrderResponse:
    service = OrderService(db_session)
    is_staff = await _is_staff(db_session, current_user.id)
    role = await _acting_role(db_session, current_user.id)
    order = await service.finalize_pricing(
        order_id,
        current_user.id,
        requester_is_staff=is_staff,
        rush_charge=request.rush_charge,
        delivery_charge=request.delivery_charge,
        tax=request.tax,
        discount=request.discount,
        changed_by_role=role,
    )
    await db_session.commit()
    return OrderResponse.model_validate(order)


async def assign_facility(
    order_id: uuid.UUID,
    current_user: User,
    request: AssignFacilityRequest,
    db_session: AsyncSession,
) -> OrderResponse:
    service = AssignmentService(db_session)
    order = await service.assign_facility(
        order_id, request.facility_id, changed_by_user_id=current_user.id, reason=request.reason
    )
    await db_session.commit()
    return OrderResponse.model_validate(order)


async def assign_pickup_operator(
    order_id: uuid.UUID,
    current_user: User,
    request: AssignOperatorRequest,
    db_session: AsyncSession,
) -> OrderResponse:
    service = AssignmentService(db_session)
    order = await service.assign_pickup_operator(
        order_id,
        request.operator_user_id,
        changed_by_user_id=current_user.id,
        reason=request.reason,
    )
    await db_session.commit()
    return OrderResponse.model_validate(order)


async def assign_delivery_operator(
    order_id: uuid.UUID,
    current_user: User,
    request: AssignOperatorRequest,
    db_session: AsyncSession,
) -> OrderResponse:
    service = AssignmentService(db_session)
    order = await service.assign_delivery_operator(
        order_id,
        request.operator_user_id,
        changed_by_user_id=current_user.id,
        reason=request.reason,
    )
    await db_session.commit()
    return OrderResponse.model_validate(order)


async def get_assignment_history(
    order_id: uuid.UUID, current_user: User, db_session: AsyncSession
) -> list[OrderAssignmentHistoryResponse]:
    order_service = OrderService(db_session)
    is_staff = await _is_staff(db_session, current_user.id)
    await order_service.get_order_for_viewer(order_id, current_user.id, is_staff=is_staff)
    history = await AssignmentService(db_session).get_history(order_id)
    return [OrderAssignmentHistoryResponse.model_validate(h) for h in history]
