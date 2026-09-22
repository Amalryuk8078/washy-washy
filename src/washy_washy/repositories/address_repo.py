"""Persistence for :class:`core.models.address.Address`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.address import Address


class AddressRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, address_id: uuid.UUID) -> Address | None:
        return await self._session.get(Address, address_id)

    async def list_for_user(self, user_id: uuid.UUID) -> list[Address]:
        stmt = select(Address).where(Address.user_id == user_id).order_by(Address.created_at)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_default_for_user(self, user_id: uuid.UUID) -> Address | None:
        stmt = select(Address).where(Address.user_id == user_id, Address.is_default.is_(True))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, address: Address) -> Address:
        self._session.add(address)
        await self._session.flush()
        return address

    async def update(self, address: Address) -> Address:
        """Persists in-place attribute changes already made to ``address``
        (an object already tracked by this session, e.g. from
        ``get_by_id``) — this repository doesn't need to know what
        changed, only to flush it.
        """
        await self._session.flush()
        return address

    async def delete(self, address: Address) -> None:
        await self._session.delete(address)
        await self._session.flush()
