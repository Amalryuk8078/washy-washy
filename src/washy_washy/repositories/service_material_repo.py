"""Persistence for :class:`core.models.service_material.ServiceMaterial`
— the service/material compatibility + care-requirement rows.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.material import Material
from core.models.service import Service
from core.models.service_material import ServiceMaterial


class ServiceMaterialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, service_id: uuid.UUID, material_id: uuid.UUID) -> ServiceMaterial | None:
        stmt = select(ServiceMaterial).where(
            ServiceMaterial.service_id == service_id,
            ServiceMaterial.material_id == material_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_materials_for_service(self, service_id: uuid.UUID) -> list[Material]:
        stmt = (
            select(Material)
            .join(ServiceMaterial, ServiceMaterial.material_id == Material.id)
            .where(ServiceMaterial.service_id == service_id)
            .order_by(Material.name)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_services_for_material(self, material_id: uuid.UUID) -> list[Service]:
        stmt = (
            select(Service)
            .join(ServiceMaterial, ServiceMaterial.service_id == Service.id)
            .where(ServiceMaterial.material_id == material_id)
            .order_by(Service.name)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, service_material: ServiceMaterial) -> ServiceMaterial:
        self._session.add(service_material)
        await self._session.flush()
        return service_material

    async def update(self, service_material: ServiceMaterial) -> ServiceMaterial:
        await self._session.flush()
        return service_material

    async def delete(self, service_material: ServiceMaterial) -> None:
        await self._session.delete(service_material)
        await self._session.flush()
