"""Availability endpoints: operating hours, partner availability,
pickup/delivery slots, and booking/cancelling a reservation.

Reading and booking are open to any authenticated caller (a customer
booking their own pickup); defining operating hours/partner
availability/slots requires `ADMIN`. Cancelling a reservation only
requires the caller to own it (enforced in the service layer, not here).
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.models.role import RoleName
from core.models.user import User
from washy_washy.api.v1.controllers import availability as availability_controller
from washy_washy.dependencies.auth import get_current_user
from washy_washy.dependencies.rbac import require_role
from washy_washy.schemas.availability import (
    BookSlotRequest,
    CreateSlotRequest,
    SetOperatingHoursRequest,
    SetPartnerAvailabilityRequest,
)
from washy_washy.schemas.common import SuccessResponse

router = APIRouter(tags=["availability"], dependencies=[Depends(get_current_user)])
_admin_only = Depends(require_role(RoleName.ADMIN.value))


@router.get("/service-areas/{service_area_id}/operating-hours", response_model=SuccessResponse)
async def get_operating_hours(
    service_area_id: uuid.UUID, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    hours = await availability_controller.get_operating_hours(service_area_id, db_session)
    return SuccessResponse(message="Operating hours", data=hours)


@router.post(
    "/service-areas/{service_area_id}/operating-hours",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_admin_only],
)
async def set_operating_hours(
    service_area_id: uuid.UUID,
    request: SetOperatingHoursRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    hours = await availability_controller.set_operating_hours(service_area_id, request, db_session)
    return SuccessResponse(message="Operating hours set", data=hours)


@router.get("/partners/{partner_profile_id}/availability", response_model=SuccessResponse)
async def get_partner_availability(
    partner_profile_id: uuid.UUID, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    availability = await availability_controller.get_partner_availability(
        partner_profile_id, db_session
    )
    return SuccessResponse(message="Partner availability", data=availability)


@router.post(
    "/partners/{partner_profile_id}/availability",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_admin_only],
)
async def set_partner_availability(
    partner_profile_id: uuid.UUID,
    request: SetPartnerAvailabilityRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    availability = await availability_controller.set_partner_availability(
        partner_profile_id, request, db_session
    )
    return SuccessResponse(message="Partner availability set", data=availability)


@router.get("/service-areas/{service_area_id}/pickup-slots", response_model=SuccessResponse)
async def list_pickup_slots(
    service_area_id: uuid.UUID, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    slots = await availability_controller.list_pickup_slots(service_area_id, db_session)
    return SuccessResponse(message="Pickup slots", data=slots)


@router.post(
    "/service-areas/{service_area_id}/pickup-slots",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_admin_only],
)
async def create_pickup_slot(
    service_area_id: uuid.UUID,
    request: CreateSlotRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    slot = await availability_controller.create_pickup_slot(service_area_id, request, db_session)
    return SuccessResponse(message="Pickup slot created", data=slot)


@router.get("/service-areas/{service_area_id}/delivery-slots", response_model=SuccessResponse)
async def list_delivery_slots(
    service_area_id: uuid.UUID, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    slots = await availability_controller.list_delivery_slots(service_area_id, db_session)
    return SuccessResponse(message="Delivery slots", data=slots)


@router.post(
    "/service-areas/{service_area_id}/delivery-slots",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_admin_only],
)
async def create_delivery_slot(
    service_area_id: uuid.UUID,
    request: CreateSlotRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    slot = await availability_controller.create_delivery_slot(service_area_id, request, db_session)
    return SuccessResponse(message="Delivery slot created", data=slot)


@router.post(
    "/pickup-slots/{slot_id}/reservations",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
)
async def book_pickup_slot(
    slot_id: uuid.UUID,
    request: BookSlotRequest,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    reservation = await availability_controller.book_pickup_slot(
        slot_id, current_user.id, request, db_session
    )
    return SuccessResponse(message="Pickup slot booked", data=reservation)


@router.delete(
    "/pickup-slots/reservations/{reservation_id}",
    response_model=SuccessResponse,
)
async def cancel_pickup_reservation(
    reservation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    await availability_controller.cancel_pickup_reservation(
        reservation_id, current_user.id, db_session
    )
    return SuccessResponse(message="Pickup reservation cancelled")


@router.post(
    "/delivery-slots/{slot_id}/reservations",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
)
async def book_delivery_slot(
    slot_id: uuid.UUID,
    request: BookSlotRequest,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    reservation = await availability_controller.book_delivery_slot(
        slot_id, current_user.id, request, db_session
    )
    return SuccessResponse(message="Delivery slot booked", data=reservation)


@router.delete(
    "/delivery-slots/reservations/{reservation_id}",
    response_model=SuccessResponse,
)
async def cancel_delivery_reservation(
    reservation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    await availability_controller.cancel_delivery_reservation(
        reservation_id, current_user.id, db_session
    )
    return SuccessResponse(message="Delivery reservation cancelled")
