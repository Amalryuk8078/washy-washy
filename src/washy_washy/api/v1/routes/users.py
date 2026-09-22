from fastapi import APIRouter, Depends

from core.models.user import User
from washy_washy.api.v1.controllers import users as users_controller
from washy_washy.dependencies.auth import get_current_user
from washy_washy.schemas.common import SuccessResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=SuccessResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> SuccessResponse:
    user = await users_controller.get_me(current_user)
    return SuccessResponse(message="Current user", data=user)
