"""Persistence for :class:`core.models.payment_event.PaymentEvent`.

Append-only, and the vehicle for webhook idempotency: ``create`` will
raise ``IntegrityError`` if ``provider_event_id`` has already been
recorded (the real, database-level guard); ``get_by_provider_event_id``
exists so the service layer can pre-check for a clean "already
processed, no-op" response instead of relying on catching that error
for every duplicate delivery — the same "pre-check for a clean
response, database constraint as the real guard against the race"
pattern as ``RBACService.grant_role_by_name`` (Phase 4).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.payment_event import PaymentEvent


class PaymentEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_provider_event_id(self, provider_event_id: str) -> PaymentEvent | None:
        stmt = select(PaymentEvent).where(PaymentEvent.provider_event_id == provider_event_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, event: PaymentEvent) -> PaymentEvent:
        self._session.add(event)
        await self._session.flush()
        return event
