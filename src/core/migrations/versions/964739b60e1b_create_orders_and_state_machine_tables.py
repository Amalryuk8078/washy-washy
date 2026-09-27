"""create orders and state machine tables

Creates the Phase 8 order tables: `orders` (references `users`,
`service_areas`, `addresses` x2, and nullably `pickup_slots`/
`delivery_slots`/`pickup_slot_reservations`/`delivery_slot_reservations`
from Phase 7), then `order_items` (references `orders`, `services`,
`materials` x2, and nullably `pricing_rules`/`material_pricing_rules`
x2 from Phase 6), then `order_status_history` (references `orders` and
`users`). Hand-written to match
`core/models/{order,order_item,order_status_history}.py` exactly,
including the two explicitly-named `order_items` foreign keys to
`material_pricing_rules` (the naming convention's derived name would
exceed PostgreSQL's 63-byte identifier limit).

Revision ID: 964739b60e1b
Revises: 01a11e11a45d
Create Date: 2026-09-27 09:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "964739b60e1b"
down_revision: str | None = "01a11e11a45d"
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
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("service_area_id", sa.Uuid(), nullable=False),
        sa.Column("pickup_address_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_address_id", sa.Uuid(), nullable=False),
        sa.Column("pickup_slot_id", sa.Uuid(), nullable=True),
        sa.Column("delivery_slot_id", sa.Uuid(), nullable=True),
        sa.Column("pickup_reservation_id", sa.Uuid(), nullable=True),
        sa.Column("delivery_reservation_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status", sa.String(length=30), server_default=sa.text("'DRAFT'"), nullable=False
        ),
        sa.Column(
            "estimated_total",
            sa.Numeric(precision=10, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("final_total", sa.Numeric(precision=10, scale=2), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["users.id"],
            name=op.f("fk_orders_customer_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["service_area_id"],
            ["service_areas.id"],
            name=op.f("fk_orders_service_area_id_service_areas"),
        ),
        sa.ForeignKeyConstraint(
            ["pickup_address_id"],
            ["addresses.id"],
            name=op.f("fk_orders_pickup_address_id_addresses"),
        ),
        sa.ForeignKeyConstraint(
            ["delivery_address_id"],
            ["addresses.id"],
            name=op.f("fk_orders_delivery_address_id_addresses"),
        ),
        sa.ForeignKeyConstraint(
            ["pickup_slot_id"],
            ["pickup_slots.id"],
            name=op.f("fk_orders_pickup_slot_id_pickup_slots"),
        ),
        sa.ForeignKeyConstraint(
            ["delivery_slot_id"],
            ["delivery_slots.id"],
            name=op.f("fk_orders_delivery_slot_id_delivery_slots"),
        ),
        sa.ForeignKeyConstraint(
            ["pickup_reservation_id"],
            ["pickup_slot_reservations.id"],
            name=op.f("fk_orders_pickup_reservation_id_pickup_slot_reservations"),
        ),
        sa.ForeignKeyConstraint(
            ["delivery_reservation_id"],
            ["delivery_slot_reservations.id"],
            name=op.f("fk_orders_delivery_reservation_id_delivery_slot_reservations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.CheckConstraint(
            "estimated_total >= 0", name=op.f("ck_orders_estimated_total_non_negative")
        ),
        sa.CheckConstraint(
            "final_total IS NULL OR final_total >= 0",
            name=op.f("ck_orders_final_total_non_negative"),
        ),
    )

    op.create_table(
        "order_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("declared_material_id", sa.Uuid(), nullable=False),
        sa.Column("verified_material_id", sa.Uuid(), nullable=True),
        sa.Column("declared_quantity", sa.Integer(), nullable=True),
        sa.Column("declared_weight_kg", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("verified_quantity", sa.Integer(), nullable=True),
        sa.Column("verified_weight_kg", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("estimated_pricing_rule_id", sa.Uuid(), nullable=True),
        sa.Column("estimated_material_pricing_rule_id", sa.Uuid(), nullable=True),
        sa.Column("estimated_line_total", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("final_pricing_rule_id", sa.Uuid(), nullable=True),
        sa.Column("final_material_pricing_rule_id", sa.Uuid(), nullable=True),
        sa.Column("final_line_total", sa.Numeric(precision=10, scale=2), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_items_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"], ["services.id"], name=op.f("fk_order_items_service_id_services")
        ),
        sa.ForeignKeyConstraint(
            ["declared_material_id"],
            ["materials.id"],
            name=op.f("fk_order_items_declared_material_id_materials"),
        ),
        sa.ForeignKeyConstraint(
            ["verified_material_id"],
            ["materials.id"],
            name=op.f("fk_order_items_verified_material_id_materials"),
        ),
        sa.ForeignKeyConstraint(
            ["estimated_pricing_rule_id"],
            ["pricing_rules.id"],
            name=op.f("fk_order_items_estimated_pricing_rule_id_pricing_rules"),
        ),
        # Explicitly shortened names -- the naming convention's derived
        # name here would exceed PostgreSQL's 63-byte identifier limit
        # (see the model's docstring).
        sa.ForeignKeyConstraint(
            ["estimated_material_pricing_rule_id"],
            ["material_pricing_rules.id"],
            name="fk_order_items_est_material_rule_id",
        ),
        sa.ForeignKeyConstraint(
            ["final_pricing_rule_id"],
            ["pricing_rules.id"],
            name=op.f("fk_order_items_final_pricing_rule_id_pricing_rules"),
        ),
        sa.ForeignKeyConstraint(
            ["final_material_pricing_rule_id"],
            ["material_pricing_rules.id"],
            name="fk_order_items_final_material_rule_id",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_items")),
        sa.CheckConstraint(
            "estimated_line_total IS NULL OR estimated_line_total >= 0",
            name=op.f("ck_order_items_estimated_line_total_non_negative"),
        ),
        sa.CheckConstraint(
            "final_line_total IS NULL OR final_line_total >= 0",
            name=op.f("ck_order_items_final_line_total_non_negative"),
        ),
    )

    op.create_table(
        "order_status_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=True),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("changed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("changed_by_role", sa.String(length=50), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_status_history_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"],
            ["users.id"],
            name=op.f("fk_order_status_history_changed_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_status_history")),
    )


def downgrade() -> None:
    op.drop_table("order_status_history")
    op.drop_table("order_items")
    op.drop_table("orders")
