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

from core.exceptions import (
    BusinessRuleException,
    ConflictException,
    NotFoundException,
)
from core.models.permission import Permission
from core.models.role import Role, RoleName
from core.models.role_permission import RolePermission
from core.models.user import User
from core.models.user_role import UserRole
from washy_washy.constants import error_codes, error_messages
from washy_washy.repositories.role_repo import RoleRepository
from washy_washy.repositories.user_repo import UserRepository
from washy_washy.repositories.user_role_repo import UserRoleRepository


class RBACService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._user_roles = UserRoleRepository(session)
        self._roles = RoleRepository(session)
        self._users = UserRepository(session)

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

    async def has_any_role(self, user_id: uuid.UUID, role_names: list[str]) -> bool:
        """Reuses ``has_role`` rather than a separate query — this is
        still "the one place authorization SQL lives," just called
        once per candidate role instead of writing an ``IN (...)``
        variant for what is, in practice, always a short, fixed list
        (e.g. the "is this caller staff" check in Phase 8's order
        endpoints).
        """
        for role_name in role_names:
            if await self.has_role(user_id, role_name):
                return True
        return False

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

    async def list_assignable_roles(self) -> list[Role]:
        return await self._roles.list_active()

    async def get_user(self, user_id: uuid.UUID) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        return user

    async def get_user_by_email(self, email: str) -> User:
        user = await self._users.get_by_email(email)
        if user is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        return user

    async def grant_role_by_name(self, user_id: uuid.UUID, role_name: str) -> list[Role]:
        """Grants ``role_name`` and returns the user's resulting active roles.

        The existence pre-check gives a clean 409 for the common case; the
        unique ``(user_id, role_id)`` constraint still guards the race.
        """
        await self.get_user(user_id)
        role = await self._get_role(role_name)
        if await self._user_roles.user_has_role(user_id, role.id):
            raise ConflictException(
                error_messages.ROLE_ALREADY_ASSIGNED, error_codes.ROLE_ALREADY_ASSIGNED
            )
        await self._user_roles.assign_role(user_id, role.id)
        return await self.get_user_roles(user_id)

    async def revoke_role_by_name(
        self, user_id: uuid.UUID, role_name: str, *, acting_user_id: uuid.UUID | None = None
    ) -> list[Role]:
        """Revokes ``role_name`` and returns the user's remaining active roles.

        An admin may not strip their own ADMIN role, so the last admin
        can't accidentally lock everyone out of role management.
        """
        await self.get_user(user_id)
        if acting_user_id == user_id and role_name == RoleName.ADMIN.value:
            raise BusinessRuleException(
                error_messages.CANNOT_REMOVE_OWN_ADMIN_ROLE,
                error_codes.CANNOT_REMOVE_OWN_ADMIN_ROLE,
            )
        role = await self._get_role(role_name)
        if not await self._user_roles.user_has_role(user_id, role.id):
            raise NotFoundException(error_messages.ROLE_NOT_ASSIGNED, error_codes.ROLE_NOT_ASSIGNED)
        await self._user_roles.remove_role(user_id, role.id)
        return await self.get_user_roles(user_id)

    async def _get_role(self, role_name: str) -> Role:
        role = await self._roles.get_by_name(role_name)
        if role is None or not role.is_active:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        return role
