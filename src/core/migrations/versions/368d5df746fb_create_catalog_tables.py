"""create catalog tables

Creates the Phase 5 catalog: `services` and `materials` (independent
parents), then `service_materials` (references both) and
`partner_capabilities` (references `services` and the existing
`partner_profiles`). Hand-written to match
`core/models/{service,material,service_material,partner_capability}.py`
exactly.

Revision ID: 368d5df746fb
Revises: 9ad4f2884494
Create Date: 2026-09-27 08:11:42.750163

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "368d5df746fb"
down_revision: str | None = "9ad4f2884494"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_services")),
        sa.UniqueConstraint("name", name=op.f("uq_services_name")),
    )

    op.create_table(
        "materials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_materials")),
        sa.UniqueConstraint("name", name=op.f("uq_materials_name")),
    )

    op.create_table(
        "service_materials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("material_id", sa.Uuid(), nullable=False),
        sa.Column("care_instructions", sa.String(length=500), nullable=True),
        sa.Column("max_temperature_celsius", sa.Integer(), nullable=True),
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
            name=op.f("fk_service_materials_material_id_materials"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            name=op.f("fk_service_materials_service_id_services"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_materials")),
        sa.UniqueConstraint(
            "service_id",
            "material_id",
            name=op.f("uq_service_materials_service_id_material_id"),
        ),
    )
    op.create_index(
        op.f("ix_service_materials_material_id"),
        "service_materials",
        ["material_id"],
        unique=False,
    )

    op.create_table(
        "partner_capabilities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("partner_profile_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["partner_profile_id"],
            ["partner_profiles.id"],
            name=op.f("fk_partner_capabilities_partner_profile_id_partner_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            name=op.f("fk_partner_capabilities_service_id_services"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partner_capabilities")),
        sa.UniqueConstraint(
            "partner_profile_id",
            "service_id",
            name=op.f("uq_partner_capabilities_partner_profile_id_service_id"),
        ),
    )
    op.create_index(
        op.f("ix_partner_capabilities_service_id"),
        "partner_capabilities",
        ["service_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_partner_capabilities_service_id"), table_name="partner_capabilities")
    op.drop_table("partner_capabilities")
    op.drop_index(op.f("ix_service_materials_material_id"), table_name="service_materials")
    op.drop_table("service_materials")
    op.drop_table("materials")
    op.drop_table("services")
