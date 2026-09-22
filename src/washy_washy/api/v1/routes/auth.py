from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from washy_washy.api.v1.controllers import auth as auth_controller
from washy_washy.schemas.auth import LoginRequest, RefreshTokenRequest, RegisterRequest
from washy_washy.schemas.common import SuccessResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    user = await auth_controller.register(request, db_session)
    return SuccessResponse(message="Registration successful", data=user)


@router.post("/login", response_model=SuccessResponse)
async def login(
    request: LoginRequest, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    tokens = await auth_controller.login(request, db_session)
    return SuccessResponse(message="Login successful", data=tokens)


@router.post("/refresh", response_model=SuccessResponse)
async def refresh(
    request: RefreshTokenRequest, db_session: AsyncSession = Depends(get_db_session)
) -> SuccessResponse:
    access_token = await auth_controller.refresh(request.refresh_token, db_session)
    return SuccessResponse(message="Token refreshed", data={"access_token": access_token})
