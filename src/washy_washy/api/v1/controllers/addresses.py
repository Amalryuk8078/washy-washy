"""Request-level orchestration for the current user's addresses."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from washy_washy.schemas.address import (
    AddressResponse,
    CreateAddressRequest,
    UpdateAddressRequest,
)
from washy_washy.services.address_service import AddressService


async def list_addresses(user_id: uuid.UUID, db_session: AsyncSession) -> list[AddressResponse]:
    service = AddressService(db_session)
    addresses = await service.list_addresses(user_id)
    return [AddressResponse.model_validate(address) for address in addresses]


async def get_address(
    user_id: uuid.UUID, address_id: uuid.UUID, db_session: AsyncSession
) -> AddressResponse:
    service = AddressService(db_session)
    address = await service.get_own_address(user_id, address_id)
    return AddressResponse.model_validate(address)


async def create_address(
    user_id: uuid.UUID, request: CreateAddressRequest, db_session: AsyncSession
) -> AddressResponse:
    service = AddressService(db_session)
    address = await service.create_address(
        user_id,
        address_line_1=request.address_line_1,
        address_line_2=request.address_line_2,
        city=request.city,
        state=request.state,
        postal_code=request.postal_code,
        country=request.country,
        label=request.label,
        latitude=request.latitude,
        longitude=request.longitude,
        is_default=request.is_default,
    )
    await db_session.commit()
    return AddressResponse.model_validate(address)


async def update_address(
    user_id: uuid.UUID,
    address_id: uuid.UUID,
    request: UpdateAddressRequest,
    db_session: AsyncSession,
) -> AddressResponse:
    service = AddressService(db_session)
    address = await service.update_address(
        user_id,
        address_id,
        address_line_1=request.address_line_1,
        address_line_2=request.address_line_2,
        city=request.city,
        state=request.state,
        postal_code=request.postal_code,
        country=request.country,
        label=request.label,
        latitude=request.latitude,
        longitude=request.longitude,
    )
    await db_session.commit()
    return AddressResponse.model_validate(address)


async def delete_address(
    user_id: uuid.UUID, address_id: uuid.UUID, db_session: AsyncSession
) -> None:
    service = AddressService(db_session)
    await service.delete_address(user_id, address_id)
    await db_session.commit()


async def set_default_address(
    user_id: uuid.UUID, address_id: uuid.UUID, db_session: AsyncSession
) -> AddressResponse:
    service = AddressService(db_session)
    address = await service.set_default_address(user_id, address_id)
    await db_session.commit()
    return AddressResponse.model_validate(address)
