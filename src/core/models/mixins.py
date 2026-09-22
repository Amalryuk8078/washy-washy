"""Reusable model infrastructure shared across future domain models.

Mixins here are intentionally small and composable — do not fold every
cross-cutting concern (soft delete, audit trail, tenancy, ...) into one
giant base. A domain model opts into exactly what it needs, e.g.::

    class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
        __tablename__ = "users"
        ...
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPrimaryKeyMixin:
    """Adds a UUID primary key generated on the application side.

    Uses SQLAlchemy's backend-agnostic ``Uuid`` type, which maps to
    PostgreSQL's native ``uuid`` column. The value is always generated
    before insert (``uuid.uuid4``) — API clients never supply it and no
    sequential/guessable ID is ever exposed.
    """

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


class CreatedAtMixin:
    """Adds a server-controlled, timezone-aware ``created_at`` only.

    For rows that are never edited in place — pure association/junction
    tables like ``UserRole``/``RolePermission``, which exist or don't,
    never "change" — so there is no ``updated_at`` to maintain.

    Also sets ``eager_defaults=True`` (inherited by every model, via
    plain MRO attribute lookup — see ``TimestampMixin``/``UUIDPrimaryKeyMixin``
    combos): without it, a row updated mid-request comes back with its
    server-computed columns (``updated_at``'s ``onupdate=func.now()``)
    "expired" rather than refreshed, deferring the fetch to the next
    attribute access. If that access happens outside an awaited
    SQLAlchemy call — e.g. inside a synchronous Pydantic
    ``model_validate(...)`` right after a flush — it can't run the async
    lazy-load it needs and raises ``MissingGreenlet``. Forcing RETURNING
    on every INSERT/UPDATE keeps these columns always populated
    immediately after flush, regardless of what touches the object next.
    """

    __mapper_args__ = {"eager_defaults": True}

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class TimestampMixin(CreatedAtMixin):
    """Adds server-controlled, timezone-aware ``created_at``/``updated_at``.

    Both columns are populated by PostgreSQL (``server_default``/
    ``onupdate`` using ``now()``) rather than application code, so they
    stay correct regardless of client clock skew and can never be
    overridden by an API consumer.
    """

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
