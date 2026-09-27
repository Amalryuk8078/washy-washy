"""create pricing tables and add care adjustment

Creates the Phase 6 pricing tables `pricing_rules` (versioned base rate
per service) and `material_pricing_rules` (versioned adjustment per
material), and adds `service_materials.care_adjustment`. Hand-written
to match `core/models/{pricing_rule,material_pricing_rule,
service_material}.py` exactly.

Revision ID: f04acb897ec2
Revises: 368d5df746fb
Create Date: 2026-09-27 08:28:41.081875

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f04acb897ec2"
down_revision: str | None = "368d5df746fb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pricing_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("pricing_model", sa.String(length=20), nullable=False),
        sa.Column("base_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
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
            ["service_id"],
            ["services.id"],
            name=op.f("fk_pricing_rules_service_id_services"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pricing_rules")),
    )
    op.create_index(
        "ix_pricing_rules_service_id_effective_from",
        "pricing_rules",
        ["service_id", "effective_from"],
        unique=False,
    )
    op.create_index(
        "uq_pricing_rules_one_active_per_service",
        "pricing_rules",
        ["service_id"],
        unique=True,
        postgresql_where=sa.text("effective_to IS NULL"),
    )

    op.create_table(
        "material_pricing_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("material_id", sa.Uuid(), nullable=False),
        sa.Column("price_adjustment", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
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
            ["material_id"],
            ["materials.id"],
            name=op.f("fk_material_pricing_rules_material_id_materials"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_material_pricing_rules")),
    )
    op.create_index(
        "ix_material_pricing_rules_material_id_effective_from",
        "material_pricing_rules",
        ["material_id", "effective_from"],
        unique=False,
    )
    op.create_index(
        "uq_material_pricing_rules_one_active_per_material",
        "material_pricing_rules",
        ["material_id"],
        unique=True,
        postgresql_where=sa.text("effective_to IS NULL"),
    )

    op.add_column(
        "service_materials",
        sa.Column("care_adjustment", sa.Numeric(precision=10, scale=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("service_materials", "care_adjustment")
    op.drop_index(
        "uq_material_pricing_rules_one_active_per_material",
        table_name="material_pricing_rules",
    )
    op.drop_index(
        "ix_material_pricing_rules_material_id_effective_from",
        table_name="material_pricing_rules",
    )
    op.drop_table("material_pricing_rules")
    op.drop_index("uq_pricing_rules_one_active_per_service", table_name="pricing_rules")
    op.drop_index("ix_pricing_rules_service_id_effective_from", table_name="pricing_rules")
    op.drop_table("pricing_rules")
