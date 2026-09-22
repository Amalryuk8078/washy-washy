"""create rbac association tables

Creates `user_roles` and `role_permissions`, the join tables linking the
parents created in the previous revision. Hand-written to match
`core/models/user_role.py` and `core/models/role_permission.py` exactly.

`ON DELETE CASCADE` on every foreign key here is intentional: deleting a
User/Role/Permission should take its now-meaningless association rows
with it, but a row in these tables never cascades back up to delete a
User/Role/Permission (FK cascade only flows parent -> child). See the
model docstrings for the full rationale.

Revision ID: e8dc958f2e5e
Revises: 0a91544a311e
Create Date: 2026-09-22 22:00:36.526865

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8dc958f2e5e"
down_revision: str | None = "0a91544a311e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_user_roles_role_id_roles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_roles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_roles")),
        sa.UniqueConstraint("user_id", "role_id", name=op.f("uq_user_roles_user_id_role_id")),
    )
    # (user_id, role_id) unique constraint above already indexes user_id
    # (leading column) — role_id needs its own index for "users with
    # this role" lookups.
    op.create_index(op.f("ix_user_roles_role_id"), "user_roles", ["role_id"], unique=False)

    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("permission_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            name=op.f("fk_role_permissions_permission_id_permissions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_role_permissions_role_id_roles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role_permissions")),
        sa.UniqueConstraint(
            "role_id",
            "permission_id",
            name=op.f("uq_role_permissions_role_id_permission_id"),
        ),
    )
    # Same reasoning as above: "roles containing this permission" filters
    # on permission_id alone, so it needs its own index.
    op.create_index(
        op.f("ix_role_permissions_permission_id"),
        "role_permissions",
        ["permission_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_role_permissions_permission_id"), table_name="role_permissions")
    op.drop_table("role_permissions")
    op.drop_index(op.f("ix_user_roles_role_id"), table_name="user_roles")
    op.drop_table("user_roles")
