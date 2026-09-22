"""create identity and rbac core tables

Creates the three independent parent tables of the RBAC graph: `users`,
`roles`, `permissions`. The join tables (`user_roles`, `role_permissions`)
that reference these come in the next revision, since a foreign key can't
target a table that doesn't exist yet.

Hand-written to match `core/models/user.py`, `core/models/role.py`, and
`core/models/permission.py` exactly (reviewed rather than a raw
autogenerate dump) — see FLOW.md Phase 1 section for the design
rationale (UUID PKs, server-controlled timestamps, the
resource/action/scope permission shape).

Revision ID: 0a91544a311e
Revises:
Create Date: 2026-09-22 22:00:35.551175

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0a91544a311e"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("phone", name=op.f("uq_users_phone")),
    )

    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("name", name=op.f("uq_roles_name")),
    )

    op.create_table(
        "permissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resource", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permissions")),
        sa.UniqueConstraint(
            "resource",
            "action",
            "scope",
            name=op.f("uq_permissions_resource_action_scope"),
        ),
        sa.CheckConstraint(
            "scope IN ('OWN', 'ASSIGNED', 'ALL')", name=op.f("ck_permissions_valid_scope")
        ),
    )


def downgrade() -> None:
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("users")
