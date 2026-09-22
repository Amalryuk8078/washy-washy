"""Authentication business logic: registration, login, and token
issuance/refresh.

No HTTP concerns and no direct SQL here — persistence goes through
``UserRepository``. This service ``flush()``es via the repository but
never commits; the caller (the controller) owns the transaction
boundary, per the project's layering conventions.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConflictException, UnauthorizedException
from core.models.user import User
from core.security.security import (
    TokenExpiredError,
    TokenInvalidError,
    create_access_token,
    create_refresh_token,
    decode_token_strict,
    hash_password,
    verify_password,
)
from washy_washy.constants import error_codes, error_messages
from washy_washy.repositories.user_repo import UserRepository, normalize_email


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._users = UserRepository(session)

    async def register(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        phone: str | None = None,
        last_name: str | None = None,
    ) -> User:
        normalized_email = normalize_email(email)

        if await self._users.exists_by_email(normalized_email):
            raise ConflictException(
                error_messages.AUTH_EMAIL_ALREADY_EXISTS,
                error_codes.AUTH_EMAIL_ALREADY_EXISTS,
            )
        if phone and await self._users.exists_by_phone(phone):
            raise ConflictException(
                error_messages.AUTH_PHONE_ALREADY_EXISTS,
                error_codes.AUTH_PHONE_ALREADY_EXISTS,
            )

        user = User(
            email=normalized_email,
            phone=phone,
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
        )
        return await self._users.create(user)

    async def login(self, *, email: str, password: str) -> tuple[User, TokenPair]:
        # Same generic failure for "no such user" and "wrong password" —
        # never reveal which one it was.
        user = await self._users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedException(
                error_messages.AUTH_INVALID_CREDENTIALS,
                error_codes.AUTH_INVALID_CREDENTIALS,
            )
        if not user.is_active:
            raise UnauthorizedException(
                error_messages.AUTH_USER_INACTIVE, error_codes.AUTH_USER_INACTIVE
            )

        return user, _issue_token_pair(user.id)

    async def refresh(self, refresh_token: str) -> str:
        payload = decode_or_raise(refresh_token)
        if payload.get("type") != "refresh":
            raise UnauthorizedException(
                error_messages.AUTH_REFRESH_TOKEN_REQUIRED,
                error_codes.AUTH_REFRESH_TOKEN_REQUIRED,
            )

        user = await self.get_active_user(payload.get("sub"))
        return create_access_token(str(user.id))

    async def get_active_user(self, subject: str | None) -> User:
        """Resolve a JWT ``sub`` claim to an active :class:`User`.

        Shared by ``refresh`` and, via
        ``washy_washy.dependencies.auth.get_current_user``, by every
        authenticated request — one place decides what "a usable token
        subject" means.
        """

        user_id = parse_subject_uuid(subject)
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UnauthorizedException(
                error_messages.AUTH_TOKEN_INVALID, error_codes.AUTH_TOKEN_INVALID
            )
        if not user.is_active:
            raise UnauthorizedException(
                error_messages.AUTH_USER_INACTIVE, error_codes.AUTH_USER_INACTIVE
            )
        return user


def _issue_token_pair(user_id: uuid.UUID) -> TokenPair:
    subject = str(user_id)
    return TokenPair(
        access_token=create_access_token(subject),
        refresh_token=create_refresh_token(subject),
    )


def decode_or_raise(token: str) -> dict:
    """Decode a JWT, raising the right ``UnauthorizedException`` variant
    (expired vs. otherwise invalid) instead of returning ``None``.
    """

    try:
        return decode_token_strict(token)
    except TokenExpiredError as exc:
        raise UnauthorizedException(
            error_messages.AUTH_TOKEN_EXPIRED, error_codes.AUTH_TOKEN_EXPIRED
        ) from exc
    except TokenInvalidError as exc:
        raise UnauthorizedException(
            error_messages.AUTH_TOKEN_INVALID, error_codes.AUTH_TOKEN_INVALID
        ) from exc


def parse_subject_uuid(subject: str | None) -> uuid.UUID:
    if subject is None:
        raise UnauthorizedException(
            error_messages.AUTH_TOKEN_INVALID, error_codes.AUTH_TOKEN_INVALID
        )
    try:
        return uuid.UUID(subject)
    except ValueError as exc:
        raise UnauthorizedException(
            error_messages.AUTH_TOKEN_INVALID, error_codes.AUTH_TOKEN_INVALID
        ) from exc
