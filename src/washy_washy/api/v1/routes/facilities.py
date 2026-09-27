"""Partner facility endpoints. Reading is open to any authenticated
caller (a customer or staff member looking up which facility handles
what); creating/activating a facility requires `ADMIN`.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.models.role import RoleName
from washy_washy.api.v1.controllers import facilities as facilities_controller
from washy_washy.dependencies.auth import get_current_user
from washy_washy.dependencies.rbac import require_role
from washy_washy.schemas.common import SuccessResponse
from washy_washy.schemas.facilities import CreateFacilityRequest, SetFacilityActiveRequest

router = APIRouter(tags=["partner-facilities"], dependencies=[Depends(get_current_user)])
_admin_only = Depends(require_role(RoleName.ADMIN.value))


@router.post(
    "/partners/{partner_profile_id}/facilities",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_admin_only],
)
async def create_facility(
    partner_profile_id: uuid.UUID,
    request: CreateFacilityRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    facility = await facilities_controller.create_facility(partner_profile_id, request, db_session)
    return SuccessResponse(message="Facility created", data=facility)


@router.get("/partners/{partner_profile_id}/facilities", response_model=SuccessResponse)
async def list_facilities_for_partner(
    partner_profile_id: uuid.UUID, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    facilities = await facilities_controller.list_facilities_for_partner(
        partner_profile_id, db_session
    )
    return SuccessResponse(message="Partner facilities", data=facilities)


@router.get("/partner-facilities", response_model=SuccessResponse)
async def list_facilities(db_session: AsyncSession = Depends(get_db_session)) -> SuccessResponse:
    facilities = await facilities_controller.list_facilities(db_session)
    return SuccessResponse(message="Facilities", data=facilities)


@router.get("/partner-facilities/{facility_id}", response_model=SuccessResponse)
async def get_facility(
    facility_id: uuid.UUID, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    facility = await facilities_controller.get_facility(facility_id, db_session)
    return SuccessResponse(message="Facility", data=facility)


@router.patch(
    "/partner-facilities/{facility_id}",
    response_model=SuccessResponse,
    dependencies=[_admin_only],
)
async def set_facility_active(
    facility_id: uuid.UUID,
    request: SetFacilityActiveRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    facility = await facilities_controller.set_facility_active(
        facility_id, request.is_active, db_session
    )
    return SuccessResponse(message="Facility updated", data=facility)
