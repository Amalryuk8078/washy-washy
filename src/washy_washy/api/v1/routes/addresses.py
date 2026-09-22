import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.models.user import User
from washy_washy.api.v1.controllers import addresses as addresses_controller
from washy_washy.dependencies.auth import get_current_user
from washy_washy.schemas.address import CreateAddressRequest, UpdateAddressRequest
from washy_washy.schemas.common import SuccessResponse

router = APIRouter(prefix="/addresses", tags=["addresses"])


@router.get("", response_model=SuccessResponse)
async def list_addresses(
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    addresses = await addresses_controller.list_addresses(current_user.id, db_session)
    return SuccessResponse(message="Addresses", data=addresses)


@router.post("", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
async def create_address(
    request: CreateAddressRequest,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    address = await addresses_controller.create_address(current_user.id, request, db_session)
    return SuccessResponse(message="Address created", data=address)


@router.get("/{address_id}", response_model=SuccessResponse)
async def get_address(
    address_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    address = await addresses_controller.get_address(current_user.id, address_id, db_session)
    return SuccessResponse(message="Address", data=address)


@router.patch("/{address_id}", response_model=SuccessResponse)
async def update_address(
    address_id: uuid.UUID,
    request: UpdateAddressRequest,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    address = await addresses_controller.update_address(
        current_user.id, address_id, request, db_session
    )
    return SuccessResponse(message="Address updated", data=address)


@router.delete("/{address_id}", response_model=SuccessResponse)
async def delete_address(
    address_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    await addresses_controller.delete_address(current_user.id, address_id, db_session)
    return SuccessResponse(message="Address deleted")


@router.post("/{address_id}/set-default", response_model=SuccessResponse)
async def set_default_address(
    address_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    address = await addresses_controller.set_default_address(
        current_user.id, address_id, db_session
    )
    return SuccessResponse(message="Default address updated", data=address)
