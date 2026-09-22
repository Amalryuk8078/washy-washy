from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from washy_washy.api.v1.controllers import health as health_controller
from washy_washy.schemas.common import SuccessResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=SuccessResponse)
async def health() -> SuccessResponse:
    data = await health_controller.get_liveness()
    return SuccessResponse(message="Washy Washy API is healthy", data=data)


@router.get("/live", response_model=SuccessResponse)
async def live() -> SuccessResponse:
    data = await health_controller.get_liveness()
    return SuccessResponse(message="Washy Washy API is live", data=data)


@router.get("/ready", response_model=SuccessResponse)
async def ready(db_session: AsyncSession = Depends(get_db_session)) -> SuccessResponse:
    data = await health_controller.get_readiness(db_session)
    return SuccessResponse(message="Washy Washy API readiness", data=data)
