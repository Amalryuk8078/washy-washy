from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.models.user import User
from washy_washy.api.v1.controllers import customers as customers_controller
from washy_washy.dependencies.auth import get_current_user
from washy_washy.schemas.common import SuccessResponse
from washy_washy.schemas.profile import CreateCustomerProfileRequest

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("/me", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
async def create_my_profile(
    request: CreateCustomerProfileRequest,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    profile = await customers_controller.create_my_profile(current_user.id, request, db_session)
    return SuccessResponse(message="Customer profile created", data=profile)


@router.get("/me", response_model=SuccessResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    profile = await customers_controller.get_my_profile(current_user.id, db_session)
    return SuccessResponse(message="Customer profile", data=profile)
