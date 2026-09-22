"""Request-level orchestration for service area endpoints."""

from sqlalchemy.ext.asyncio import AsyncSession

from washy_washy.schemas.service_area import CreateServiceAreaRequest, ServiceAreaResponse
from washy_washy.services.service_area_service import ServiceAreaService


async def list_service_areas(db_session: AsyncSession) -> list[ServiceAreaResponse]:
    service = ServiceAreaService(db_session)
    areas = await service.list_active()
    return [ServiceAreaResponse.model_validate(area) for area in areas]


async def create_service_area(
    request: CreateServiceAreaRequest, db_session: AsyncSession
) -> ServiceAreaResponse:
    service = ServiceAreaService(db_session)
    area = await service.create_service_area(request.name, request.postal_codes)
    await db_session.commit()
    return ServiceAreaResponse.model_validate(area)
