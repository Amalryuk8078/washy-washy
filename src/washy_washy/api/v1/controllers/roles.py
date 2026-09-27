"""Request-level orchestration for the admin role-management endpoints."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from washy_washy.schemas.role import GrantRoleRequest, RoleResponse
from washy_washy.services.rbac_service import RBACService


async def list_assignable_roles(db_session: AsyncSession) -> list[RoleResponse]:
    service = RBACService(db_session)
    roles = await service.list_assignable_roles()
    return [RoleResponse.model_validate(role) for role in roles]


async def get_user_roles(user_id: uuid.UUID, db_session: AsyncSession) -> list[RoleResponse]:
    service = RBACService(db_session)
    await service.get_user(user_id)  # 404s if the user doesn't exist
    roles = await service.get_user_roles(user_id)
    return [RoleResponse.model_validate(role) for role in roles]


async def grant_role(
    user_id: uuid.UUID, request: GrantRoleRequest, db_session: AsyncSession
) -> list[RoleResponse]:
    service = RBACService(db_session)
    roles = await service.grant_role_by_name(user_id, request.role_name)
    await db_session.commit()
    return [RoleResponse.model_validate(role) for role in roles]


async def revoke_role(
    user_id: uuid.UUID,
    role_name: str,
    acting_user_id: uuid.UUID,
    db_session: AsyncSession,
) -> list[RoleResponse]:
    service = RBACService(db_session)
    roles = await service.revoke_role_by_name(user_id, role_name, acting_user_id=acting_user_id)
    await db_session.commit()
    return [RoleResponse.model_validate(role) for role in roles]
