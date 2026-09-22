"""Persistence for :class:`core.models.user.User`.

Repository rules (see README.md "Development conventions"): receives an
injected ``AsyncSession``, never creates its own; never raises
``HTTPException`` or makes authorization decisions; flushes but does not
commit — the transaction boundary belongs to the service/controller layer
that calls this repository.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.user import User


def normalize_email(email: str) -> str:
    """The single normalization path every read/write must go through.

    Washy Washy treats ``Amal@Example.com`` and ``amal@example.com`` as
    the same identity: emails are lowercased and stripped before they
    ever reach the database. Combined with the plain UNIQUE constraint on
    ``users.email`` (see the model), this is sufficient without a
    PostgreSQL case-insensitive extension.
    """

    return email.strip().lower()


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == normalize_email(email))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> User | None:
        stmt = select(User).where(User.phone == phone)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def exists_by_email(self, email: str) -> bool:
        return await self.get_by_email(email) is not None

    async def exists_by_phone(self, phone: str) -> bool:
        return await self.get_by_phone(phone) is not None

    async def create(self, user: User) -> User:
        user.email = normalize_email(user.email)
        self._session.add(user)
        await self._session.flush()
        return user
