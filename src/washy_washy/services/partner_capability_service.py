"""Partner capability business logic: which services a partner can
perform. Capability only — capacity/scheduling is Phase 7's job.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConflictException, NotFoundException
from core.models.service import Service
from washy_washy.constants import error_codes, error_messages
from washy_washy.repositories.partner_capability_repo import PartnerCapabilityRepository
from washy_washy.repositories.partner_profile_repo import PartnerProfileRepository
from washy_washy.repositories.service_repo import ServiceRepository


class PartnerCapabilityService:
    def __init__(self, session: AsyncSession) -> None:
        self._capabilities = PartnerCapabilityRepository(session)
        self._partner_profiles = PartnerProfileRepository(session)
        self._services = ServiceRepository(session)

    async def grant_capability(self, partner_profile_id: uuid.UUID, service_id: uuid.UUID) -> None:
        await self._require_partner_profile(partner_profile_id)
        await self._require_service(service_id)
        if await self._capabilities.has_capability(partner_profile_id, service_id):
            raise ConflictException(
                error_messages.PARTNER_CAPABILITY_ALREADY_EXISTS,
                error_codes.PARTNER_CAPABILITY_ALREADY_EXISTS,
            )
        await self._capabilities.grant(partner_profile_id, service_id)

    async def revoke_capability(self, partner_profile_id: uuid.UUID, service_id: uuid.UUID) -> None:
        await self._capabilities.revoke(partner_profile_id, service_id)

    async def has_capability(self, partner_profile_id: uuid.UUID, service_id: uuid.UUID) -> bool:
        return await self._capabilities.has_capability(partner_profile_id, service_id)

    async def list_services_for_partner(self, partner_profile_id: uuid.UUID) -> list[Service]:
        return await self._capabilities.list_services_for_partner(partner_profile_id)

    async def _require_partner_profile(self, partner_profile_id: uuid.UUID) -> None:
        if await self._partner_profiles.get_by_id(partner_profile_id) is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)

    async def _require_service(self, service_id: uuid.UUID) -> None:
        if await self._services.get_by_id(service_id) is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
