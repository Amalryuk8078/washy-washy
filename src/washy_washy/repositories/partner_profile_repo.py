"""Persistence for :class:`core.models.partner_profile.PartnerProfile`.

`create`/`get_by_id`/`get_by_user_id` were unwired to any endpoint
through Phase 8 (Phase 4's own `4.8 APIs` list didn't include
`/partners/me`) — Phase 9 is the first to actually use `update`, for
the `PartnerStatus` lifecycle (`PATCH /partners/{id}/status`).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.partner_profile import PartnerProfile


class PartnerProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, partner_profile_id: uuid.UUID) -> PartnerProfile | None:
        return await self._session.get(PartnerProfile, partner_profile_id)

    async def get_by_user_id(self, user_id: uuid.UUID) -> PartnerProfile | None:
        stmt = select(PartnerProfile).where(PartnerProfile.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, profile: PartnerProfile) -> PartnerProfile:
        self._session.add(profile)
        await self._session.flush()
        return profile

    async def update(self, profile: PartnerProfile) -> PartnerProfile:
        await self._session.flush()
        return profile
