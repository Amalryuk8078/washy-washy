"""Address business logic: ownership enforcement and the
transaction-safe "set as default" operation.
"""

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import NotFoundException
from core.models.address import Address
from washy_washy.constants import error_codes, error_messages
from washy_washy.repositories.address_repo import AddressRepository


class AddressService:
    def __init__(self, session: AsyncSession) -> None:
        self._addresses = AddressRepository(session)

    async def list_addresses(self, user_id: uuid.UUID) -> list[Address]:
        return await self._addresses.list_for_user(user_id)

    async def get_own_address(self, user_id: uuid.UUID, address_id: uuid.UUID) -> Address:
        """Raises ``NotFoundException`` — not ``ForbiddenException`` —
        for an address that exists but belongs to someone else. A
        caller who doesn't own the ID never learns whether it exists at
        all, the same security posture as ``AuthService.login``'s
        generic invalid-credentials error.
        """
        address = await self._addresses.get_by_id(address_id)
        if address is None or address.user_id != user_id:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        return address

    async def create_address(
        self,
        user_id: uuid.UUID,
        *,
        address_line_1: str,
        city: str,
        state: str,
        postal_code: str,
        country: str,
        label: str,
        address_line_2: str | None = None,
        latitude: Decimal | None = None,
        longitude: Decimal | None = None,
        is_default: bool = False,
    ) -> Address:
        address = Address(
            user_id=user_id,
            address_line_1=address_line_1,
            address_line_2=address_line_2,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
            latitude=latitude,
            longitude=longitude,
            label=label,
            is_default=False,
        )
        created = await self._addresses.create(address)
        if is_default:
            created = await self.set_default_address(user_id, created.id)
        return created

    async def update_address(
        self,
        user_id: uuid.UUID,
        address_id: uuid.UUID,
        *,
        address_line_1: str | None = None,
        address_line_2: str | None = None,
        city: str | None = None,
        state: str | None = None,
        postal_code: str | None = None,
        country: str | None = None,
        latitude: Decimal | None = None,
        longitude: Decimal | None = None,
        label: str | None = None,
    ) -> Address:
        # None means "leave unchanged" for every field here, so this
        # can't explicitly clear address_line_2 back to NULL — acceptable
        # for this phase's scope, not worth a separate "unset" sentinel.
        address = await self.get_own_address(user_id, address_id)
        if address_line_1 is not None:
            address.address_line_1 = address_line_1
        if address_line_2 is not None:
            address.address_line_2 = address_line_2
        if city is not None:
            address.city = city
        if state is not None:
            address.state = state
        if postal_code is not None:
            address.postal_code = postal_code
        if country is not None:
            address.country = country
        if latitude is not None:
            address.latitude = latitude
        if longitude is not None:
            address.longitude = longitude
        if label is not None:
            address.label = label
        return await self._addresses.update(address)

    async def delete_address(self, user_id: uuid.UUID, address_id: uuid.UUID) -> None:
        address = await self.get_own_address(user_id, address_id)
        await self._addresses.delete(address)

    async def set_default_address(self, user_id: uuid.UUID, address_id: uuid.UUID) -> Address:
        """Atomically makes ``address_id`` the user's one default address.

        Two separate flushes, not one: unset the old default (if any)
        and flush that *before* setting the new one, so the two updates
        are never both ``is_default = true`` at the same instant mid-flush
        — the database's partial unique index (see the ``Address`` model)
        would reject that collision even within the same transaction.
        """
        new_default = await self.get_own_address(user_id, address_id)

        current_default = await self._addresses.get_default_for_user(user_id)
        if current_default is not None and current_default.id != new_default.id:
            current_default.is_default = False
            await self._addresses.update(current_default)

        new_default.is_default = True
        return await self._addresses.update(new_default)
