"""add partner operations tables and order assignment columns

Creates the Phase 9 partner-operations tables: `partner_facilities`
(references `partner_profiles`/`service_areas` — the
`PartnerProfile <-> ServiceArea` link Phase 7 deferred to this phase),
then adds `orders.assigned_facility_id`/`pickup_operator_user_id`/
`delivery_operator_user_id` (referencing `partner_facilities`/`users`),
then adds `order_items.condition_notes`/`damage_reported`, then creates
`order_assignment_history` (references `orders`/`users`). Hand-written
to match `core/models/{partner_facility,order,order_item,
order_assignment_history}.py` exactly.

Revision ID: 3b8164c9fa11
Revises: 964739b60e1b
Create Date: 2026-09-27 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3b8164c9fa11"
down_revision: str | None = "964739b60e1b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "partner_facilities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("partner_profile_id", sa.Uuid(), nullable=False),
        sa.Column("service_area_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("address_line_1", sa.String(length=255), nullable=False),
        sa.Column("address_line_2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=False),
        sa.Column("postal_code", sa.String(length=20), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("daily_capacity", sa.Numeric(precision=10, scale=2), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["partner_profile_id"],
            ["partner_profiles.id"],
            name=op.f("fk_partner_facilities_partner_profile_id_partner_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["service_area_id"],
            ["service_areas.id"],
            name=op.f("fk_partner_facilities_service_area_id_service_areas"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partner_facilities")),
        sa.UniqueConstraint(
            "partner_profile_id",
            "name",
            name=op.f("uq_partner_facilities_partner_profile_id_name"),
        ),
    )

    op.add_column("orders", sa.Column("assigned_facility_id", sa.Uuid(), nullable=True))
    op.add_column("orders", sa.Column("pickup_operator_user_id", sa.Uuid(), nullable=True))
    op.add_column("orders", sa.Column("delivery_operator_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_orders_assigned_facility_id_partner_facilities"),
        "orders",
        "partner_facilities",
        ["assigned_facility_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_orders_pickup_operator_user_id_users"),
        "orders",
        "users",
        ["pickup_operator_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_orders_delivery_operator_user_id_users"),
        "orders",
        "users",
        ["delivery_operator_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("order_items", sa.Column("condition_notes", sa.String(length=500), nullable=True))
    op.add_column(
        "order_items",
        sa.Column("damage_reported", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    op.create_table(
        "order_assignment_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_role", sa.String(length=20), nullable=False),
        sa.Column("previous_assignee_id", sa.Uuid(), nullable=True),
        sa.Column("new_assignee_id", sa.Uuid(), nullable=True),
        sa.Column("changed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_assignment_history_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"],
            ["users.id"],
            name=op.f("fk_order_assignment_history_changed_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_assignment_history")),
    )


def downgrade() -> None:
    op.drop_table("order_assignment_history")

    op.drop_column("order_items", "damage_reported")
    op.drop_column("order_items", "condition_notes")

    op.drop_constraint(
        op.f("fk_orders_delivery_operator_user_id_users"), "orders", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("fk_orders_pickup_operator_user_id_users"), "orders", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("fk_orders_assigned_facility_id_partner_facilities"), "orders", type_="foreignkey"
    )
    op.drop_column("orders", "delivery_operator_user_id")
    op.drop_column("orders", "pickup_operator_user_id")
    op.drop_column("orders", "assigned_facility_id")

    op.drop_table("partner_facilities")
