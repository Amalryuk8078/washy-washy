"""Request-level orchestration for the current-user endpoint."""

from core.models.user import User
from washy_washy.schemas.auth import UserResponse


async def get_me(current_user: User) -> UserResponse:
    return UserResponse.model_validate(current_user)
