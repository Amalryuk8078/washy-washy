"""Request-level orchestration for authentication endpoints.

Thin on purpose: builds the service, calls it, shapes the result into a
response schema. The transaction boundary lives here — ``register`` is
the only operation that writes, so it's the only one that commits.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from washy_washy.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from washy_washy.services.auth_service import AuthService


async def register(request: RegisterRequest, db_session: AsyncSession) -> UserResponse:
    service = AuthService(db_session)
    user = await service.register(
        email=request.email,
        password=request.password,
        first_name=request.first_name,
        phone=request.phone,
        last_name=request.last_name,
    )
    await db_session.commit()
    return UserResponse.model_validate(user)


async def login(request: LoginRequest, db_session: AsyncSession) -> TokenResponse:
    service = AuthService(db_session)
    _, tokens = await service.login(email=request.email, password=request.password)
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


async def refresh(refresh_token: str, db_session: AsyncSession) -> str:
    service = AuthService(db_session)
    return await service.refresh(refresh_token)
