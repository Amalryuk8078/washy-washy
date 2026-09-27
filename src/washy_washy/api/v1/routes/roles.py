"""Admin-only role management endpoints.

Closes a gap Phase 3/4 explicitly deferred: those phases built RBAC
*enforcement* (`require_role`/`require_permission`) but no way to grant
roles except by calling `UserRoleRepository` directly (which is exactly
what every test suite did). Everything here requires the `ADMIN` role.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.models.role import RoleName
from core.models.user import User
from washy_washy.api.v1.controllers import roles as roles_controller
from washy_washy.dependencies.auth import get_current_user
from washy_washy.dependencies.rbac import require_role
from washy_washy.schemas.common import SuccessResponse
from washy_washy.schemas.role import GrantRoleRequest

router = APIRouter(tags=["roles"], dependencies=[Depends(require_role(RoleName.ADMIN.value))])


@router.get("/roles", response_model=SuccessResponse)
async def list_assignable_roles(
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    roles = await roles_controller.list_assignable_roles(db_session)
    return SuccessResponse(message="Assignable roles", data=roles)


@router.get("/users/{user_id}/roles", response_model=SuccessResponse)
async def get_user_roles(
    user_id: uuid.UUID,
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    roles = await roles_controller.get_user_roles(user_id, db_session)
    return SuccessResponse(message="User roles", data=roles)


@router.post(
    "/users/{user_id}/roles",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant_role(
    user_id: uuid.UUID,
    request: GrantRoleRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    roles = await roles_controller.grant_role(user_id, request, db_session)
    return SuccessResponse(message="Role granted", data=roles)


@router.delete("/users/{user_id}/roles/{role_name}", response_model=SuccessResponse)
async def revoke_role(
    user_id: uuid.UUID,
    role_name: str,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    roles = await roles_controller.revoke_role(user_id, role_name, current_user.id, db_session)
    return SuccessResponse(message="Role revoked", data=roles)
