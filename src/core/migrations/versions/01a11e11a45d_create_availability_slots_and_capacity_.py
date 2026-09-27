"""create availability slots and capacity tables

Creates the Phase 7 availability/scheduling tables: `operating_hours`
and `partner_availabilities` (independent, each referencing an
existing table), then `pickup_slots`/`delivery_slots` (independent
parents referencing `service_areas`), then
`pickup_slot_reservations`/`delivery_slot_reservations` (reference the
slot tables + `users`). Hand-written to match
`core/models/{operating_hours,partner_availability,pickup_slot,
delivery_slot,pickup_slot_reservation,delivery_slot_reservation}.py`
exactly.

Revision ID: 01a11e11a45d
Revises: f04acb897ec2
Create Date: 2026-09-27 08:45:12.873100

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "01a11e11a45d"
down_revision: str | None = "f04acb897ec2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp_columns() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "operating_hours",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_area_id", sa.Uuid(), nullable=False),
        sa.Column("day_of_week", sa.String(length=10), nullable=False),
        sa.Column("opening_time", sa.Time(), nullable=False),
        sa.Column("closing_time", sa.Time(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["service_area_id"],
            ["service_areas.id"],
            name=op.f("fk_operating_hours_service_area_id_service_areas"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_operating_hours")),
        sa.UniqueConstraint(
            "service_area_id",
            "day_of_week",
            name=op.f("uq_operating_hours_service_area_id_day_of_week"),
        ),
    )

    op.create_table(
        "partner_availabilities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("partner_profile_id", sa.Uuid(), nullable=False),
        sa.Column("day_of_week", sa.String(length=10), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["partner_profile_id"],
            ["partner_profiles.id"],
            name=op.f("fk_partner_availabilities_partner_profile_id_partner_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partner_availabilities")),
        sa.UniqueConstraint(
            "partner_profile_id",
            "day_of_week",
            name=op.f("uq_partner_availabilities_partner_profile_id_day_of_week"),
        ),
    )

    for slot_table, area_table_fk in (
        ("pickup_slots", "fk_pickup_slots_service_area_id_service_areas"),
        ("delivery_slots", "fk_delivery_slots_service_area_id_service_areas"),
    ):
        op.create_table(
            slot_table,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("service_area_id", sa.Uuid(), nullable=False),
            sa.Column("slot_date", sa.Date(), nullable=False),
            sa.Column("start_time", sa.Time(), nullable=False),
            sa.Column("end_time", sa.Time(), nullable=False),
            sa.Column("capacity_unit", sa.String(length=10), nullable=False),
            sa.Column("capacity_total", sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column(
                "capacity_reserved",
                sa.Numeric(precision=10, scale=2),
                server_default=sa.text("0"),
                nullable=False,
            ),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            *_timestamp_columns(),
            sa.ForeignKeyConstraint(
                ["service_area_id"],
                ["service_areas.id"],
                name=op.f(area_table_fk),
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{slot_table}")),
            sa.UniqueConstraint(
                "service_area_id",
                "slot_date",
                "start_time",
                "end_time",
                name=op.f(f"uq_{slot_table}_area_date_start_end"),
            ),
            sa.CheckConstraint(
                "capacity_reserved <= capacity_total",
                name=op.f(f"ck_{slot_table}_capacity_within_total"),
            ),
            sa.CheckConstraint(
                "capacity_reserved >= 0",
                name=op.f(f"ck_{slot_table}_capacity_reserved_non_negative"),
            ),
        )

    for reservation_table, slot_table in (
        ("pickup_slot_reservations", "pickup_slots"),
        ("delivery_slot_reservations", "delivery_slots"),
    ):
        op.create_table(
            reservation_table,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("slot_id", sa.Uuid(), nullable=False),
            sa.Column("customer_user_id", sa.Uuid(), nullable=False),
            sa.Column("capacity_used", sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column(
                "status",
                sa.String(length=20),
                server_default=sa.text("'ACTIVE'"),
                nullable=False,
            ),
            *_timestamp_columns(),
            sa.ForeignKeyConstraint(
                ["slot_id"],
                [f"{slot_table}.id"],
                name=op.f(f"fk_{reservation_table}_slot_id_{slot_table}"),
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["customer_user_id"],
                ["users.id"],
                name=op.f(f"fk_{reservation_table}_customer_user_id_users"),
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{reservation_table}")),
        )


def downgrade() -> None:
    op.drop_table("delivery_slot_reservations")
    op.drop_table("pickup_slot_reservations")
    op.drop_table("delivery_slots")
    op.drop_table("pickup_slots")
    op.drop_table("partner_availabilities")
    op.drop_table("operating_hours")
