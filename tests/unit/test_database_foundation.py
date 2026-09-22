"""Tests for the shared database/model foundation (Phase 1A).

No domain models exist yet, so these exercise the reusable infrastructure
directly: the naming convention on ``Base.metadata`` and the UUID/
timestamp mixins. A throwaway model class is defined locally purely to
inspect the column shapes the mixins produce — it is never persisted.
"""

import uuid

from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


def test_base_metadata_exists() -> None:
    assert Base.metadata is not None


def test_naming_convention_is_deterministic() -> None:
    convention = Base.metadata.naming_convention
    assert convention["pk"] == "pk_%(table_name)s"
    assert convention["uq"] == "uq_%(table_name)s_%(column_0_name)s"
    assert convention["ck"] == "ck_%(table_name)s_%(constraint_name)s"
    assert convention["fk"] == "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
    assert convention["ix"] == "ix_%(column_0_label)s"


class _Widget(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Throwaway model used only to inspect the mixins' column shapes."""

    __tablename__ = "_test_widget"

    name: Mapped[str] = mapped_column(default="widget")


def test_uuid_primary_key_mixin_column_shape() -> None:
    column = _Widget.__table__.c.id
    assert column.primary_key is True
    assert isinstance(column.type, Uuid)


def test_uuid_primary_key_mixin_default_produces_valid_uuid() -> None:
    # SQLAlchemy wraps zero-arg default callables as ``lambda ctx: fn()``
    # (see ``CallableColumnDefault._maybe_wrap_callable``), so the stored
    # ``arg`` expects an execution context positionally; it's unused by a
    # context-free generator like ``uuid.uuid4``, so ``None`` is fine here.
    default_factory = _Widget.__table__.c.id.default.arg
    generated = default_factory(None)
    assert isinstance(generated, uuid.UUID)


def test_timestamp_columns_are_timezone_aware_and_server_controlled() -> None:
    created_col = _Widget.__table__.c.created_at
    updated_col = _Widget.__table__.c.updated_at

    assert created_col.type.timezone is True
    assert updated_col.type.timezone is True

    assert created_col.nullable is False
    assert updated_col.nullable is False

    # Populated by PostgreSQL, not by application code or API clients.
    assert created_col.server_default is not None
    assert updated_col.server_default is not None
    assert updated_col.onupdate is not None
