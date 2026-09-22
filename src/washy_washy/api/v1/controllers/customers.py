"""Request-level orchestration for the current user's customer profile."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from washy_washy.schemas.profile import CreateCustomerProfileRequest, CustomerProfileResponse
from washy_washy.services.profile_service import ProfileService


async def create_my_profile(
    user_id: uuid.UUID, request: CreateCustomerProfileRequest, db_session: AsyncSession
) -> CustomerProfileResponse:
    service = ProfileService(db_session)
    profile = await service.create_customer_profile(user_id, display_name=request.display_name)
    await db_session.commit()
    return CustomerProfileResponse.model_validate(profile)


async def get_my_profile(user_id: uuid.UUID, db_session: AsyncSession) -> CustomerProfileResponse:
    service = ProfileService(db_session)
    profile = await service.get_customer_profile(user_id)
    return CustomerProfileResponse.model_validate(profile)
