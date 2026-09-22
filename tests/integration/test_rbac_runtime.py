"""Integration tests for the Phase 3 RBAC runtime: RBACService's role/
permission resolution and the require_role/require_permission FastAPI
dependency factories, against a real PostgreSQL database.

require_role/require_permission's inner dependency functions are called
directly (with an already-resolved current_user, obtained by calling
get_current_user directly first) rather than through FastAPI's request
handling — same rationale as tests/integration/test_auth.py's
get_current_user tests: Phase 3 wires no protected route, so there's
nothing to test through at the HTTP level. get_current_user's own
authentication failures (no token, invalid token, expired token) are
already covered by tests/integration/test_auth.py and aren't repeated
here — this file is about the authorization layer built on top of it.
"""

import uuid

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from core.exceptions import ForbiddenException
from core.models.permission import Permission, PermissionScope
from core.models.role import Role
from core.security.security import create_access_token
from washy_washy.dependencies.auth import get_current_user
from washy_washy.dependencies.rbac import require_permission, require_role
from washy_washy.repositories.permission_repo import PermissionRepository
from washy_washy.repositories.role_permission_repo import RolePermissionRepository
from washy_washy.repositories.role_repo import RoleRepository
from washy_washy.repositories.user_role_repo import UserRoleRepository
from washy_washy.services.auth_service import AuthService
from washy_washy.services.rbac_service import RBACService


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


async def _make_user(db_session):
    return await AuthService(db_session).register(
        email=f"{_unique('user')}@example.com", password="longenough1", first_name="Test"
    )


async def _make_role(db_session, name: str | None = None) -> Role:
    return await RoleRepository(db_session).create(Role(name=name or _unique("ROLE")))


async def _make_permission(
    db_session,
    resource: str | None = None,
    action: str = "READ_ALL",
    scope: str = PermissionScope.ALL,
) -> Permission:
    return await PermissionRepository(db_session).create(
        Permission(resource=resource or _unique("resource"), action=action, scope=scope)
    )


async def _current_user_for(db_session, user_id: uuid.UUID):
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=create_access_token(str(user_id))
    )
    return await get_current_user(credentials=credentials, db_session=db_session)


@pytest.mark.asyncio
async def test_get_user_roles_returns_assigned_active_roles(db_session) -> None:
    user = await _make_user(db_session)
    role = await _make_role(db_session)
    await UserRoleRepository(db_session).assign_role(user.id, role.id)

    roles = await RBACService(db_session).get_user_roles(user.id)

    assert [r.id for r in roles] == [role.id]


@pytest.mark.asyncio
async def test_get_user_roles_excludes_inactive_roles(db_session) -> None:
    user = await _make_user(db_session)
    role = await _make_role(db_session)
    role.is_active = False
    await db_session.flush()
    await UserRoleRepository(db_session).assign_role(user.id, role.id)

    roles = await RBACService(db_session).get_user_roles(user.id)

    assert roles == []


@pytest.mark.asyncio
async def test_has_role_true_for_assigned_active_role(db_session) -> None:
    user = await _make_user(db_session)
    role = await _make_role(db_session)
    await UserRoleRepository(db_session).assign_role(user.id, role.id)

    assert await RBACService(db_session).has_role(user.id, role.name) is True


@pytest.mark.asyncio
async def test_has_role_false_for_unassigned_role(db_session) -> None:
    user = await _make_user(db_session)

    assert await RBACService(db_session).has_role(user.id, "SOME_ROLE_NOT_GRANTED") is False


@pytest.mark.asyncio
async def test_role_to_permission_resolution(db_session) -> None:
    user = await _make_user(db_session)
    role = await _make_role(db_session)
    permission = await _make_permission(db_session)
    await UserRoleRepository(db_session).assign_role(user.id, role.id)
    await RolePermissionRepository(db_session).assign_permission(role.id, permission.id)

    service = RBACService(db_session)
    permissions = await service.get_user_permissions(user.id)

    assert [p.id for p in permissions] == [permission.id]
    assert (
        await service.has_permission(
            user.id, permission.resource, permission.action, permission.scope
        )
        is True
    )


@pytest.mark.asyncio
async def test_has_permission_false_without_any_grant(db_session) -> None:
    user = await _make_user(db_session)

    assert (
        await RBACService(db_session).has_permission(user.id, "orders", "READ_ALL", "ALL") is False
    )


@pytest.mark.asyncio
async def test_multiple_roles_accumulate_permissions(db_session) -> None:
    user = await _make_user(db_session)
    role_a = await _make_role(db_session)
    role_b = await _make_role(db_session)
    permission_a = await _make_permission(db_session, action="READ_ALL")
    permission_b = await _make_permission(db_session, action="CREATE")
    await UserRoleRepository(db_session).assign_role(user.id, role_a.id)
    await UserRoleRepository(db_session).assign_role(user.id, role_b.id)
    await RolePermissionRepository(db_session).assign_permission(role_a.id, permission_a.id)
    await RolePermissionRepository(db_session).assign_permission(role_b.id, permission_b.id)

    permissions = await RBACService(db_session).get_user_permissions(user.id)

    assert {p.id for p in permissions} == {permission_a.id, permission_b.id}


@pytest.mark.asyncio
async def test_permission_shared_across_roles_is_not_duplicated(db_session) -> None:
    user = await _make_user(db_session)
    role_a = await _make_role(db_session)
    role_b = await _make_role(db_session)
    shared_permission = await _make_permission(db_session)
    await UserRoleRepository(db_session).assign_role(user.id, role_a.id)
    await UserRoleRepository(db_session).assign_role(user.id, role_b.id)
    await RolePermissionRepository(db_session).assign_permission(role_a.id, shared_permission.id)
    await RolePermissionRepository(db_session).assign_permission(role_b.id, shared_permission.id)

    permissions = await RBACService(db_session).get_user_permissions(user.id)

    assert [p.id for p in permissions] == [shared_permission.id]


@pytest.mark.asyncio
async def test_rbac_service_assign_and_remove_role(db_session) -> None:
    user = await _make_user(db_session)
    role = await _make_role(db_session)
    service = RBACService(db_session)

    await service.assign_role(user.id, role.id)
    assert await service.has_role(user.id, role.name) is True

    await service.remove_role(user.id, role.id)
    assert await service.has_role(user.id, role.name) is False


@pytest.mark.asyncio
async def test_require_role_allows_matching_role(db_session) -> None:
    user = await _make_user(db_session)
    role = await _make_role(db_session)
    await UserRoleRepository(db_session).assign_role(user.id, role.id)
    current_user = await _current_user_for(db_session, user.id)

    dependency = require_role(role.name)
    result = await dependency(current_user=current_user, db_session=db_session)

    assert result.id == user.id


@pytest.mark.asyncio
async def test_require_role_rejects_missing_role(db_session) -> None:
    user = await _make_user(db_session)
    current_user = await _current_user_for(db_session, user.id)

    dependency = require_role("SOME_ROLE_NOT_GRANTED")
    with pytest.raises(ForbiddenException):
        await dependency(current_user=current_user, db_session=db_session)


@pytest.mark.asyncio
async def test_require_permission_allows_granted_permission(db_session) -> None:
    user = await _make_user(db_session)
    role = await _make_role(db_session)
    permission = await _make_permission(
        db_session, resource="orders", action="READ_ALL", scope=PermissionScope.ALL
    )
    await UserRoleRepository(db_session).assign_role(user.id, role.id)
    await RolePermissionRepository(db_session).assign_permission(role.id, permission.id)
    current_user = await _current_user_for(db_session, user.id)

    dependency = require_permission("orders", "READ_ALL", PermissionScope.ALL)
    result = await dependency(current_user=current_user, db_session=db_session)

    assert result.id == user.id


@pytest.mark.asyncio
async def test_require_permission_rejects_ungranted_permission(db_session) -> None:
    user = await _make_user(db_session)
    current_user = await _current_user_for(db_session, user.id)

    dependency = require_permission("orders", "READ_ALL", PermissionScope.ALL)
    with pytest.raises(ForbiddenException):
        await dependency(current_user=current_user, db_session=db_session)
