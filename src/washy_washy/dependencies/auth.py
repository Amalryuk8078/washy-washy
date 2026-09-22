"""FastAPI dependency that resolves the authenticated user from a
``Authorization: Bearer <access_token>`` header.

Lives in ``washy_washy`` (not ``core/dependencies``, alongside
``get_db_session``) because it needs ``UserRepository`` and
``washy_washy``'s own error codes/messages, which ``core`` must never
depend on.

Only resolves *who* the caller is — it does not check roles or
permissions. That's Phase 3's ``require_role``/``require_permission``,
built on top of this.
"""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.exceptions import UnauthorizedException
from core.models.user import User
from washy_washy.constants import error_codes, error_messages
from washy_washy.services.auth_service import AuthService, decode_or_raise

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db_session: AsyncSession = Depends(get_db_session),
) -> User:
    if credentials is None:
        raise UnauthorizedException(
            error_messages.AUTH_TOKEN_INVALID, error_codes.AUTH_TOKEN_INVALID
        )

    payload = decode_or_raise(credentials.credentials)
    if payload.get("type") != "access":
        raise UnauthorizedException(
            error_messages.AUTH_TOKEN_INVALID, error_codes.AUTH_TOKEN_INVALID
        )

    return await AuthService(db_session).get_active_user(payload.get("sub"))
