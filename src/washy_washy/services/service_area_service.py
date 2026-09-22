"""Service area business logic: creation (with its initial postal
codes) and the "is this postal code serviceable?" check.

No direct User <-> ServiceArea relationship exists (see
``core/models/service_area.py``'s module docstring and FLOW.md §4.6's
design note) — serviceability is a property of a *location* (a postal
code, typically reached via an ``Address``), not of a user. A customer
can have addresses in several service areas at once; nothing about a
user itself is "in" an area.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConflictException
from core.models.service_area import ServiceArea
from washy_washy.constants import error_codes, error_messages
from washy_washy.repositories.service_area_repo import ServiceAreaRepository


class ServiceAreaService:
    def __init__(self, session: AsyncSession) -> None:
        self._service_areas = ServiceAreaRepository(session)

    async def list_active(self) -> list[ServiceArea]:
        return await self._service_areas.list_active()

    async def create_service_area(self, name: str, postal_codes: list[str]) -> ServiceArea:
        if await self._service_areas.get_by_name(name) is not None:
            raise ConflictException(
                error_messages.SERVICE_AREA_NAME_ALREADY_EXISTS,
                error_codes.SERVICE_AREA_NAME_ALREADY_EXISTS,
            )
        service_area = await self._service_areas.create(ServiceArea(name=name))
        for postal_code in postal_codes:
            await self._service_areas.add_postal_code(service_area.id, postal_code)
        return service_area

    async def is_postal_code_serviceable(self, postal_code: str) -> bool:
        return await self.get_service_area_for_postal_code(postal_code) is not None

    async def get_service_area_for_postal_code(self, postal_code: str) -> ServiceArea | None:
        return await self._service_areas.get_by_postal_code(postal_code)

    async def get_by_id(self, service_area_id: uuid.UUID) -> ServiceArea | None:
        return await self._service_areas.get_by_id(service_area_id)
