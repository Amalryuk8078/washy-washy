"""Integration tests for the admin role-management API
(`RBACService.{grant,revoke}_role_by_name`, `list_assignable_roles`,
`get_user`/`get_user_by_email`), against a real PostgreSQL database.

Closes a gap Phase 3/4 explicitly deferred: an admin API for granting/
revoking roles, rather than tests reaching into `UserRoleRepository`
directly (which is still how *these* tests bootstrap the initial ADMIN
grant needed to test the API itself — there's no other way in).
"""

import uuid

import pytest

from core.exceptions import BusinessRuleException, ConflictException, NotFoundException
from core.models.role import Role, RoleName
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


@pytest.mark.asyncio
async def test_list_assignable_roles_includes_seeded_roles(db_session) -> None:
    roles = await RBACService(db_session).list_assignable_roles()

    names = {role.name for role in roles}
    assert RoleName.ADMIN.value in names
    assert RoleName.CUSTOMER.value in names


@pytest.mark.asyncio
async def test_grant_role_by_name(db_session) -> None:
    user = await _make_user(db_session)
    role = await _make_role(db_session)
    service = RBACService(db_session)

    roles = await service.grant_role_by_name(user.id, role.name)

    assert [r.id for r in roles] == [role.id]


@pytest.mark.asyncio
async def test_grant_duplicate_role_rejected(db_session) -> None:
    user = await _make_user(db_session)
    role = await _make_role(db_session)
    service = RBACService(db_session)
    await service.grant_role_by_name(user.id, role.name)

    with pytest.raises(ConflictException):
        await service.grant_role_by_name(user.id, role.name)


@pytest.mark.asyncio
async def test_grant_role_for_nonexistent_user_raises_not_found(db_session) -> None:
    role = await _make_role(db_session)

    with pytest.raises(NotFoundException):
        await RBACService(db_session).grant_role_by_name(uuid.uuid4(), role.name)


@pytest.mark.asyncio
async def test_grant_nonexistent_role_raises_not_found(db_session) -> None:
    user = await _make_user(db_session)

    with pytest.raises(NotFoundException):
        await RBACService(db_session).grant_role_by_name(user.id, "NOT_A_REAL_ROLE")


@pytest.mark.asyncio
async def test_grant_inactive_role_raises_not_found(db_session) -> None:
    user = await _make_user(db_session)
    role = await _make_role(db_session)
    role.is_active = False
    await db_session.flush()

    with pytest.raises(NotFoundException):
        await RBACService(db_session).grant_role_by_name(user.id, role.name)


@pytest.mark.asyncio
async def test_revoke_role_by_name(db_session) -> None:
    user = await _make_user(db_session)
    role = await _make_role(db_session)
    service = RBACService(db_session)
    await service.grant_role_by_name(user.id, role.name)

    roles = await service.revoke_role_by_name(user.id, role.name)

    assert roles == []


@pytest.mark.asyncio
async def test_revoke_unassigned_role_raises_not_found(db_session) -> None:
    user = await _make_user(db_session)
    role = await _make_role(db_session)

    with pytest.raises(NotFoundException):
        await RBACService(db_session).revoke_role_by_name(user.id, role.name)


@pytest.mark.asyncio
async def test_admin_cannot_revoke_own_admin_role(db_session) -> None:
    admin_user = await _make_user(db_session)
    await UserRoleRepository(db_session).assign_role(
        admin_user.id, (await RoleRepository(db_session).get_by_name(RoleName.ADMIN.value)).id
    )
    service = RBACService(db_session)

    with pytest.raises(BusinessRuleException):
        await service.revoke_role_by_name(
            admin_user.id, RoleName.ADMIN.value, acting_user_id=admin_user.id
        )


@pytest.mark.asyncio
async def test_admin_can_revoke_another_users_admin_role(db_session) -> None:
    acting_admin = await _make_user(db_session)
    target_user = await _make_user(db_session)
    admin_role = await RoleRepository(db_session).get_by_name(RoleName.ADMIN.value)
    await UserRoleRepository(db_session).assign_role(target_user.id, admin_role.id)
    service = RBACService(db_session)

    roles = await service.revoke_role_by_name(
        target_user.id, RoleName.ADMIN.value, acting_user_id=acting_admin.id
    )

    assert roles == []


@pytest.mark.asyncio
async def test_get_user_and_get_user_by_email(db_session) -> None:
    user = await _make_user(db_session)
    service = RBACService(db_session)

    assert (await service.get_user(user.id)).id == user.id
    assert (await service.get_user_by_email(user.email)).id == user.id


@pytest.mark.asyncio
async def test_get_user_by_email_not_found(db_session) -> None:
    with pytest.raises(NotFoundException):
        await RBACService(db_session).get_user_by_email(f"{_unique('nobody')}@example.com")
