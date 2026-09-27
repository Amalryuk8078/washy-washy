# Washy Washy Backend

FastAPI backend foundation for **Washy Washy**, a laundry-service platform.
This repository is currently at **Phase 8 — Orders / State Machine**,
built on Phase 0–7 (HTTP skeleton, auth, RBAC, users/profiles/addresses/
service areas, catalog, pricing, availability/slots/capacity). Phase 8
adds `Order`/`OrderItem`/`OrderStatusHistory` and the full 24-state
order lifecycle, with every transition validated against a central
graph and executed via the same **race-free atomic `UPDATE`** pattern
Phase 7 used for slot capacity — verified under real concurrent load,
not just sequential-logic tests. A plain customer may submit/cancel
their own order; the rest of the pipeline requires staff (`ADMIN`/
`SUPERVISOR`/`LAUNDRY_PARTNER`). An admin role-management API
(`/roles`, `/users/{id}/roles`) was added as a small addendum between
Phase 4 and 5, closing a gap those phases explicitly deferred. See the
Roadmap.

## Overview

```text
Customer Flutter App
Laundry Partner Flutter App        Apache APISIX        FastAPI Backend        PostgreSQL
Admin Web                    →                     →                    →      Redis
Supervisor Operations                                                          Celery
```

Only the FastAPI backend + PostgreSQL exist at this stage. APISIX, Redis,
and Celery are introduced in later phases.

## Architecture

A single FastAPI application (**modular monolith**, not microservices),
internally layered as:

```text
HTTP Request
     ↓
Route            — HTTP concerns only: params, body, status codes, deps
     ↓
Controller       — thin request-level orchestration
     ↓
Service          — business/use-case behavior
     ↓
Repository       — persistence (SELECT/INSERT/UPDATE/DELETE)
     ↓
Core Model       — SQLAlchemy table models
     ↓
PostgreSQL
```

Pydantic schemas sit at the API boundary (`Request → Schema → Route → ...`).

**Two packages, one dependency direction:**

```text
src/core/          shared infrastructure: db engine/session, base model,
                    security primitives, logging, exceptions, shared deps,
                    Alembic migrations. Independent of washy_washy.

src/washy_washy/    the service package: routes, controllers, services,
                    repositories, schemas, constants, utils.
                    Depends on core, never the other way around.
```

`core` never imports `washy_washy`. Database table models live only in
`core/models/` — service packages do not define their own model modules.

## Folder structure

```text
washy-washy-backend/
├── pyproject.toml
├── alembic.ini
├── Dockerfile
├── docker-compose.yml
├── .env.example
│
├── src/
│   ├── core/
│   │   ├── config/          # CoreSettings (db url, jwt secret, log level)
│   │   ├── database/        # Base (+ naming convention), async engine/session
│   │   ├── models/          # mixins.py + User, Role, Permission, UserRole,
│   │   │                    # RolePermission, CustomerProfile, PartnerProfile,
│   │   │                    # Address, ServiceArea, ServiceAreaPostalCode,
│   │   │                    # Service, Material, ServiceMaterial,
│   │   │                    # PartnerCapability, PricingRule,
│   │   │                    # MaterialPricingRule, OperatingHours,
│   │   │                    # PartnerAvailability, PickupSlot, DeliverySlot,
│   │   │                    # PickupSlotReservation, DeliverySlotReservation,
│   │   │                    # Order, OrderItem, OrderStatusHistory
│   │   ├── security/        # password hashing, JWT encode/decode
│   │   ├── dependencies/    # get_db_session
│   │   ├── logging/         # structured logging setup
│   │   ├── middleware/      # request-id correlation middleware
│   │   ├── exceptions/      # AppException family + FastAPI handlers
│   │   └── migrations/      # Alembic env.py, versions/ (9 revisions so far)
│   │
│   └── washy_washy/
│       ├── main.py          # FastAPI app construction
│       ├── __main__.py      # `python -m washy_washy`
│       ├── config.py        # service-level Settings(CoreSettings)
│       ├── api/v1/routes/   # health, auth, users, customers, addresses,
│       │                    # service_areas, roles, catalog, pricing,
│       │                    # availability, orders
│       ├── api/v1/controllers/  # same set
│       ├── dependencies/    # auth.py: get_current_user
│       │                    # rbac.py: require_role, require_permission,
│       │                    # require_any_role
│       ├── constants/       # error codes / messages (AUTH_*, profile/
│       │                    # service-area/role/catalog/pricing/
│       │                    # availability/order conflict codes)
│       ├── schemas/         # common, auth, profile, address, service_area,
│       │                    # role, catalog, pricing, availability, orders
│       ├── repositories/    # user, role, permission, user_role,
│       │                    # role_permission, customer_profile,
│       │                    # partner_profile, address, service_area,
│       │                    # service, material, service_material,
│       │                    # partner_capability, pricing_rule,
│       │                    # material_pricing_rule, operating_hours,
│       │                    # partner_availability, pickup_slot,
│       │                    # delivery_slot, pickup_slot_reservation,
│       │                    # delivery_slot_reservation, order, order_item,
│       │                    # order_status_history
│       ├── services/        # auth_service, rbac_service, profile_service,
│       │                    # address_service, service_area_service,
│       │                    # catalog_service, partner_capability_service,
│       │                    # pricing_service, availability_service,
│       │                    # order_service, order_state_service
│       ├── docs/            # openapi.py (tags + custom_openapi),
│       │                    # swagger_ui.py (branded /docs, /redoc)
│       ├── static/          # swagger-custom.css, favicon.svg
│       └── utils/
│
└── tests/
    ├── conftest.py
    ├── test_health.py
    ├── test_import.py
    ├── unit/                # test_database_foundation, test_alembic_wiring,
    │                        # test_rbac_models, test_auth_tokens_and_schemas,
    │                        # test_phase4_models, test_phase5_models,
    │                        # test_phase6_models, test_phase7_models,
    │                        # test_phase8_models (no DB required)
    ├── integration/         # test_database_connection, test_user_identity,
    │                        # test_rbac_associations, test_auth,
    │                        # test_rbac_runtime, test_profiles,
    │                        # test_addresses, test_service_areas,
    │                        # test_catalog, test_pricing, test_availability,
    │                        # test_availability_concurrency, test_orders,
    │                        # test_order_state_machine
    │                        # (require a live, migrated DB)
    └── api/                 # test_auth_routes, test_protected_routes_require_auth
                              # (HTTP-level, validation-only, no DB)
```

## Requirements

- Python 3.12+
- PostgreSQL 16 (or via Docker)
- Docker + Docker Compose (optional, for containerized run)

## Environment setup

```bash
python -m venv .venv
```

Activate it:

```bash
# Linux/macOS
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\activate
```

Copy the example environment file and adjust values as needed:

```bash
cp .env.example .env
```

Required variables fail fast on startup if missing (`DATABASE_URL`,
`JWT_SECRET`). See `.env.example` for the full list:

```env
APP_NAME=Washy Washy API
SERVICE_NAME=washy-washy
APP_ENV=development
DEBUG=true

API_V1_PREFIX=/api/v1

SERVICE_HOST=0.0.0.0
SERVICE_PORT=8000

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=washy_washy
POSTGRES_USER=washy
POSTGRES_PASSWORD=change_me

DATABASE_URL=postgresql+asyncpg://washy:change_me@localhost:5432/washy_washy

JWT_SECRET=change_me
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

CORS_ORIGINS=http://localhost:3000,http://localhost:5173

LOG_LEVEL=INFO
```

## Installation

```bash
pip install -e ".[dev]"
```

This installs the app (in editable mode, `src/` layout) plus dev tools
(`pytest`, `pytest-asyncio`, `httpx`, `ruff`).

## Running locally

Start PostgreSQL (Docker is the easiest path — see below — or use a local
install), then:

```bash
uvicorn washy_washy.main:app --reload
```

or:

```bash
python -m washy_washy
```

- Swagger UI (branded): http://localhost:8000/docs
- ReDoc (branded): http://localhost:8000/redoc
- Raw OpenAPI schema: http://localhost:8000/openapi.json
- Health: http://localhost:8000/api/v1/health

## Running with Docker

```bash
docker compose up --build
alembic upgrade head   # first time only — or: docker exec <api container> python -m alembic upgrade head
```

This starts `postgres` and `api` only. Redis, Celery, and APISIX are not
part of this stage and are added in later phases.

The app is reachable on **http://localhost:8080** (Swagger:
`/docs`, health: `/api/v1/health/ready`) — the `api` service publishes
container port `8000` on host port `8080`, not `8000`, to avoid colliding
with other projects' compose stacks that also default to `8000` on a
shared dev machine. Adjust the `ports:` mapping in `docker-compose.yml`
if that's not a concern on your machine.

If `docker compose`/`docker info` fail with something like `open
//./pipe/dockerDesktopLinuxEngine: The system cannot find the file
specified`, Docker Desktop's engine isn't actually running — restarting
the Docker Desktop *app* alone often doesn't fix this, because it
doesn't reset WSL2's network state. Try, in order: fully quit Docker
Desktop, run `wsl --shutdown`, then relaunch Docker Desktop and wait
~30s.

## Local PostgreSQL without Docker (fallback)

If Docker Desktop isn't available, run a real, local PostgreSQL instead —
no admin rights required, via the
[`postgresql-binaries`](https://pypi.org/project/postgresql-binaries/)
PyPI package (portable Postgres binaries, dev/CI use only — production
still runs through `docker-compose.yml`'s `postgres` service):

```bash
pip install postgresql-binaries
python -c "import postgresql_binaries as pb; print(pb.bin())"   # locate the extracted bin/ dir
```

Then, using that `bin/` path (`$PGBIN` below) and a data directory of your
choice (`.pgdata/` at the repo root is `.gitignore`d for exactly this):

```bash
# one-time: initialize the cluster + create the app role/database
$PGBIN/initdb -D .pgdata -U washy --pwfile=<(echo change_me)
$PGBIN/pg_ctl -D .pgdata -l .pgdata/pg.log start
$PGBIN/createdb -h localhost -p 5432 -U washy washy_washy

# every session
$PGBIN/pg_ctl -D .pgdata -l .pgdata/pg.log start
alembic upgrade head

# when done
$PGBIN/pg_ctl -D .pgdata stop
```

Point `.env`'s `DATABASE_URL`/`POSTGRES_*` at `localhost:5432` with
whatever user/password/db name you initialized above, same as the
Docker path.

## Database architecture

`core/database/base.py` defines the single shared declarative `Base`.
Every model (once domain models exist) inherits from it; no other `Base`
is ever created. `Base.metadata` carries a deterministic naming
convention (`pk_`, `fk_`, `uq_`, `ck_`, `ix_` prefixes) so every
Alembic-generated constraint/index name is stable and reviewable instead
of relying on PostgreSQL's own autogenerated names.

`core/models/mixins.py` provides the two pieces of reusable
infrastructure new domain models opt into:

- `UUIDPrimaryKeyMixin` — a `Uuid` primary key generated application-side
  (`default=uuid.uuid4`) before insert. No sequential/guessable IDs, and
  API clients never supply their own primary key.
- `TimestampMixin` — timezone-aware `created_at`/`updated_at` populated
  by PostgreSQL itself (`server_default=func.now()`, `onupdate=func.now()`
  on `updated_at`), not by application code. Neither column is ever
  accepted as input from a client.

A future model looks like:

```python
from core.database.base import Base
from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    ...
```

There is intentionally no universal soft-delete or audit-field mixin —
those have per-domain semantics (some entities are soft-deletable,
transactional records like orders/payments generally are not) and will
be added explicitly where each domain needs them, not forced onto every
table.

The async engine (`core/database/engine.py`) and session factory
(`core/database/session.py`) are unchanged from Phase 0. The transaction
boundary stays at the controller/service layer: repositories receive an
injected `AsyncSession`, never commit independently, and never create
their own session.

## Identity & RBAC models (Phase 1B–1D)

Five tables, forming `User -> UserRole -> Role -> RolePermission ->
Permission`:

```text
User            id, email (unique), phone (nullable, unique), password_hash,
                first_name, last_name (nullable), is_active, is_verified,
                created_at, updated_at
```

`User` has **no** `role`/`role_id` column — roles are assigned through
`UserRole` so one user can hold several. It also has no profile fields;
customer/partner profile data is a later phase's model, kept separate
from identity.

**Email** is normalized (stripped, lowercased) by the repository layer
(`washy_washy/repositories/user_repo.py::normalize_email`) before every
write and lookup, so `Amal@Example.com` and `amal@example.com` collide as
the same identity. The `users.email` column then carries a plain UNIQUE
constraint over that already-normalized value — no PostgreSQL `citext`
extension needed for something the application already guarantees.

**Phone** is nullable with a plain UNIQUE constraint; PostgreSQL allows
any number of NULLs alongside at most one occurrence of each non-NULL
value, which is exactly the desired "unique when present" behavior.

```text
Role            id, name (unique), description, is_active,
                created_at, updated_at
```

Foundational role names (`core/models/role.py::RoleName`, not DB-enforced
— `name` stays a plain string so a new role can be added without a
migration): `CUSTOMER`, `LAUNDRY_PARTNER`, `SUPERVISOR`, `ADMIN`. Seeded
idempotently by the `seed foundational roles` migration.

```text
Permission      id, resource, action, scope, description,
                created_at, updated_at
                unique (resource, action, scope)
                check (scope IN ('OWN', 'ASSIGNED', 'ALL'))
```

A permission is `resource + action + scope`. Design decision (documented
in `core/models/permission.py::PermissionScope`): some actions already
encode scope in their name (`READ_OWN`, `READ_ASSIGNED`, `READ_ALL`,
`UPDATE_OWN`, `UPDATE_ASSIGNED`, `UPDATE_ALL`) — for those, `scope` is
always set to match the suffix exactly rather than being a second,
possibly-contradictory source of truth. Actions with no scope in their
name (`CREATE`, `ASSIGN`, `REASSIGN`, `APPROVE`, `CANCEL`, `OVERRIDE`) are
inherently administrative/global in this system, so `scope` is `ALL`.
This keeps `scope` always populated (never NULL), which is what lets
`(resource, action, scope)` work as a real uniqueness constraint — a
NULL-able `scope` would let PostgreSQL silently accept duplicate
`(resource, action, NULL)` rows, since NULLs never compare equal under a
standard UNIQUE constraint. No permissions are seeded — only roles that
are actually meaningful today are; permissions for unimplemented modules
would be speculative.

```text
UserRole            id, user_id -> users.id, role_id -> roles.id, created_at
                     unique (user_id, role_id)

RolePermission       id, role_id -> roles.id, permission_id -> permissions.id, created_at
                     unique (role_id, permission_id)
```

Both are pure association tables: **immutable once created** (no
`updated_at` — an assignment exists or it doesn't, never edited in
place), and both foreign keys are `ON DELETE CASCADE`. That cascade only
flows parent → association: deleting a `User`/`Role`/`Permission` removes
its now-meaningless grants, but deleting a `UserRole`/`RolePermission`
row can never delete the `User`/`Role`/`Permission` it references. The
database's `(user_id, role_id)` / `(role_id, permission_id)` unique
constraints — not an application-level existence check — are the real
guard against a duplicate grant under concurrent requests; repository
`assign_*` methods do not pre-check and let a duplicate surface as an
`IntegrityError`.

Indexes beyond the primary/unique keys: `ix_user_roles_role_id` and
`ix_role_permissions_permission_id`, added because the composite unique
constraints only efficiently serve lookups on their *leading* column
(`user_id`, `role_id` respectively) — "users with this role" and "roles
containing this permission" queries filter on the trailing column alone
and need their own index.

Repositories: `user_repo.py`, `role_repo.py`, `permission_repo.py`,
`user_role_repo.py`, `role_permission_repo.py` under
`washy_washy/repositories/`. All persistence-only — no FastAPI, no
`HTTPException`, no JWT, no authorization decisions, no commits (they
`flush()`; the caller owns the transaction boundary).

## Authentication (Phase 2)

```text
POST /api/v1/auth/register   -> AuthService.register()   -> UserRepository
POST /api/v1/auth/login      -> AuthService.login()       -> verify_password() + issue tokens
POST /api/v1/auth/refresh    -> AuthService.refresh()     -> decode + reissue access token
```

`washy_washy/services/auth_service.py::AuthService` holds the workflow;
`washy_washy/api/v1/controllers/auth.py` is the thin orchestration layer
(it's the only controller that commits — `register` is the only write);
`washy_washy/api/v1/routes/auth.py` is HTTP-only.

- **Registration**: normalizes the email, rejects a duplicate
  email/phone (`ConflictException` / `AUTH_EMAIL_ALREADY_EXISTS` /
  `AUTH_PHONE_ALREADY_EXISTS`), hashes the password
  (`core.security.hash_password`), creates the `User`. Never returns
  `password`/`password_hash` — the response is always
  `washy_washy/schemas/auth.py::UserResponse`, which doesn't have those
  fields.
- **Password policy**: minimum 8 characters, enforced by a Pydantic
  validator on `RegisterRequest` (`schemas/auth.py::MIN_PASSWORD_LENGTH`)
  — deliberately simple, no invented complexity rules.
- **Login**: looks up by (normalized) email, verifies the password, and
  checks `is_active`. **The same `AUTH_INVALID_CREDENTIALS` error/message
  covers both "no such user" and "wrong password"** — this is
  intentional, so a caller can never learn which one was wrong (see
  `AuthService.login`'s comment).
- **Tokens**: `create_access_token`/`create_refresh_token`
  (`core/security/security.py`, unchanged primitives) embed only
  `sub` (user id), `type` (`access`/`refresh`), `iat`, `exp` — never the
  full user object, never anything sensitive.
- **Refresh**: `POST /auth/refresh` only accepts a `type: refresh` token
  (an access token is rejected with `AUTH_REFRESH_TOKEN_REQUIRED`),
  re-verifies the user is still active, and issues a new access token.
  **No refresh-token rotation/persistent storage** — out of scope until
  a design explicitly needs it (would mean a new database table).
- **`get_current_user`** (`washy_washy/dependencies/auth.py`): a FastAPI
  dependency — not yet wired to any protected route, since Phase 2 adds
  no protected endpoints — that reads `Authorization: Bearer <token>`,
  decodes it, requires `type: access`, and loads the (active) `User`.
  Only resolves *who* the caller is; it makes no role/permission
  decisions — that's `require_role`/`require_permission` in Phase 3.
- **Errors**: `core.security.security.decode_token_strict` (new,
  additive — the original `decode_token` is untouched) raises
  `TokenExpiredError`/`TokenInvalidError` distinctly, so
  `AUTH_TOKEN_EXPIRED` and `AUTH_TOKEN_INVALID` are genuinely
  distinguishable, not the same generic failure. All `AUTH_*` codes live
  in `washy_washy/constants/error_codes.py`/`error_messages.py`, raised
  via the existing `UnauthorizedException`/`ConflictException` family —
  no new exception types.

**Dependency fix (discovered by this phase, not introduced by it):**
Phase 0 pinned `bcrypt>=4.1.0`, which is incompatible with
`passlib==1.7.4` (unmaintained since 2020) — passlib's own internal
bcrypt self-test raises `ValueError: password cannot be longer than 72
bytes` on first use under bcrypt 4.1+'s stricter validation, so
`hash_password`/`verify_password` were completely broken before this
phase (nothing had called them yet). Fixed by pinning
`bcrypt>=4.0.0,<4.1` in `pyproject.toml`; verified working after
reinstalling.

## RBAC runtime (Phase 3)

Turns Phase 1's RBAC data model (`User -> UserRole -> Role ->
RolePermission -> Permission`) into actual authorization decisions.

- **`washy_washy/services/rbac_service.py::RBACService`** — the one
  place authorization SQL lives; routes/dependencies never write their
  own role/permission queries. `get_user_roles`, `get_user_permissions`,
  `has_role(user_id, role_name)`, `has_permission(user_id, resource,
  action, scope)`, plus `assign_role`/`remove_role` (thin wrappers over
  `UserRoleRepository`, kept here so RBAC has one service-level API
  surface rather than callers reaching into repositories directly).
  **Only active roles ever grant anything** — an inactive role is
  treated as if it were never assigned, even though the underlying
  `UserRole` row still exists (matches the `is_active` lifecycle model
  from Phase 1, not a deletion).
- **`washy_washy/dependencies/rbac.py::require_role`/`require_permission`**
  — dependency *factories*: `require_role("ADMIN")` and
  `require_permission("orders", "READ_ALL", "ALL")` each return a
  FastAPI dependency. Both build on `get_current_user` (401 if
  unauthenticated), then call `RBACService` (403 `ForbiddenException` if
  the role/permission isn't granted). Authorization is never a
  hard-coded check like `if user.role == "ADMIN"` — it always queries
  the real Role/Permission tables. At the time this phase was built, no
  route used either dependency yet — Phase 4 is what gives `require_role`
  its first real caller (`POST /service-areas`, `ADMIN`-only); see below.
- Usage, exactly as it ended up being used in Phase 4:
  ```python
  @router.post(
      "",
      dependencies=[Depends(require_role(RoleName.ADMIN.value))],
  )
  async def create_service_area(...): ...
  ```

## Users, profiles, addresses & service areas (Phase 4)

The first phase with real protected HTTP endpoints — `get_current_user`
(Phase 2) and `require_role` (Phase 3) finally have callers.

```text
GET  /api/v1/users/me           -> current user's own identity (reuses auth's UserResponse)
GET  /api/v1/customers/me       -> current user's own CustomerProfile
POST /api/v1/customers/me       -> create it
GET  /api/v1/addresses          -> current user's own addresses
POST /api/v1/addresses          -> create one
GET|PATCH|DELETE /api/v1/addresses/{id}   -> must be the caller's own
POST /api/v1/addresses/{id}/set-default   -> atomically flips the default
GET  /api/v1/service-areas      -> any authenticated caller
POST /api/v1/service-areas      -> ADMIN role only (require_role's first real use)
```

- **`CustomerProfile`/`PartnerProfile`** — one per user (`user_id` unique
  FK), holding only domain-specific fields (`display_name`;
  `business_name`/`contact_phone`/`status`) — never `email`/
  `password_hash`/`is_active`. Profile existence is independent of role
  assignment: creating a `CustomerProfile` doesn't grant the `CUSTOMER`
  role, and vice versa. `PartnerProfile.status` (`PENDING`/`ACTIVE`/
  `SUSPENDED`/`INACTIVE`) is a business-onboarding lifecycle, distinct
  from `User.is_active` (an auth-account flag) — full onboarding
  *workflow* is Phase 9's job, this phase only adds the field. Only
  `/customers/me` is wired to an endpoint; `PartnerProfile`'s
  model/repository/service exist but aren't exposed yet (Phase 4's own
  spec doesn't list a `/partners/me` route) — same "build the piece,
  don't force a premature endpoint" pattern as Phase 2/3.
- **`Address`** — a user can have several; never stored on `User`
  itself. Ownership is enforced in `AddressService`, not at the route
  layer: fetching/updating/deleting an address that exists but belongs
  to someone else raises `NotFoundException`, not `ForbiddenException`
  — deliberately, so a caller never learns whether an ID they don't own
  exists at all (the same security posture as login's generic
  invalid-credentials error). At most one address per user may have
  `is_default = true`, enforced by a **partial unique index**
  (`WHERE is_default = true`) — not just application logic.
  `AddressService.set_default_address` flips the old default off and
  flushes *before* setting the new one on, in two separate flushes, so
  the two updates are never both `true` at the same instant (the partial
  index would reject that collision even within the same transaction).
- **`ServiceArea`/`ServiceAreaPostalCode`** — deliberately two tables,
  not a `postal_code` column on `ServiceArea` itself: one area can cover
  many postal codes, and a different boundary representation (city,
  polygon, ...) could be added later without reworking `ServiceArea`. A
  postal code belongs to at most one area (`postal_code` is globally
  unique in the child table) so "which area covers this address" is
  never ambiguous. **No direct `User <-> ServiceArea` relationship
  table** — a deliberate design decision, not an oversight: serviceability
  is a property of a *location* (a postal code), not of a user, who can
  have addresses in several areas at once.
  `ServiceAreaService.is_postal_code_serviceable(postal_code)` is the
  informational "is this covered?" check — it does **not** gate address
  creation (a customer can save an address anywhere; availability/slot
  enforcement is Phase 7's job).

**Real bug found and fixed by this phase**: creating an address with
`is_default=true` does an INSERT then, inside the same request, an
UPDATE (the default-flip). Without `eager_defaults` configured on the
ORM mappers, the UPDATE's server-computed `updated_at` (via
`onupdate=func.now()`) came back "expired" rather than refreshed —
reading it afterward inside a *synchronous* `AddressResponse.model_validate(...)`
(exactly what the real controller does) raised
`MissingGreenlet: greenlet_spawn has not been called`, a 500 in
practice, even though the row itself was correctly written and
committed. Fixed by adding `__mapper_args__ = {"eager_defaults": True}`
to `core/models/mixins.py::CreatedAtMixin` (inherited by every model,
`TimestampMixin` included) so RETURNING is always used on INSERT/UPDATE,
keeping server-computed columns populated immediately after flush
regardless of what touches the object next. Verified live via `uvicorn`
(reproduced the 500, applied the fix, confirmed 201 + correct default-flip
on a second request) and via a regression test
(`tests/integration/test_addresses.py::test_create_default_address_response_serializes_without_error`)
that was confirmed to fail without the fix before being left in place.

## Admin role management API

Closes a gap Phase 3/4 explicitly left open: an admin API for granting/
revoking roles, rather than reaching into `UserRoleRepository` directly
(which is still how tests bootstrap the very first ADMIN grant — there's
no other way in, by design: nothing self-elevates).

```text
GET    /api/v1/roles                         -> assignable (active) roles
GET    /api/v1/users/{user_id}/roles         -> a user's roles
POST   /api/v1/users/{user_id}/roles         -> grant {"role_name": "..."}
DELETE /api/v1/users/{user_id}/roles/{name}  -> revoke
```

All four require the `ADMIN` role (router-level
`dependencies=[Depends(require_role(RoleName.ADMIN.value))]` —
`washy_washy/api/v1/routes/roles.py`). Logic lives in
`RBACService.{list_assignable_roles,get_user,get_user_by_email,
grant_role_by_name,revoke_role_by_name}`. Granting a role an admin
already has, or revoking one they don't have, is a clean `409`/`404`
(existence pre-checked; the underlying `(user_id, role_id)` unique
constraint still guards the race). **An admin cannot revoke their own
`ADMIN` role** (`422 CANNOT_REMOVE_OWN_ADMIN_ROLE`) — otherwise the last
admin could accidentally lock everyone, including themselves, out of
role management; another admin can still revoke it for them.

## Catalog (Phase 5)

```text
GET/POST /api/v1/services                              -> list (any authenticated caller) / create (ADMIN)
GET/PATCH /api/v1/services/{id}                          -> get / {"is_active": bool} (ADMIN)
GET/POST /api/v1/services/{id}/materials                 -> compatible materials / set compatibility (ADMIN)
DELETE   /api/v1/services/{id}/materials/{material_id}   -> remove compatibility (ADMIN)
GET/POST /api/v1/materials                              -> list / create (ADMIN)
GET/PATCH /api/v1/materials/{id}                          -> get / activate/deactivate (ADMIN)
GET      /api/v1/materials/{id}/services                 -> compatible services
```

- **`Service`/`Material`** — plain string `name` (unique), not an enum:
  the business adds new ones over time without a migration. No
  `ServiceCategory`/hierarchy — the example services (Wash, Dry Clean,
  Iron, ...) don't naturally group into anything, and unused hierarchy
  is worse than none (add one later if a real grouping need shows up).
- **`ServiceMaterial`** — the (service, material) compatibility row,
  carrying optional `care_instructions`/`max_temperature_celsius`. Uses
  `TimestampMixin` (mutable), not the association-table pattern from
  Phase 1 (`CreatedAtMixin` only) — care requirements are real content
  that gets corrected over time, not a pure yes/no grant.
  `CatalogService.set_compatibility` creates or updates in place.
- **Customer-declared vs. facility-verified material** (mentioned in the
  Phase 5 spec) is deliberately *not* modeled here — that distinction
  belongs to an `OrderItem` in Phase 8, once orders exist. This table is
  just the reference vocabulary both of those future fields will point at.
- **`PartnerCapability`** — which services a partner can perform.
  Capability only; capacity/scheduling is Phase 7's job. Modeled as an
  immutable grant (`CreatedAtMixin`, like `UserRole`/`RolePermission`),
  unlike `ServiceMaterial`. **No API endpoint yet** — `PartnerCapabilityService`
  exists and is tested, but Phase 5's own endpoint list (`5.7`) doesn't
  ask for one; same "build the piece, don't force a premature endpoint"
  pattern as `PartnerProfile` in Phase 4.

## Pricing (Phase 6)

```text
GET/POST /api/v1/services/{id}/pricing    -> current rate / set a new version (ADMIN)
GET/POST /api/v1/materials/{id}/pricing   -> current adjustment / set a new version (ADMIN)
POST     /api/v1/pricing/estimate         -> price breakdown for a service+material+quantity
```

Formula: `total = base + material_adjustment + care_adjustment +
quantity_charge + rush_charge + delivery_charge + tax - discount`,
where `subtotal = base + material_adjustment + care_adjustment +
quantity_charge`. `PricingService.calculate_price` always returns every
component (`PriceBreakdown`), never just the total.

- **`PricingRule`/`MaterialPricingRule`** — each row *is* a version:
  setting a new rate closes the current active row (`effective_to =
  now()`) and inserts a new one; a rate change never rewrites an
  existing row's price. At most one active (`effective_to IS NULL`) row
  per service/material, enforced by a partial unique index — same
  pattern as `Address`'s one-default-per-user index (Phase 4). Two
  separate flushes (close, then insert), not one, so the two rows are
  never simultaneously active mid-flush.
- **`pricing_model`** (`PER_ITEM`/`PER_KG`/`PER_BAG`/`BASE_PLUS_WEIGHT`/
  `CUSTOM`, plain string, not DB-enforced) determines how `unit_price`
  combines with the caller's `quantity`/`weight_kg`/`custom_charge` —
  passing the wrong one for the active model is a clean
  `422 QUANTITY_REQUIRED`/`WEIGHT_REQUIRED`, not a silent zero.
- **Rush charge, delivery charge, tax, and discount are caller-supplied
  inputs to the calculation, not stored catalog rates** — the spec's own
  input list for the pricing service treats them this way; a generic
  "global tax rate" table would be speculative before a real policy
  need shows up (e.g. once Phase 10 payments/invoices need one).
- **`ServiceMaterial.care_adjustment`** (new column) is *not*
  independently versioned — it's a smaller modifier attached directly
  to the care requirement it corresponds to, edited in place like the
  rest of that row, not a rate significant enough to warrant version
  history of its own.
- **No separate "estimate" vs. "final" method** — `calculate_price` is
  the same call either way; Phase 8's order flow will call it once with
  customer-declared material/quantity (estimate) and again with
  facility-verified values after inspection (final). Persisting *which*
  rule version produced a stored price, so a later rate change can't
  alter an existing order's total, is Phase 8's job once `Order`/
  `OrderItem` exist — `PriceBreakdown` already carries the rule ids a
  snapshot would need.

## Availability / Slots / Capacity (Phase 7)

```text
GET/POST /api/v1/service-areas/{id}/operating-hours    -> per-day open/close time (ADMIN writes)
GET/POST /api/v1/partners/{id}/availability             -> per-day partner hours (ADMIN writes)
GET/POST /api/v1/service-areas/{id}/pickup-slots         -> dated capacity slots (ADMIN writes)
GET/POST /api/v1/service-areas/{id}/delivery-slots       -> same, separate table
POST     /api/v1/pickup-slots/{id}/reservations          -> book (any authenticated caller)
DELETE   /api/v1/pickup-slots/reservations/{id}          -> cancel own reservation
POST     /api/v1/delivery-slots/{id}/reservations        -> book
DELETE   /api/v1/delivery-slots/reservations/{id}        -> cancel own reservation
```

- **`OperatingHours`/`PartnerAvailability`** — one row per
  `(service_area_id | partner_profile_id, day_of_week)`, edited in place
  (not versioned — a wrong closing time isn't worth keeping history of,
  unlike a `PricingRule`). `close_day` sets `is_active = false` rather
  than deleting the row.
- **`PickupSlot`/`DeliverySlot`** — deliberately two separate tables,
  not one table with a direction flag. Each carries `capacity_total`/
  `capacity_reserved` (`Numeric(10,2)`) plus two `CHECK` constraints
  (`capacity_reserved <= capacity_total`, `>= 0`) as a last-resort
  database guard.
- **Race-free capacity reservation is the core mechanism of this
  phase**: `try_reserve_capacity` does the availability check and the
  increment in one atomic conditional `UPDATE`:
  ```sql
  UPDATE pickup_slots
  SET capacity_reserved = capacity_reserved + :amount
  WHERE id = :slot_id
    AND is_active = true
    AND capacity_reserved + :amount <= capacity_total
  ```
  If no row matches (already full, or a concurrent request got there
  first), the affected-row count is `0` and the booking is rejected with
  `422 SLOT_CAPACITY_EXCEEDED` — there is no read-then-write window for
  two concurrent requests to race past a stale check. **Verified under
  genuine concurrency**, not just sequential-logic assertions:
  `tests/integration/test_availability_concurrency.py` fires 10 truly
  concurrent booking attempts (separate database connections +
  `asyncio.gather`) against a slot with room for exactly 3 — exactly 3
  succeed, and `capacity_reserved` never exceeds `capacity_total`.
- **Cancellation** releases capacity via the mirrored `release_capacity`
  and is idempotent — cancelling an already-cancelled reservation is a
  silent no-op, so it can never double-free capacity.
- **Ownership** on cancel follows `AddressService`'s posture: a
  reservation belonging to someone else raises `404 NotFoundException`,
  never `403` — a caller can't learn whether an ID they don't own
  exists.
- **Reservations deliberately carry no `partner_profile_id`/`order_id`**
  — a reservation is against the slot's capacity, not a specific
  partner (partner assignment is Phase 9) or order (`Order` doesn't
  exist until Phase 8).
- **Known, documented scope gap**: `has_capable_partner(service_id)`
  checks only whether *any* partner anywhere holds a service's
  capability — it is not scoped to the service area being booked, and
  it is **not enforced** inside the booking flow. A correctly
  area-scoped check needs a `PartnerProfile <-> ServiceArea`
  association that doesn't exist yet (that link belongs to Phase 9).
  Documented in `availability_service.py`'s module docstring rather than
  silently glossed over.

## Orders / State Machine (Phase 8)

```text
POST   /api/v1/orders                            -> create (as customer)
GET    /api/v1/orders                            -> list own orders
GET    /api/v1/orders/{id}                       -> own order, or staff
GET    /api/v1/orders/{id}/history               -> own order's audit trail, or staff
POST   /api/v1/orders/{id}/transition            -> generic move (ownership/role checked inside)
POST   /api/v1/orders/{id}/schedule-pickup       -> books a Phase 7 slot + moves to PICKUP_SCHEDULED
POST   /api/v1/orders/{id}/items/{item_id}/itemize   -> ADMIN/SUPERVISOR/LAUNDRY_PARTNER only
POST   /api/v1/orders/{id}/finalize-price        -> ADMIN/SUPERVISOR/LAUNDRY_PARTNER only
```

24-state lifecycle (`DRAFT` through `COMPLETED`, plus exception states
like `PAYMENT_FAILED`/`CANCELLED`), with the legal transition graph and
its authorization rules centralized in `order_state_service.py` — no
route or controller hard-codes "if status == X."

- **`Order` is this project's first genuinely significant business
  record**, which drove a deliberate foreign-key split: `customer_id`
  cascades with the user (ownership), but the service area/addresses/
  slots/reservations it references do not (`ON DELETE RESTRICT`) — a
  customer deleting an old address, or an admin removing a slot, fails
  loudly instead of silently erasing an order's history.
- **`OrderItem`** keeps declared vs. verified material/quantity/weight
  genuinely separate (inspection never overwrites the customer's
  original declaration) and snapshots both an *estimated* and a
  *final* pricing-rule id + line total — exactly what `PricingRule`'s
  own Phase 6 docstring said Phase 8 would need. Because those rule
  rows are immutable once closed, a later rate change can never
  retroactively alter what an item already charged.
- **Concurrency-safe transitions**, the same pattern as Phase 7's slot
  capacity: `OrderRepository.try_transition` is one atomic
  `UPDATE ... WHERE status = :from_status` statement, not a
  read-then-write. Two concurrent requests moving the same order never
  both "win" — the loser gets a clean `409 ORDER_STATE_CONFLICT`.
  Verified under real concurrent load: 8 simultaneous attempts to
  cancel the *same* order all race for one atomic slot; exactly one
  succeeds and the order ends with exactly one cancellation recorded in
  its history, regardless of how the 8 attempts actually interleaved.
- **Two authorization tiers**: a plain customer may submit
  (`DRAFT -> PENDING_PAYMENT`) and cancel their own order from most
  pre-pickup states; everything else (`PICKUP_ASSIGNED` onward)
  requires staff (`ADMIN`/`SUPERVISOR`/`LAUNDRY_PARTNER`, via the new
  `require_any_role` dependency). A disallowed-for-this-caller
  transition is `403`; a nonexistent/not-your-order is `404`.
- **Not implemented, by design**: no partner-to-order assignment
  (Phase 9), no real payment gateway behind `PENDING_PAYMENT ->
  CONFIRMED` (Phase 10 — currently a plain staff-triggered flip), no
  delivery-slot scheduling workflow (`delivery_slot_id`/
  `delivery_reservation_id` columns exist per the spec's field list,
  unpopulated until Phase 9).

## Database setup / Alembic

Migrations are owned by `core` (models live in `core/models/`); the
`washy_washy` service package does not have its own migrations folder.
`core/migrations/env.py` imports `core.models` (not `washy_washy.main`)
to populate `target_metadata`, so generating/running migrations never
starts the FastAPI app and never needs it to.

```bash
alembic revision --autogenerate -m "message"
alembic upgrade head
alembic downgrade -1
alembic heads      # list migration heads (no DB connection required)
alembic current    # show the DB's applied revision (requires a reachable DB)
```

The application never calls `Base.metadata.create_all(...)` on startup —
schema changes are managed exclusively through Alembic migrations.

Current revision chain (oldest to newest):

```text
0a91544a311e  create identity and rbac core tables   (users, roles, permissions)
e8dc958f2e5e  create rbac association tables         (user_roles, role_permissions)
db9e1e1a26b8  seed foundational roles                (idempotent data seed)
3587faef9553  create profile and address tables       (customer_profiles, partner_profiles, addresses)
9ad4f2884494  create service area tables              (service_areas, service_area_postal_codes)
368d5df746fb  create catalog tables                   (services, materials, service_materials,
                                                        partner_capabilities)
f04acb897ec2  create pricing tables + care_adjustment (pricing_rules, material_pricing_rules,
                                                        service_materials.care_adjustment)
01a11e11a45d  create availability, slots, and capacity (operating_hours, partner_availabilities,
                                                        pickup_slots, delivery_slots,
                                                        pickup_slot_reservations,
                                                        delivery_slot_reservations)
964739b60e1b  create orders and state machine tables  (orders, order_items,
                                                        order_status_history, head)
```

All nine were hand-written to match the models exactly (reviewed rather
than a raw `--autogenerate` dump, per the project's migration-safety
rule). `alembic upgrade head` has been run end-to-end against a real
PostgreSQL instance (both a local install and, separately, the
`docker-compose` `postgres` container) — schema, seeded roles, and every
table/index/constraint verified by querying the database directly, plus
the full `pytest` suite (300 tests) passing with zero skips against it.
The newest revision's full `upgrade`/`downgrade`/`upgrade` round-trip
was also run and verified (all 3 Phase 8 tables dropped cleanly on
downgrade, recreated identically on re-upgrade) — see "Running tests"
below.

## API documentation (Swagger / ReDoc)

`/docs` and `/redoc` are **not** FastAPI's stock pages — `main.py` sets
`docs_url=None, redoc_url=None` and replaces them with routes from
`washy_washy/docs/swagger_ui.py` that serve the same swagger-ui-dist/
ReDoc assets plus:

- `washy_washy/static/swagger-custom.css` — a Washy Washy–branded skin
  (brand color tokens, rounded/shadowed operation blocks, restyled
  buttons/inputs), including a `prefers-color-scheme: dark` variant.
  Layered on top of the stock CDN CSS via an extra `<link>`, never
  replacing it.
- `washy_washy/static/favicon.svg` — a small droplet mark used as the
  favicon for both pages.
- A branded header (logo + title + `Swagger`/`Reference`/`OpenAPI JSON`
  links) injected into the page body.
- `washy_washy/docs/openapi.py::custom_openapi` — builds and caches
  `app.openapi_schema` with real tag metadata (`TAGS_METADATA`: `root`,
  `health`, `auth`, `users`, `customers`, `addresses`, `service-areas` —
  each with a one-line description shown above that tag's operations in
  both UIs) and a top-level description that documents the `{success,
  message, data}` / `{success, message, code, data}` response envelope
  once, instead of repeating it per endpoint.

Both routes are `include_in_schema=False` (they don't appear as
operations in the schema they render) and static assets are served from
`/static` via `StaticFiles`. Since Phase 4, most operations now show a
locked-padlock "Authorize" requirement in both UIs — FastAPI adds the
`HTTPBearer` security scheme to an operation's schema automatically once
it actually depends on `get_current_user`, which is now true for
everything except `/`, `/health*`, and `/auth/register|login|refresh`.

## Running tests

```bash
pytest
```

Tests hit the app through the ASGI transport (`httpx.ASGITransport`) — no
separately running server is required for API tests.

Everything under `tests/unit/` and `tests/api/` runs without a database
(`tests/api/` hits real HTTP routes via the ASGI transport, but only the
request-validation/token-decoding paths that never touch PostgreSQL).
Everything under `tests/integration/` needs a real, migrated PostgreSQL
instance (`docker compose up postgres`, or see "Local PostgreSQL without
Docker" above, then `alembic upgrade head`) and **skips itself cleanly**
(does not fail) when one isn't reachable, or when the tables haven't been
migrated yet — so `pytest` alone is always self-contained whether or not
a database is up. Each integration test runs inside its own transaction
that's rolled back on teardown, so they never leave rows behind — except
`test_availability_concurrency.py` and `test_order_state_machine.py`'s
concurrency test, which deliberately use independent database
connections (a genuine race needs separate connections, not one
connection's savepoints) and clean up manually in a `finally` block.
Verified end-to-end against a real PostgreSQL instance: **300 passed, 0
skipped, 0 failed** (up from 265 as of Phase 7) — reproducibly, from a
cold shell with nothing pre-exported.
(`tests/conftest.py`'s `DATABASE_URL`/`JWT_SECRET` fallback only applies
when no `.env` exists — it used to apply unconditionally via
`os.environ.setdefault`, which shadowed a real `.env`'s password and
made every integration test silently skip in any shell that didn't
already happen to have `DATABASE_URL` exported. Fixed; see FLOW.md's
changelog for the full story.)

`pytest.ini_options` sets `asyncio_default_fixture_loop_scope = "session"`
and `asyncio_default_test_loop_scope = "session"` — deliberately, not the
pytest-asyncio default of a fresh event loop per test function.
`core/database/engine.py`'s `get_engine()`/`get_session_factory()` are
`@lru_cache` singletons (matching production, where one event loop runs
for the process's lifetime), and asyncpg connections are bound to the
loop that created them; a per-test loop breaks the cached connection pool
on the second test that touches the database (`RuntimeError: Task ...
attached to a different loop` / `'NoneType' object has no attribute
'send'`) — only visible once tests actually ran against a live database,
not from `ruff`/unit tests alone.

`get_current_user`, `require_role`, and `require_permission` are all
exercised in `tests/integration/{test_auth,test_rbac_runtime}.py` by
calling them directly as plain async functions — no phase so far has
wired a protected route to hang an HTTP-level test off of.

## Running Ruff

```bash
ruff check .
```

## Development conventions

- **Routes** stay thin: HTTP concerns only, delegate to controllers/services.
- **Controllers** orchestrate a request; no SQL, no deep business rules.
- **Services** own business behavior and are independently unit-testable;
  they receive dependencies rather than reaching for globals.
- **Repositories** own persistence, receive an injected `AsyncSession`,
  never create their own session, and never raise HTTP exceptions —
  they return `None`/empty results and let the service decide what that
  means (e.g. raise `NotFoundException`).
- **Transactions** have a clear boundary: controller/service coordinates
  multiple repository calls, then commits once.
- **Models** live only in `core/models/`, inherit the single shared
  `Base`, and are never duplicated per service package.
- **Errors** use the shared `AppException` family (`core/exceptions`) and
  the stable codes in `washy_washy/constants/error_codes.py`; responses
  always follow the `{success, message, data}` / `{success, message,
  code, data}` envelope in `washy_washy/schemas/common.py`.

## Roadmap

This repository intentionally stops after Phase 0. Planned phases:

```text
Phase 0   FastAPI Foundation
Phase 1A  Database Foundation (Base, naming convention, UUID/timestamp mixins,
          async Alembic env)
Phase 1B  User / Identity model
Phase 1C  Role / Permission models
Phase 1D  UserRole / RolePermission associations
Phase 2   Authentication (register/login/refresh, JWT, get_current_user)
Phase 3   RBAC runtime (require_role/require_permission)
Phase 4   Users / Profiles / Addresses / Service Areas
Phase 5   Catalog + Services + Materials
Phase 6   Pricing Engine
Phase 7   Availability + Slots + Capacity
Phase 8   Orders + State Machine                                        ← you are here
Phase 9   Partner Operations
Phase 10  Payments + Invoices + Refunds
Phase 11  Redis + Celery
Phase 12  APISIX + etcd
Phase 13  Flutter Integration
Phase 14  Production / AWS
```

Phase 8 deliberately stops at orders: no partner-to-order assignment
(Phase 9), no real payment gateway behind `PENDING_PAYMENT ->
CONFIRMED` (Phase 10 — currently a plain staff-triggered status flip),
and no delivery-slot scheduling workflow (the columns exist per the
spec's field list, unpopulated). Payments are not started.
