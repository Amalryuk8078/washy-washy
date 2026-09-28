"""create payment, invoice, and refund tables

Creates the Phase 10 financial tables: `invoices` (references
`orders`), then `invoice_items` (references `invoices`/`order_items`),
then `payments` (references `invoices`), then `payment_attempts`/
`payment_events` (both reference `payments`), then `refunds`
(references `payments`). Hand-written to match
`core/models/{invoice,invoice_item,payment,payment_attempt,
payment_event,refund}.py` exactly.

Revision ID: a4e3ae0f131d
Revises: 3b8164c9fa11
Create Date: 2026-09-27 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a4e3ae0f131d"
down_revision: str | None = "3b8164c9fa11"
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
        "invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'DRAFT'"), nullable=False
        ),
        sa.Column("subtotal", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "tax", sa.Numeric(precision=10, scale=2), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "discount",
            sa.Numeric(precision=10, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("total", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "amount_paid",
            sa.Numeric(precision=10, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_invoices_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoices")),
        sa.UniqueConstraint("order_id", name=op.f("uq_invoices_order_id")),
        sa.CheckConstraint("total >= 0", name=op.f("ck_invoices_total_non_negative")),
        sa.CheckConstraint("amount_paid >= 0", name=op.f("ck_invoices_amount_paid_non_negative")),
        sa.CheckConstraint(
            "amount_paid <= total", name=op.f("ck_invoices_amount_paid_within_total")
        ),
    )

    op.create_table(
        "invoice_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("order_item_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            name=op.f("fk_invoice_items_invoice_id_invoices"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["order_item_id"],
            ["order_items.id"],
            name=op.f("fk_invoice_items_order_item_id_order_items"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoice_items")),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default=sa.text("'USD'"), nullable=False),
        sa.Column(
            "captured_amount",
            sa.Numeric(precision=10, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "refunded_amount",
            sa.Numeric(precision=10, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'PENDING'"), nullable=False
        ),
        sa.Column("provider_reference", sa.String(length=255), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            name=op.f("fk_payments_invoice_id_invoices"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_payments_amount_non_negative")),
        sa.CheckConstraint(
            "captured_amount >= 0 AND captured_amount <= amount",
            name=op.f("ck_payments_captured_within_amount"),
        ),
        sa.CheckConstraint(
            "refunded_amount >= 0 AND refunded_amount <= captured_amount",
            name=op.f("ck_payments_refunded_within_captured"),
        ),
    )

    op.create_table(
        "payment_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("provider_reference", sa.String(length=255), nullable=True),
        sa.Column("failure_reason", sa.String(length=500), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_payment_attempts_payment_id_payments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_attempts")),
    )

    op.create_table(
        "payment_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_payment_events_payment_id_payments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_events")),
        sa.UniqueConstraint("provider_event_id", name=op.f("uq_payment_events_provider_event_id")),
    )

    op.create_table(
        "refunds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'PENDING'"), nullable=False
        ),
        sa.Column("provider_reference", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_refunds_payment_id_payments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refunds")),
        sa.CheckConstraint("amount > 0", name=op.f("ck_refunds_amount_positive")),
    )


def downgrade() -> None:
    op.drop_table("refunds")
    op.drop_table("payment_events")
    op.drop_table("payment_attempts")
    op.drop_table("payments")
    op.drop_table("invoice_items")
    op.drop_table("invoices")
