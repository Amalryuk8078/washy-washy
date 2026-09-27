"""Request-level orchestration for partner-onboarding endpoints."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from washy_washy.schemas.facilities import UpdatePartnerStatusRequest
from washy_washy.schemas.profile import PartnerProfileResponse
from washy_washy.services.profile_service import ProfileService


async def update_partner_status(
    partner_profile_id: uuid.UUID, request: UpdatePartnerStatusRequest, db_session: AsyncSession
) -> PartnerProfileResponse:
    service = ProfileService(db_session)
    profile = await service.update_partner_status(partner_profile_id, request.status.value)
    await db_session.commit()
    return PartnerProfileResponse.model_validate(profile)
