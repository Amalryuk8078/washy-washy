"""RBAC resolution: turns the Role/Permission database (Phase 1) into
runtime authorization decisions.

This is the one place authorization SQL lives — routes and dependencies
never write their own role/permission queries; they call this service.
Only *active* roles ever grant anything (an inactive role is treated as
if it weren't assigned).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.permission import Permission
from core.models.role import Role
from core.models.role_permission import RolePermission
from core.models.user_role import UserRole
from washy_washy.repositories.user_role_repo import UserRoleRepository


class RBACService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._user_roles = UserRoleRepository(session)

    async def get_user_roles(self, user_id: uuid.UUID) -> list[Role]:
        roles = await self._user_roles.get_roles_for_user(user_id)
        return [role for role in roles if role.is_active]

    async def get_user_permissions(self, user_id: uuid.UUID) -> list[Permission]:
        stmt = (
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id, Role.is_active.is_(True))
            .distinct()
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def has_role(self, user_id: uuid.UUID, role_name: str) -> bool:
        stmt = (
            select(Role.id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id,
                Role.name == role_name,
                Role.is_active.is_(True),
            )
        )
        result = await self._session.execute(stmt)
        return result.first() is not None

    async def has_permission(
        self, user_id: uuid.UUID, resource: str, action: str, scope: str
    ) -> bool:
        stmt = (
            select(Permission.id)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id,
                Role.is_active.is_(True),
                Permission.resource == resource,
                Permission.action == action,
                Permission.scope == scope,
            )
        )
        result = await self._session.execute(stmt)
        return result.first() is not None

    async def assign_role(self, user_id: uuid.UUID, role_id: uuid.UUID) -> UserRole:
        return await self._user_roles.assign_role(user_id, role_id)

    async def remove_role(self, user_id: uuid.UUID, role_id: uuid.UUID) -> None:
        await self._user_roles.remove_role(user_id, role_id)
