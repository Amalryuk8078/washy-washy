"""Order endpoints: creation, ownership-scoped queries, and the state
machine (scheduling, itemization, price finalization, and generic
transitions).

Creating an order and viewing/listing/scheduling/transitioning your own
order only require authentication -- ownership and the customer/staff
transition split are enforced in ``OrderStateService``/``OrderService``,
not here (see their module docstrings). Itemizing an item and
finalizing a price are staff-only (``ADMIN``/``SUPERVISOR``/
``LAUNDRY_PARTNER``): a customer never verifies their own declared
material/quantity.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.models.role import RoleName
from core.models.user import User
from washy_washy.api.v1.controllers import orders as orders_controller
from washy_washy.dependencies.auth import get_current_user
from washy_washy.dependencies.rbac import require_any_role
from washy_washy.schemas.common import SuccessResponse
from washy_washy.schemas.orders import (
    CreateOrderRequest,
    FinalizePriceRequest,
    ItemizeOrderItemRequest,
    SchedulePickupRequest,
    TransitionOrderRequest,
)

router = APIRouter(tags=["orders"], dependencies=[Depends(get_current_user)])
_staff_only = Depends(
    require_any_role(
        RoleName.ADMIN.value, RoleName.SUPERVISOR.value, RoleName.LAUNDRY_PARTNER.value
    )
)


@router.post("/orders", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    request: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    order = await orders_controller.create_order(current_user, request, db_session)
    return SuccessResponse(message="Order created", data=order)


@router.get("/orders", response_model=SuccessResponse)
async def list_own_orders(
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    orders = await orders_controller.list_own_orders(current_user, db_session)
    return SuccessResponse(message="Orders", data=orders)


@router.get("/orders/{order_id}", response_model=SuccessResponse)
async def get_order(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    order = await orders_controller.get_order(order_id, current_user, db_session)
    return SuccessResponse(message="Order", data=order)


@router.get("/orders/{order_id}/history", response_model=SuccessResponse)
async def get_order_history(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    history = await orders_controller.get_order_history(order_id, current_user, db_session)
    return SuccessResponse(message="Order status history", data=history)


@router.post("/orders/{order_id}/transition", response_model=SuccessResponse)
async def transition_order(
    order_id: uuid.UUID,
    request: TransitionOrderRequest,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    order = await orders_controller.transition_order(order_id, current_user, request, db_session)
    return SuccessResponse(message="Order status updated", data=order)


@router.post("/orders/{order_id}/schedule-pickup", response_model=SuccessResponse)
async def schedule_pickup(
    order_id: uuid.UUID,
    request: SchedulePickupRequest,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    order = await orders_controller.schedule_pickup(order_id, current_user, request, db_session)
    return SuccessResponse(message="Pickup scheduled", data=order)


@router.post(
    "/orders/{order_id}/items/{item_id}/itemize",
    response_model=SuccessResponse,
    dependencies=[_staff_only],
)
async def itemize_order_item(
    order_id: uuid.UUID,
    item_id: uuid.UUID,
    request: ItemizeOrderItemRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    item = await orders_controller.itemize_order_item(order_id, item_id, request, db_session)
    return SuccessResponse(message="Order item itemized", data=item)


@router.post(
    "/orders/{order_id}/finalize-price",
    response_model=SuccessResponse,
    dependencies=[_staff_only],
)
async def finalize_price(
    order_id: uuid.UUID,
    request: FinalizePriceRequest,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    order = await orders_controller.finalize_price(order_id, current_user, request, db_session)
    return SuccessResponse(message="Price finalized", data=order)
