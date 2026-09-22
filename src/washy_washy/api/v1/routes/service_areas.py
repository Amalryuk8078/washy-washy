"""Service area endpoints.

``POST /service-areas`` is the first route in this project to actually
enforce Phase 3's RBAC mechanism — everything before this phase built
``require_role``/``require_permission`` without a consumer.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.models.role import RoleName
from core.models.user import User
from washy_washy.api.v1.controllers import service_areas as service_areas_controller
from washy_washy.dependencies.auth import get_current_user
from washy_washy.dependencies.rbac import require_role
from washy_washy.schemas.common import SuccessResponse
from washy_washy.schemas.service_area import CreateServiceAreaRequest

router = APIRouter(prefix="/service-areas", tags=["service-areas"])


@router.get("", response_model=SuccessResponse)
async def list_service_areas(
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    areas = await service_areas_controller.list_service_areas(db_session)
    return SuccessResponse(message="Service areas", data=areas)


@router.post(
    "",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(RoleName.ADMIN.value))],
)
async def create_service_area(
    request: CreateServiceAreaRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    area = await service_areas_controller.create_service_area(request, db_session)
    return SuccessResponse(message="Service area created", data=area)
