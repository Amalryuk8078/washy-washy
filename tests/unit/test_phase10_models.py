"""Offline (no database) tests for the Phase 10 payment/invoice/refund
model definitions.
"""

from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from core.models import (
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    Payment,
    PaymentAttempt,
    PaymentEvent,
    PaymentStatus,
    Refund,
    RefundStatus,
)


def test_mappers_configure_without_error() -> None:
    configure_mappers()


def test_invoice_status_matches_spec() -> None:
    assert {s.value for s in InvoiceStatus} == {
        "DRAFT",
        "FINALIZED",
        "VOID",
        "PAID",
        "PARTIALLY_PAID",
    }


def test_payment_status_matches_spec() -> None:
    assert {s.value for s in PaymentStatus} == {
        "PENDING",
        "AUTHORIZED",
        "CAPTURED",
        "FAILED",
        "VOIDED",
        "CANCELLED",
        "PARTIALLY_PAID",
    }


def test_refund_status_values() -> None:
    assert {s.value for s in RefundStatus} == {"PENDING", "PROCESSED", "FAILED"}


def test_invoice_unique_per_order_and_cascades() -> None:
    unique_columns = {
        tuple(c.name for c in con.columns)
        for con in Invoice.__table__.constraints
        if isinstance(con, UniqueConstraint)
    }
    assert ("order_id",) in unique_columns

    for constraint in Invoice.__table__.constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            for fk in constraint.elements:
                assert fk.ondelete == "CASCADE"


def test_invoice_defaults_draft_and_zero_paid() -> None:
    assert Invoice.__table__.c.status.default.arg == InvoiceStatus.DRAFT.value
    assert Invoice.__table__.c.amount_paid.default.arg == Decimal("0")


def test_invoice_check_constraints() -> None:
    check_names = {
        con.name for con in Invoice.__table__.constraints if isinstance(con, CheckConstraint)
    }
    assert "ck_invoices_total_non_negative" in check_names
    assert "ck_invoices_amount_paid_non_negative" in check_names
    assert "ck_invoices_amount_paid_within_total" in check_names


def test_invoice_item_has_no_updated_at() -> None:
    columns = set(InvoiceItem.__table__.c.keys())
    assert "created_at" in columns
    assert "updated_at" not in columns


def test_invoice_item_order_item_id_is_a_plain_reference() -> None:
    for constraint in InvoiceItem.__table__.constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            for fk in constraint.elements:
                if fk.parent.name == "order_item_id":
                    assert fk.ondelete is None
                if fk.parent.name == "invoice_id":
                    assert fk.ondelete == "CASCADE"


def test_payment_defaults_pending_and_zero_amounts() -> None:
    assert Payment.__table__.c.status.default.arg == PaymentStatus.PENDING.value
    assert Payment.__table__.c.captured_amount.default.arg == Decimal("0")
    assert Payment.__table__.c.refunded_amount.default.arg == Decimal("0")
    assert Payment.__table__.c.currency.default.arg == "USD"


def test_payment_check_constraints() -> None:
    check_names = {
        con.name for con in Payment.__table__.constraints if isinstance(con, CheckConstraint)
    }
    assert "ck_payments_amount_non_negative" in check_names
    assert "ck_payments_captured_within_amount" in check_names
    assert "ck_payments_refunded_within_captured" in check_names


def test_payment_attempt_has_updated_at() -> None:
    # Deliberately mutable (TimestampMixin), unlike PaymentEvent below --
    # an attempt resolves from PENDING to a terminal state in place.
    columns = set(PaymentAttempt.__table__.c.keys())
    assert "updated_at" in columns


def test_payment_event_is_append_only_and_unique_per_provider_event() -> None:
    columns = set(PaymentEvent.__table__.c.keys())
    assert "updated_at" not in columns

    unique_columns = {
        tuple(c.name for c in con.columns)
        for con in PaymentEvent.__table__.constraints
        if isinstance(con, UniqueConstraint)
    }
    assert ("provider_event_id",) in unique_columns


def test_refund_defaults_pending_and_amount_must_be_positive() -> None:
    assert Refund.__table__.c.status.default.arg == RefundStatus.PENDING.value
    check_names = {
        con.name for con in Refund.__table__.constraints if isinstance(con, CheckConstraint)
    }
    assert "ck_refunds_amount_positive" in check_names
