"""Customer/partner profile business logic.

Profile creation is independent of role assignment (see
``core/models/customer_profile.py``'s docstring): creating a
``CustomerProfile`` doesn't grant the ``CUSTOMER`` role, and holding
that role doesn't require one.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConflictException, NotFoundException
from core.models.customer_profile import CustomerProfile
from core.models.partner_profile import PartnerProfile
from washy_washy.constants import error_codes, error_messages
from washy_washy.repositories.customer_profile_repo import CustomerProfileRepository
from washy_washy.repositories.partner_profile_repo import PartnerProfileRepository


class ProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self._customer_profiles = CustomerProfileRepository(session)
        self._partner_profiles = PartnerProfileRepository(session)

    async def create_customer_profile(
        self, user_id: uuid.UUID, display_name: str | None = None
    ) -> CustomerProfile:
        if await self._customer_profiles.get_by_user_id(user_id) is not None:
            raise ConflictException(
                error_messages.CUSTOMER_PROFILE_ALREADY_EXISTS,
                error_codes.CUSTOMER_PROFILE_ALREADY_EXISTS,
            )
        profile = CustomerProfile(user_id=user_id, display_name=display_name)
        return await self._customer_profiles.create(profile)

    async def get_customer_profile(self, user_id: uuid.UUID) -> CustomerProfile:
        profile = await self._customer_profiles.get_by_user_id(user_id)
        if profile is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        return profile

    async def create_partner_profile(
        self, user_id: uuid.UUID, business_name: str, contact_phone: str | None = None
    ) -> PartnerProfile:
        if await self._partner_profiles.get_by_user_id(user_id) is not None:
            raise ConflictException(
                error_messages.PARTNER_PROFILE_ALREADY_EXISTS,
                error_codes.PARTNER_PROFILE_ALREADY_EXISTS,
            )
        profile = PartnerProfile(
            user_id=user_id, business_name=business_name, contact_phone=contact_phone
        )
        return await self._partner_profiles.create(profile)

    async def get_partner_profile(self, user_id: uuid.UUID) -> PartnerProfile:
        profile = await self._partner_profiles.get_by_user_id(user_id)
        if profile is None:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        return profile
