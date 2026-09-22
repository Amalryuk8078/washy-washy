"""create service area tables

Creates `service_areas` and `service_area_postal_codes` — the latter
references the former, so it must come second. Hand-written to match
`core/models/service_area{,_postal_code}.py` exactly.

Revision ID: 9ad4f2884494
Revises: 3587faef9553
Create Date: 2026-09-23 00:00:38.985613

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9ad4f2884494"
down_revision: str | None = "3587faef9553"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_areas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_areas")),
        sa.UniqueConstraint("name", name=op.f("uq_service_areas_name")),
    )

    op.create_table(
        "service_area_postal_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_area_id", sa.Uuid(), nullable=False),
        sa.Column("postal_code", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["service_area_id"],
            ["service_areas.id"],
            name=op.f("fk_service_area_postal_codes_service_area_id_service_areas"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_area_postal_codes")),
        sa.UniqueConstraint("postal_code", name=op.f("uq_service_area_postal_codes_postal_code")),
    )


def downgrade() -> None:
    op.drop_table("service_area_postal_codes")
    op.drop_table("service_areas")
