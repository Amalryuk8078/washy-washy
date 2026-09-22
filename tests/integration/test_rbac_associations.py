"""Integration tests for Role/Permission/UserRole/RolePermission against
a real PostgreSQL database. Requires a migrated DB (``alembic upgrade
head``) — see tests/integration/conftest.py's ``db_session`` fixture,
which skips cleanly when one isn't available.
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from core.models.permission import Permission, PermissionScope
from core.models.role import Role
from core.models.user import User
from washy_washy.repositories.permission_repo import PermissionRepository
from washy_washy.repositories.role_permission_repo import RolePermissionRepository
from washy_washy.repositories.role_repo import RoleRepository
from washy_washy.repositories.user_repo import UserRepository
from washy_washy.repositories.user_role_repo import UserRoleRepository


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


async def _make_user(db_session) -> User:
    return await UserRepository(db_session).create(
        User(
            email=f"{_unique('user')}@example.com",
            password_hash="not-a-real-hash",
            first_name="Test",
        )
    )


async def _make_role(db_session) -> Role:
    return await RoleRepository(db_session).create(Role(name=_unique("ROLE")))


async def _make_permission(db_session) -> Permission:
    return await PermissionRepository(db_session).create(
        Permission(resource=_unique("resource"), action="CREATE", scope=PermissionScope.ALL)
    )


@pytest.mark.asyncio
async def test_create_role_defaults_active(db_session) -> None:
    role = await _make_role(db_session)

    assert isinstance(role.id, uuid.UUID)
    assert role.is_active is True


@pytest.mark.asyncio
async def test_duplicate_role_name_rejected(db_session) -> None:
    repo = RoleRepository(db_session)
    name = _unique("ROLE")
    await repo.create(Role(name=name))

    with pytest.raises(IntegrityError):
        await repo.create(Role(name=name))


@pytest.mark.asyncio
async def test_create_permission(db_session) -> None:
    permission = await _make_permission(db_session)

    assert isinstance(permission.id, uuid.UUID)


@pytest.mark.asyncio
async def test_duplicate_permission_identity_rejected(db_session) -> None:
    repo = PermissionRepository(db_session)
    resource = _unique("resource")
    await repo.create(Permission(resource=resource, action="CREATE", scope=PermissionScope.ALL))

    with pytest.raises(IntegrityError):
        await repo.create(Permission(resource=resource, action="CREATE", scope=PermissionScope.ALL))


@pytest.mark.asyncio
async def test_permission_scope_check_constraint_rejects_invalid_scope(db_session) -> None:
    repo = PermissionRepository(db_session)

    with pytest.raises(IntegrityError):
        await repo.create(
            Permission(resource=_unique("resource"), action="CREATE", scope="NOT_A_SCOPE")
        )


@pytest.mark.asyncio
async def test_assign_and_retrieve_user_role(db_session) -> None:
    user = await _make_user(db_session)
    role = await _make_role(db_session)
    repo = UserRoleRepository(db_session)

    await repo.assign_role(user.id, role.id)

    assert await repo.user_has_role(user.id, role.id) is True
    roles = await repo.get_roles_for_user(user.id)
    assert [r.id for r in roles] == [role.id]


@pytest.mark.asyncio
async def test_duplicate_user_role_assignment_rejected(db_session) -> None:
    user = await _make_user(db_session)
    role = await _make_role(db_session)
    repo = UserRoleRepository(db_session)
    await repo.assign_role(user.id, role.id)

    with pytest.raises(IntegrityError):
        await repo.assign_role(user.id, role.id)


@pytest.mark.asyncio
async def test_user_role_foreign_key_integrity(db_session) -> None:
    repo = UserRoleRepository(db_session)

    with pytest.raises(IntegrityError):
        await repo.assign_role(uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_removing_user_role_does_not_delete_user_or_role(db_session) -> None:
    user = await _make_user(db_session)
    role = await _make_role(db_session)
    repo = UserRoleRepository(db_session)
    await repo.assign_role(user.id, role.id)

    await repo.remove_role(user.id, role.id)

    assert await repo.user_has_role(user.id, role.id) is False
    assert await UserRepository(db_session).get_by_id(user.id) is not None
    assert await RoleRepository(db_session).get_by_id(role.id) is not None


@pytest.mark.asyncio
async def test_deleting_user_cascades_to_user_role_but_not_role(db_session) -> None:
    user = await _make_user(db_session)
    role = await _make_role(db_session)
    repo = UserRoleRepository(db_session)
    await repo.assign_role(user.id, role.id)

    await db_session.delete(user)
    await db_session.flush()

    assert await repo.user_has_role(user.id, role.id) is False
    assert await RoleRepository(db_session).get_by_id(role.id) is not None


@pytest.mark.asyncio
async def test_assign_and_retrieve_role_permission(db_session) -> None:
    role = await _make_role(db_session)
    permission = await _make_permission(db_session)
    repo = RolePermissionRepository(db_session)

    await repo.assign_permission(role.id, permission.id)

    assert await repo.role_has_permission(role.id, permission.id) is True
    permissions = await repo.get_permissions_for_role(role.id)
    assert [p.id for p in permissions] == [permission.id]


@pytest.mark.asyncio
async def test_duplicate_role_permission_assignment_rejected(db_session) -> None:
    role = await _make_role(db_session)
    permission = await _make_permission(db_session)
    repo = RolePermissionRepository(db_session)
    await repo.assign_permission(role.id, permission.id)

    with pytest.raises(IntegrityError):
        await repo.assign_permission(role.id, permission.id)


@pytest.mark.asyncio
async def test_role_permission_foreign_key_integrity(db_session) -> None:
    repo = RolePermissionRepository(db_session)

    with pytest.raises(IntegrityError):
        await repo.assign_permission(uuid.uuid4(), uuid.uuid4())
