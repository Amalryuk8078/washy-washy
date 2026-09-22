"""Integration tests for ServiceArea/serviceability, plus the
`require_role`/`require_permission`-gated `POST /service-areas` behavior
at the dependency level, against a real PostgreSQL database.
"""

import uuid

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from core.exceptions import ConflictException, ForbiddenException
from core.models.role import RoleName
from core.security.security import create_access_token
from washy_washy.dependencies.auth import get_current_user
from washy_washy.dependencies.rbac import require_role
from washy_washy.repositories.role_repo import RoleRepository
from washy_washy.repositories.user_role_repo import UserRoleRepository
from washy_washy.services.auth_service import AuthService
from washy_washy.services.service_area_service import ServiceAreaService


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


def _unique_postal_code() -> str:
    # postal_code is VARCHAR(20) -- a full uuid4 string doesn't fit.
    return str(uuid.uuid4().int)[:10]


async def _make_user(db_session):
    return await AuthService(db_session).register(
        email=f"{_unique('user')}@example.com", password="longenough1", first_name="Test"
    )


@pytest.mark.asyncio
async def test_create_service_area_with_postal_codes(db_session) -> None:
    service = ServiceAreaService(db_session)

    area = await service.create_service_area(_unique("Downtown"), ["12345", "12346"])

    assert area.is_active is True
    assert await service.is_postal_code_serviceable("12345") is True
    assert await service.is_postal_code_serviceable("12346") is True


@pytest.mark.asyncio
async def test_duplicate_service_area_name_rejected(db_session) -> None:
    service = ServiceAreaService(db_session)
    name = _unique("Downtown")
    await service.create_service_area(name, [])

    with pytest.raises(ConflictException):
        await service.create_service_area(name, [])


@pytest.mark.asyncio
async def test_unserviced_postal_code_is_not_serviceable(db_session) -> None:
    service = ServiceAreaService(db_session)

    assert await service.is_postal_code_serviceable(_unique_postal_code()) is False


@pytest.mark.asyncio
async def test_inactive_service_area_postal_code_not_serviceable(db_session) -> None:
    service = ServiceAreaService(db_session)
    postal_code = _unique_postal_code()
    area = await service.create_service_area(_unique("Suburbs"), [postal_code])
    area.is_active = False
    await db_session.flush()

    assert await service.is_postal_code_serviceable(postal_code) is False


@pytest.mark.asyncio
async def test_list_active_excludes_inactive(db_session) -> None:
    service = ServiceAreaService(db_session)
    active = await service.create_service_area(_unique("Active"), [])
    inactive = await service.create_service_area(_unique("Inactive"), [])
    inactive.is_active = False
    await db_session.flush()

    active_ids = {area.id for area in await service.list_active()}

    assert active.id in active_ids
    assert inactive.id not in active_ids


@pytest.mark.asyncio
async def test_require_role_admin_allows_admin_user(db_session) -> None:
    user = await _make_user(db_session)
    admin_role = await RoleRepository(db_session).get_by_name(RoleName.ADMIN.value)
    assert admin_role is not None, "ADMIN role should already be seeded by Phase 1's migration"
    await UserRoleRepository(db_session).assign_role(user.id, admin_role.id)

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=create_access_token(str(user.id))
    )
    current_user = await get_current_user(credentials=credentials, db_session=db_session)

    dependency = require_role(RoleName.ADMIN.value)
    result = await dependency(current_user=current_user, db_session=db_session)

    assert result.id == user.id


@pytest.mark.asyncio
async def test_require_role_admin_rejects_non_admin_user(db_session) -> None:
    user = await _make_user(db_session)
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=create_access_token(str(user.id))
    )
    current_user = await get_current_user(credentials=credentials, db_session=db_session)

    dependency = require_role(RoleName.ADMIN.value)
    with pytest.raises(ForbiddenException):
        await dependency(current_user=current_user, db_session=db_session)


@pytest.mark.asyncio
async def test_require_role_admin_rejects_customer_role(db_session) -> None:
    user = await _make_user(db_session)
    customer_role = await RoleRepository(db_session).get_by_name(RoleName.CUSTOMER.value)
    assert customer_role is not None
    await UserRoleRepository(db_session).assign_role(user.id, customer_role.id)

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=create_access_token(str(user.id))
    )
    current_user = await get_current_user(credentials=credentials, db_session=db_session)

    dependency = require_role(RoleName.ADMIN.value)
    with pytest.raises(ForbiddenException):
        await dependency(current_user=current_user, db_session=db_session)
