"""default payment currency to inr

Changes `payments.currency`'s server-side default from `'USD'` to
`'INR'`, matching `core/models/payment.py::Payment.currency`'s updated
default. Only alters the column default — existing rows (and their
already-stored currency values) are untouched; this only changes what
gets written when a caller omits `currency` from here on.

Revision ID: b8af1bd42035
Revises: a4e3ae0f131d
Create Date: 2026-10-04 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8af1bd42035"
down_revision: str | None = "a4e3ae0f131d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "payments",
        "currency",
        server_default=sa.text("'INR'"),
    )


def downgrade() -> None:
    op.alter_column(
        "payments",
        "currency",
        server_default=sa.text("'USD'"),
    )
