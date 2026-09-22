"""Persistence for :class:`core.models.customer_profile.CustomerProfile`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.customer_profile import CustomerProfile


class CustomerProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: uuid.UUID) -> CustomerProfile | None:
        stmt = select(CustomerProfile).where(CustomerProfile.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, profile: CustomerProfile) -> CustomerProfile:
        self._session.add(profile)
        await self._session.flush()
        return profile
