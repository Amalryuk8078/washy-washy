"""create profile and address tables

Creates `customer_profiles`, `partner_profiles`, and `addresses` — three
independent tables that each reference only `users` (already exists),
so they can all land in one revision. Hand-written to match
`core/models/{customer_profile,partner_profile,address}.py` exactly.

Revision ID: 3587faef9553
Revises: db9e1e1a26b8
Create Date: 2026-09-23 00:00:37.749543

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3587faef9553"
down_revision: str | None = "db9e1e1a26b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_customer_profiles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customer_profiles")),
        sa.UniqueConstraint("user_id", name=op.f("uq_customer_profiles_user_id")),
    )

    op.create_table(
        "partner_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("business_name", sa.String(length=200), nullable=False),
        sa.Column("contact_phone", sa.String(length=32), nullable=True),
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'PENDING'"), nullable=False
        ),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_partner_profiles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partner_profiles")),
        sa.UniqueConstraint("user_id", name=op.f("uq_partner_profiles_user_id")),
    )

    op.create_table(
        "addresses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("address_line_1", sa.String(length=255), nullable=False),
        sa.Column("address_line_2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=False),
        sa.Column("postal_code", sa.String(length=20), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("label", sa.String(length=20), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_addresses_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_addresses")),
    )
    op.create_index(op.f("ix_addresses_user_id"), "addresses", ["user_id"], unique=False)
    # Partial unique index: at most one is_default=true row per user_id.
    # Not expressible as a plain UniqueConstraint (those can't have a
    # WHERE clause) — this is the real guard behind
    # AddressService's transactional "set as default" operation.
    op.create_index(
        "uq_addresses_one_default_per_user",
        "addresses",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_addresses_one_default_per_user", table_name="addresses")
    op.drop_index(op.f("ix_addresses_user_id"), table_name="addresses")
    op.drop_table("addresses")
    op.drop_table("partner_profiles")
    op.drop_table("customer_profiles")
