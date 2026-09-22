"""Persistence for :class:`core.models.role_permission.RolePermission`."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.permission import Permission
from core.models.role_permission import RolePermission


class RolePermissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def assign_permission(
        self, role_id: uuid.UUID, permission_id: uuid.UUID
    ) -> RolePermission:
        """Does not pre-check for an existing grant: the database's unique
        ``(role_id, permission_id)`` constraint is the real guard against
        a duplicate under concurrent requests (see the model docstring).
        A duplicate grant surfaces as an ``IntegrityError`` on flush.
        """
        role_permission = RolePermission(role_id=role_id, permission_id=permission_id)
        self._session.add(role_permission)
        await self._session.flush()
        return role_permission

    async def remove_permission(self, role_id: uuid.UUID, permission_id: uuid.UUID) -> None:
        stmt = delete(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        )
        await self._session.execute(stmt)

    async def get_permissions_for_role(self, role_id: uuid.UUID) -> list[Permission]:
        stmt = (
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def role_has_permission(self, role_id: uuid.UUID, permission_id: uuid.UUID) -> bool:
        stmt = select(RolePermission.id).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
