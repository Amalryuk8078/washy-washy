"""Persistence for :class:`core.models.partner_profile.PartnerProfile`.

Not yet wired to any API endpoint (Phase 4's `4.8 APIs` list doesn't
include `/partners/me`) — exists so the model/service layer are complete
and ready, same "build the piece, don't force a premature endpoint"
pattern as Phase 2/3's `get_current_user`/`require_role`.
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
