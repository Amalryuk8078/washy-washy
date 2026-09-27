"""Catalog endpoints: services, materials, and their compatibility.

Reading is open to any authenticated caller; writes (create, activate/
deactivate, set/remove compatibility) require the `ADMIN` role.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.models.role import RoleName
from washy_washy.api.v1.controllers import catalog as catalog_controller
from washy_washy.dependencies.auth import get_current_user
from washy_washy.dependencies.rbac import require_role
from washy_washy.schemas.catalog import (
    CreateMaterialRequest,
    CreateServiceRequest,
    SetCompatibilityRequest,
    UpdateActiveRequest,
)
from washy_washy.schemas.common import SuccessResponse

router = APIRouter(tags=["catalog"], dependencies=[Depends(get_current_user)])
_admin_only = Depends(require_role(RoleName.ADMIN.value))


@router.get("/services", response_model=SuccessResponse)
async def list_services(db_session: AsyncSession = Depends(get_db_session)) -> SuccessResponse:
    services = await catalog_controller.list_services(db_session)
    return SuccessResponse(message="Services", data=services)


@router.post(
    "/services",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_admin_only],
)
async def create_service(
    request: CreateServiceRequest, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    service = await catalog_controller.create_service(request, db_session)
    return SuccessResponse(message="Service created", data=service)


@router.get("/services/{service_id}", response_model=SuccessResponse)
async def get_service(
    service_id: uuid.UUID, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    service = await catalog_controller.get_service(service_id, db_session)
    return SuccessResponse(message="Service", data=service)


@router.patch("/services/{service_id}", response_model=SuccessResponse, dependencies=[_admin_only])
async def update_service_active(
    service_id: uuid.UUID,
    request: UpdateActiveRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    service = await catalog_controller.set_service_active(service_id, request.is_active, db_session)
    return SuccessResponse(message="Service updated", data=service)


@router.get("/services/{service_id}/materials", response_model=SuccessResponse)
async def get_compatible_materials(
    service_id: uuid.UUID, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    materials = await catalog_controller.get_compatible_materials(service_id, db_session)
    return SuccessResponse(message="Compatible materials", data=materials)


@router.post(
    "/services/{service_id}/materials",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_admin_only],
)
async def set_compatibility(
    service_id: uuid.UUID,
    request: SetCompatibilityRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    compatibility = await catalog_controller.set_compatibility(service_id, request, db_session)
    return SuccessResponse(message="Compatibility set", data=compatibility)


@router.delete(
    "/services/{service_id}/materials/{material_id}",
    response_model=SuccessResponse,
    dependencies=[_admin_only],
)
async def remove_compatibility(
    service_id: uuid.UUID,
    material_id: uuid.UUID,
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    await catalog_controller.remove_compatibility(service_id, material_id, db_session)
    return SuccessResponse(message="Compatibility removed")


@router.get("/materials", response_model=SuccessResponse)
async def list_materials(db_session: AsyncSession = Depends(get_db_session)) -> SuccessResponse:
    materials = await catalog_controller.list_materials(db_session)
    return SuccessResponse(message="Materials", data=materials)


@router.post(
    "/materials",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_admin_only],
)
async def create_material(
    request: CreateMaterialRequest, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    material = await catalog_controller.create_material(request, db_session)
    return SuccessResponse(message="Material created", data=material)


@router.get("/materials/{material_id}", response_model=SuccessResponse)
async def get_material(
    material_id: uuid.UUID, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    material = await catalog_controller.get_material(material_id, db_session)
    return SuccessResponse(message="Material", data=material)


@router.patch(
    "/materials/{material_id}", response_model=SuccessResponse, dependencies=[_admin_only]
)
async def update_material_active(
    material_id: uuid.UUID,
    request: UpdateActiveRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    material = await catalog_controller.set_material_active(
        material_id, request.is_active, db_session
    )
    return SuccessResponse(message="Material updated", data=material)


@router.get("/materials/{material_id}/services", response_model=SuccessResponse)
async def get_compatible_services(
    material_id: uuid.UUID, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    services = await catalog_controller.get_compatible_services(material_id, db_session)
    return SuccessResponse(message="Compatible services", data=services)
