"""Persistence for :class:`core.models.user_role.UserRole`."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.role import Role
from core.models.user_role import UserRole


class UserRoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def assign_role(self, user_id: uuid.UUID, role_id: uuid.UUID) -> UserRole:
        """Does not pre-check for an existing assignment: the database's
        unique ``(user_id, role_id)`` constraint is the real guard against
        a duplicate under concurrent requests (see the model docstring).
        A duplicate assignment surfaces as an ``IntegrityError`` on flush.
        """
        user_role = UserRole(user_id=user_id, role_id=role_id)
        self._session.add(user_role)
        await self._session.flush()
        return user_role

    async def remove_role(self, user_id: uuid.UUID, role_id: uuid.UUID) -> None:
        stmt = delete(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
        await self._session.execute(stmt)

    async def get_roles_for_user(self, user_id: uuid.UUID) -> list[Role]:
        stmt = (
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def user_has_role(self, user_id: uuid.UUID, role_id: uuid.UUID) -> bool:
        stmt = select(UserRole.id).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
