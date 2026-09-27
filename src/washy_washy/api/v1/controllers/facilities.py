"""Request-level orchestration for partner facility endpoints."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from washy_washy.schemas.facilities import CreateFacilityRequest, FacilityResponse
from washy_washy.services.facility_service import PartnerFacilityService


async def create_facility(
    partner_profile_id: uuid.UUID, request: CreateFacilityRequest, db_session: AsyncSession
) -> FacilityResponse:
    service = PartnerFacilityService(db_session)
    facility = await service.create_facility(
        partner_profile_id,
        request.service_area_id,
        name=request.name,
        address_line_1=request.address_line_1,
        address_line_2=request.address_line_2,
        city=request.city,
        state=request.state,
        postal_code=request.postal_code,
        country=request.country,
        daily_capacity=request.daily_capacity,
    )
    await db_session.commit()
    return FacilityResponse.model_validate(facility)


async def get_facility(facility_id: uuid.UUID, db_session: AsyncSession) -> FacilityResponse:
    service = PartnerFacilityService(db_session)
    facility = await service.get_facility(facility_id)
    return FacilityResponse.model_validate(facility)


async def list_facilities(db_session: AsyncSession) -> list[FacilityResponse]:
    service = PartnerFacilityService(db_session)
    facilities = await service.list_facilities()
    return [FacilityResponse.model_validate(f) for f in facilities]


async def list_facilities_for_partner(
    partner_profile_id: uuid.UUID, db_session: AsyncSession
) -> list[FacilityResponse]:
    service = PartnerFacilityService(db_session)
    facilities = await service.list_facilities_for_partner(partner_profile_id)
    return [FacilityResponse.model_validate(f) for f in facilities]


async def set_facility_active(
    facility_id: uuid.UUID, is_active: bool, db_session: AsyncSession
) -> FacilityResponse:
    service = PartnerFacilityService(db_session)
    facility = await service.set_active(facility_id, is_active)
    await db_session.commit()
    return FacilityResponse.model_validate(facility)
