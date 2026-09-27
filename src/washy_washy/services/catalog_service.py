"""Catalog business logic: Service/Material CRUD (+ activate/deactivate)
and the service/material compatibility + care-requirement rows between
them.

Deliberately independent of pricing (Phase 6) and availability/capacity
(Phase 7) — nothing here knows about cost or scheduling.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConflictException, NotFoundException
from core.models.material import Material
from core.models.service import Service
from core.models.service_material import ServiceMaterial
from washy_washy.constants import error_codes, error_messages
from washy_washy.repositories.material_repo import MaterialRepository
from washy_washy.repositories.service_material_repo import ServiceMaterialRepository
from washy_washy.repositories.service_repo import ServiceRepository


class CatalogService:
    def __init__(self, session: AsyncSession) -> None:
        self._services = ServiceRepository(session)
        self._materials = MaterialRepository(session)
        self._service_materials = ServiceMaterialRepository(session)

    # -- Services ----------------------------------------------------

    async def create_service(self, name: str, description: str | None = None) -> Service:
        if await self._services.get_by_name(name) is not None:
            raise ConflictException(
                error_messages.SERVICE_NAME_ALREADY_EXISTS,
                error_codes.SERVICE_NAME_ALREADY_EXISTS,
            )
        return await self._services.create(Service(name=name, description=description))

    async def get_service(self, service_id: uuid.UUID) -> Service:
        service = await self._services.get_by_id(service_id)
        if service is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        return service

    async def list_services(self, *, include_inactive: bool = False) -> list[Service]:
        return await self._services.list_all(include_inactive=include_inactive)

    async def set_service_active(self, service_id: uuid.UUID, is_active: bool) -> Service:
        service = await self.get_service(service_id)
        service.is_active = is_active
        return await self._services.update(service)

    # -- Materials -----------------------------------------------------

    async def create_material(self, name: str, description: str | None = None) -> Material:
        if await self._materials.get_by_name(name) is not None:
            raise ConflictException(
                error_messages.MATERIAL_NAME_ALREADY_EXISTS,
                error_codes.MATERIAL_NAME_ALREADY_EXISTS,
            )
        return await self._materials.create(Material(name=name, description=description))

    async def get_material(self, material_id: uuid.UUID) -> Material:
        material = await self._materials.get_by_id(material_id)
        if material is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        return material

    async def list_materials(self, *, include_inactive: bool = False) -> list[Material]:
        return await self._materials.list_all(include_inactive=include_inactive)

    async def set_material_active(self, material_id: uuid.UUID, is_active: bool) -> Material:
        material = await self.get_material(material_id)
        material.is_active = is_active
        return await self._materials.update(material)

    # -- Compatibility -------------------------------------------------

    async def set_compatibility(
        self,
        service_id: uuid.UUID,
        material_id: uuid.UUID,
        *,
        care_instructions: str | None = None,
        max_temperature_celsius: int | None = None,
    ) -> ServiceMaterial:
        """Creates the (service, material) compatibility row, or updates
        the existing one's care metadata in place if it already exists
        — this is not "grant vs. reject a duplicate" like a role
        assignment; the care requirements genuinely can change.
        """
        await self.get_service(service_id)
        await self.get_material(material_id)

        existing = await self._service_materials.get(service_id, material_id)
        if existing is not None:
            existing.care_instructions = care_instructions
            existing.max_temperature_celsius = max_temperature_celsius
            return await self._service_materials.update(existing)

        service_material = ServiceMaterial(
            service_id=service_id,
            material_id=material_id,
            care_instructions=care_instructions,
            max_temperature_celsius=max_temperature_celsius,
        )
        return await self._service_materials.create(service_material)

    async def remove_compatibility(self, service_id: uuid.UUID, material_id: uuid.UUID) -> None:
        existing = await self._service_materials.get(service_id, material_id)
        if existing is not None:
            await self._service_materials.delete(existing)

    async def is_compatible(self, service_id: uuid.UUID, material_id: uuid.UUID) -> bool:
        return await self._service_materials.get(service_id, material_id) is not None

    async def get_compatible_materials(self, service_id: uuid.UUID) -> list[Material]:
        return await self._service_materials.list_materials_for_service(service_id)

    async def get_compatible_services(self, material_id: uuid.UUID) -> list[Service]:
        return await self._service_materials.list_services_for_material(material_id)
