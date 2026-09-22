"""Persistence for :class:`core.models.permission.Permission`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.permission import Permission
from core.models.role_permission import RolePermission


class PermissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, permission_id: uuid.UUID) -> Permission | None:
        return await self._session.get(Permission, permission_id)

    async def get_by_resource_action_scope(
        self, resource: str, action: str, scope: str
    ) -> Permission | None:
        stmt = select(Permission).where(
            Permission.resource == resource,
            Permission.action == action,
            Permission.scope == scope,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_role(self, role_id: uuid.UUID) -> list[Permission]:
        stmt = (
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, permission: Permission) -> Permission:
        self._session.add(permission)
        await self._session.flush()
        return permission
