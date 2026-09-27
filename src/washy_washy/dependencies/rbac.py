"""FastAPI dependency factories for RBAC enforcement.

Built on top of ``get_current_user`` (Phase 2): a request is
authenticated first (401 via ``get_current_user`` if the token is
missing/invalid/expired), then authorized against the permission model
(403 if the role/permission isn't granted). Authorization is never a
hard-coded role check (``if user.role == "ADMIN"``) — it always goes
through :class:`~washy_washy.services.rbac_service.RBACService`, which
queries the actual Role/Permission tables.

Usage (once a route needs it — no route does yet in this phase)::

    @router.get("/orders", dependencies=[Depends(require_permission("orders", "READ_ALL", "ALL"))])
    async def list_orders(): ...
"""

from collections.abc import Awaitable, Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.exceptions import ForbiddenException
from core.models.user import User
from washy_washy.constants import error_codes, error_messages
from washy_washy.dependencies.auth import get_current_user
from washy_washy.services.rbac_service import RBACService


def require_role(role_name: str) -> Callable[..., Awaitable[User]]:
    async def dependency(
        current_user: User = Depends(get_current_user),
        db_session: AsyncSession = Depends(get_db_session),
    ) -> User:
        if not await RBACService(db_session).has_role(current_user.id, role_name):
            raise ForbiddenException(error_messages.FORBIDDEN, error_codes.FORBIDDEN)
        return current_user

    return dependency


def require_any_role(*role_names: str) -> Callable[..., Awaitable[User]]:
    """Like ``require_role``, but grants access if the caller holds
    *any* of several roles — e.g. an order operation that any of
    ``ADMIN``/``SUPERVISOR``/``LAUNDRY_PARTNER`` ("staff") may perform,
    without needing three separate ``require_role`` dependencies.
    """

    async def dependency(
        current_user: User = Depends(get_current_user),
        db_session: AsyncSession = Depends(get_db_session),
    ) -> User:
        if not await RBACService(db_session).has_any_role(current_user.id, list(role_names)):
            raise ForbiddenException(error_messages.FORBIDDEN, error_codes.FORBIDDEN)
        return current_user

    return dependency


def require_permission(resource: str, action: str, scope: str) -> Callable[..., Awaitable[User]]:
    async def dependency(
        current_user: User = Depends(get_current_user),
        db_session: AsyncSession = Depends(get_db_session),
    ) -> User:
        if not await RBACService(db_session).has_permission(
            current_user.id, resource, action, scope
        ):
            raise ForbiddenException(error_messages.FORBIDDEN, error_codes.FORBIDDEN)
        return current_user

    return dependency
