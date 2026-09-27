"""Partner facility business logic: the physical sites a partner
operates from, and the `PartnerProfile <-> ServiceArea` link Phase 7
deferred to this phase.
"""

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConflictException, NotFoundException
from core.models.partner_facility import PartnerFacility
from washy_washy.constants import error_codes, error_messages
from washy_washy.repositories.partner_facility_repo import PartnerFacilityRepository
from washy_washy.repositories.partner_profile_repo import PartnerProfileRepository
from washy_washy.repositories.service_area_repo import ServiceAreaRepository


class PartnerFacilityService:
    def __init__(self, session: AsyncSession) -> None:
        self._facilities = PartnerFacilityRepository(session)
        self._partner_profiles = PartnerProfileRepository(session)
        self._service_areas = ServiceAreaRepository(session)

    async def create_facility(
        self,
        partner_profile_id: uuid.UUID,
        service_area_id: uuid.UUID,
        *,
        name: str,
        address_line_1: str,
        city: str,
        state: str,
        postal_code: str,
        country: str,
        address_line_2: str | None = None,
        daily_capacity: Decimal | None = None,
    ) -> PartnerFacility:
        if await self._partner_profiles.get_by_id(partner_profile_id) is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        if await self._service_areas.get_by_id(service_area_id) is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        if await self._facilities.get_by_name(partner_profile_id, name) is not None:
            raise ConflictException(
                error_messages.FACILITY_NAME_ALREADY_EXISTS,
                error_codes.FACILITY_NAME_ALREADY_EXISTS,
            )

        facility = PartnerFacility(
            partner_profile_id=partner_profile_id,
            service_area_id=service_area_id,
            name=name,
            address_line_1=address_line_1,
            address_line_2=address_line_2,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
            daily_capacity=daily_capacity,
        )
        return await self._facilities.create(facility)

    async def get_facility(self, facility_id: uuid.UUID) -> PartnerFacility:
        facility = await self._facilities.get_by_id(facility_id)
        if facility is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        return facility

    async def list_facilities(self, *, include_inactive: bool = False) -> list[PartnerFacility]:
        return await self._facilities.list_all(active_only=not include_inactive)

    async def list_facilities_for_partner(
        self, partner_profile_id: uuid.UUID, *, include_inactive: bool = False
    ) -> list[PartnerFacility]:
        return await self._facilities.list_for_partner(
            partner_profile_id, active_only=not include_inactive
        )

    async def set_active(self, facility_id: uuid.UUID, is_active: bool) -> PartnerFacility:
        facility = await self.get_facility(facility_id)
        facility.is_active = is_active
        return await self._facilities.update(facility)
