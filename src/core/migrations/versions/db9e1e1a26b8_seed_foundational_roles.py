"""seed foundational roles

Seeds the four foundational business roles (see
`core/models/role.py::RoleName`). No permissions are seeded here — per
Phase 1 scope, only roles that are actually meaningful today are
created; permissions for unimplemented modules would be speculative.

Idempotent and deterministic:
- Role IDs are derived with `uuid.uuid5` from a fixed namespace + role
  name, so the same role always gets the same ID on every environment
  this migration runs against (not a random `uuid4` per run).
- The insert uses `ON CONFLICT (name) DO NOTHING`, so re-running
  `upgrade` (or applying it to a database that already has these rows)
  never creates duplicates or errors.
- `downgrade` removes exactly these four rows by name and is itself a
  no-op if they're already gone.

Revision ID: db9e1e1a26b8
Revises: e8dc958f2e5e
Create Date: 2026-09-22 22:00:37.520393

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "db9e1e1a26b8"
down_revision: str | None = "e8dc958f2e5e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLE_NAMESPACE = uuid.NAMESPACE_DNS

_FOUNDATIONAL_ROLES = [
    ("CUSTOMER", "Books and manages their own laundry orders."),
    ("LAUNDRY_PARTNER", "Fulfils orders assigned to their laundry facility."),
    ("SUPERVISOR", "Oversees day-to-day operations across partners and orders."),
    ("ADMIN", "Full platform administration."),
]


def _role_id(name: str) -> uuid.UUID:
    return uuid.uuid5(_ROLE_NAMESPACE, f"washy-washy.role.{name}")


def upgrade() -> None:
    connection = op.get_bind()
    for name, description in _FOUNDATIONAL_ROLES:
        connection.execute(
            sa.text(
                """
                INSERT INTO roles (id, name, description, is_active)
                VALUES (:id, :name, :description, true)
                ON CONFLICT (name) DO NOTHING
                """
            ),
            {"id": _role_id(name), "name": name, "description": description},
        )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("DELETE FROM roles WHERE name = ANY(:names)"),
        {"names": [name for name, _ in _FOUNDATIONAL_ROLES]},
    )
