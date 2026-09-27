"""Request-level orchestration for the catalog endpoints."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from washy_washy.schemas.catalog import (
    CreateMaterialRequest,
    CreateServiceRequest,
    MaterialResponse,
    ServiceMaterialResponse,
    ServiceResponse,
    SetCompatibilityRequest,
)
from washy_washy.services.catalog_service import CatalogService


async def list_services(db_session: AsyncSession) -> list[ServiceResponse]:
    service = CatalogService(db_session)
    services = await service.list_services()
    return [ServiceResponse.model_validate(s) for s in services]


async def get_service(service_id: uuid.UUID, db_session: AsyncSession) -> ServiceResponse:
    service = CatalogService(db_session)
    result = await service.get_service(service_id)
    return ServiceResponse.model_validate(result)


async def create_service(
    request: CreateServiceRequest, db_session: AsyncSession
) -> ServiceResponse:
    service = CatalogService(db_session)
    result = await service.create_service(request.name, request.description)
    await db_session.commit()
    return ServiceResponse.model_validate(result)


async def set_service_active(
    service_id: uuid.UUID, is_active: bool, db_session: AsyncSession
) -> ServiceResponse:
    service = CatalogService(db_session)
    result = await service.set_service_active(service_id, is_active)
    await db_session.commit()
    return ServiceResponse.model_validate(result)


async def list_materials(db_session: AsyncSession) -> list[MaterialResponse]:
    service = CatalogService(db_session)
    materials = await service.list_materials()
    return [MaterialResponse.model_validate(m) for m in materials]


async def get_material(material_id: uuid.UUID, db_session: AsyncSession) -> MaterialResponse:
    service = CatalogService(db_session)
    result = await service.get_material(material_id)
    return MaterialResponse.model_validate(result)


async def create_material(
    request: CreateMaterialRequest, db_session: AsyncSession
) -> MaterialResponse:
    service = CatalogService(db_session)
    result = await service.create_material(request.name, request.description)
    await db_session.commit()
    return MaterialResponse.model_validate(result)


async def set_material_active(
    material_id: uuid.UUID, is_active: bool, db_session: AsyncSession
) -> MaterialResponse:
    service = CatalogService(db_session)
    result = await service.set_material_active(material_id, is_active)
    await db_session.commit()
    return MaterialResponse.model_validate(result)


async def get_compatible_materials(
    service_id: uuid.UUID, db_session: AsyncSession
) -> list[MaterialResponse]:
    service = CatalogService(db_session)
    materials = await service.get_compatible_materials(service_id)
    return [MaterialResponse.model_validate(m) for m in materials]


async def get_compatible_services(
    material_id: uuid.UUID, db_session: AsyncSession
) -> list[ServiceResponse]:
    service = CatalogService(db_session)
    services = await service.get_compatible_services(material_id)
    return [ServiceResponse.model_validate(s) for s in services]


async def set_compatibility(
    service_id: uuid.UUID, request: SetCompatibilityRequest, db_session: AsyncSession
) -> ServiceMaterialResponse:
    service = CatalogService(db_session)
    result = await service.set_compatibility(
        service_id,
        request.material_id,
        care_instructions=request.care_instructions,
        max_temperature_celsius=request.max_temperature_celsius,
        care_adjustment=request.care_adjustment,
    )
    await db_session.commit()
    return ServiceMaterialResponse.model_validate(result)


async def remove_compatibility(
    service_id: uuid.UUID, material_id: uuid.UUID, db_session: AsyncSession
) -> None:
    service = CatalogService(db_session)
    await service.remove_compatibility(service_id, material_id)
    await db_session.commit()
