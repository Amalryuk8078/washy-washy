# Washy Washy Backend — Flow & Architecture

> **Living document.** This file must be updated whenever the code's logic,
> layering, or folder structure changes (new domain module, new layer,
> renamed package, new external service, new phase started, etc.). Treat a
> structural PR as incomplete until this file reflects it. Keep the
> "Current status" and "Changelog" sections at the bottom current.

## 1. What this is

FastAPI backend for **Washy Washy**, a laundry-service platform. Single
**modular monolith** (not microservices). Currently at **Phase 7 —
Availability / Slots / Capacity**, built on Phase 0–6 (HTTP skeleton,
auth, RBAC, users/profiles/addresses/service areas, catalog, pricing).
Phase 7 adds operating hours, partner availability, and pickup/delivery
slot booking with race-free capacity reservation: `PickupSlot`/
`DeliverySlot` each carry a `capacity_total`/`capacity_reserved` pair
guarded by an atomic conditional `UPDATE` (no `SELECT FOR UPDATE`, no
Redis) so concurrent bookings can never overbook a slot, and
`PickupSlotReservation`/`DeliverySlotReservation` record who booked
how much. An admin role-management API was added as a small addendum
between Phase 4 and 5, closing a gap those phases explicitly deferred.
This environment's database/migrations/Docker have all been verified
end-to-end against a real PostgreSQL (265/265 tests passing) and
`/docs`/`/redoc` carry Washy Washy branding — see §6e–§6j and the
changelog. Orders/payments are not yet implemented.

Target system context (only FastAPI + PostgreSQL exist today; the rest are
future phases):

```text
Customer Flutter App
Laundry Partner Flutter App     →   Apache APISIX   →   FastAPI Backend   →   PostgreSQL
Admin Web                                                                     Redis
Supervisor Operations                                                        Celery
```

## 2. Two packages, one dependency direction

```text
src/core/          shared infrastructure — db engine/session, declarative
                    Base, security primitives, logging, exceptions, shared
                    FastAPI dependencies, Alembic migrations.
                    Knows nothing about washy_washy.

src/washy_washy/    the actual service — routes, controllers, services,
                    repositories, schemas, constants, utils.
                    Depends on core. core never imports washy_washy.
```

Rule: **all SQLAlchemy models live only in `core/models/`**. Service
packages never define their own model modules, so there is one migration
history and one source of truth for the schema.

## 3. Request flow (layered)

```text
HTTP Request
     │
     ▼
Route            src/washy_washy/api/v1/routes/*.py
                  HTTP concerns only — path, method, request/response
                  schema, status codes, declares its Depends(...).
     │
     ▼
Controller        src/washy_washy/api/v1/controllers/*.py
                  Thin request-level orchestration. Calls one or more
                  services, shapes the result into a schema. No SQL,
                  no deep business rules.
     │
     ▼
Service            src/washy_washy/services/*  (empty until a domain lands)
                  Business/use-case logic. Independently unit-testable.
                  Receives dependencies (e.g. AsyncSession, repos) rather
                  than reaching for globals.
     │
     ▼
Repository          src/washy_washy/repositories/*  (empty until a domain
                  needs persistence)
                  Owns SELECT/INSERT/UPDATE/DELETE. Receives an injected
                  AsyncSession, never creates its own. Never raises HTTP
                  exceptions — returns None/empty and lets the service
                  decide (e.g. raise NotFoundException).
     │
     ▼
Core Model          src/core/models/*.py
                  SQLAlchemy table models, all inheriting core.database.
                  base.Base.
     │
     ▼
PostgreSQL
```

Transactions: the controller/service coordinates multiple repository calls
and commits once — there is no per-repository commit.

Pydantic schemas sit at the API boundary in both directions
(`Request body → Schema → Route` and `Route → Schema → Response`).

## 4. Concrete example today: health check

The only fully wired vertical slice right now.

```text
GET /api/v1/health/ready
  → washy_washy/api/v1/routes/health.py :: ready()
      - Depends(get_db_session)  [core/dependencies/database.py]
      → washy_washy/api/v1/controllers/health.py :: get_readiness(db_session)
          → _check_postgres(): SELECT 1 via the injected AsyncSession
      ← {"status": "ok"|"degraded", "checks": {"postgres": bool}}
  ← SuccessResponse(message=..., data=...)
```

Also: `GET /api/v1/health` and `/health/live` → `get_liveness()` (no DB
touch, just `{"status": "ok"}`).

Router wiring: `washy_washy/api/v1/__init__.py` builds `api_v1_router` and
includes `routes/health.py`'s router; `washy_washy/main.py` mounts
`api_v1_router` under `settings.api_v1_prefix` (`/api/v1`).

## 5. App construction (`washy_washy/main.py`)

`create_app()` is the single wiring point — the only place allowed to
assemble the FastAPI app:

1. Load `Settings` via `get_settings()` (cached).
2. `lifespan`: on startup, calls `configure_logging(settings.log_level)`.
   It does **not** touch the database — no `Base.metadata.create_all(...)`
   and no connection probe. Schema changes are Alembic's job only.
3. Instantiate `FastAPI(title=..., lifespan=...)`.
4. Add `RequestIDMiddleware` (outermost of the two below — added first).
5. Add `CORSMiddleware` using `settings.cors_origins_list`.
6. `register_exception_handlers(app)`.
7. Mount `api_v1_router` at `settings.api_v1_prefix`.
8. Define root `GET /` → points to `/docs` and the health endpoint.
9. Module-level `app = create_app()` — this is the ASGI object Uvicorn
   serves (`washy_washy.main:app`).

Entry points that reach this `app`:
- `python -m washy_washy` → `washy_washy/__main__.py` → `uvicorn.run("washy_washy.main:app", ...)`
- `uvicorn washy_washy.main:app --reload` (dev)
- `Dockerfile` CMD → same target, host `0.0.0.0:8000`

## 6. Cross-cutting concerns

### Settings (`core/config/settings.py`, `washy_washy/config.py`)
- `CoreSettings` (core) — infra-only config: `app_env`, `debug`, Postgres
  fields, `database_url` (required, fails fast if missing), JWT fields
  (`jwt_secret` required), `log_level`. Reads `.env`.
- `Settings(CoreSettings)` (washy_washy) — adds service-level config:
  `app_name`, `service_name`, `api_v1_prefix`, `service_host/port`,
  `cors_origins` (+ `cors_origins_list` property). Same `.env` file.
- Both are `@lru_cache`d singletons — `get_core_settings()` / `get_settings()`.
  `core` code should call `get_core_settings()`; `washy_washy` code calls
  `get_settings()` (which has everything `CoreSettings` has, plus its own).

### Database — engine & session (`core/database/`)
- `base.py` — the single `Base(DeclarativeBase)`. Every model must inherit
  from this; never create a second `Base` elsewhere. `Base.metadata` is a
  `MetaData` instance carrying a **deterministic naming convention** (see
  §6a) so every constraint/index Alembic generates has a stable,
  reviewable name.
- `engine.py` — `get_engine()`, cached `AsyncEngine` via
  `create_async_engine(settings.database_url, echo=debug, pool_pre_ping=True)`.
- `session.py` — `get_session_factory()`, cached `async_sessionmaker`
  (`expire_on_commit=False`, `autoflush=False`).
- `core/dependencies/database.py` — `get_db_session()`: the FastAPI
  dependency (`Depends(get_db_session)`) that yields an `AsyncSession` per
  request and closes it via the `async with` context.

### 6a. Model infrastructure (`core/models/`) — Phase 1A

The reusable foundation every domain model builds on:

- `core/models/base.py` — thin re-export of `core.database.base.Base`
  (the one and only `Base`; not a second declaration).
- `core/models/__init__.py` — re-exports `Base`, `CreatedAtMixin`,
  `TimestampMixin`, `UUIDPrimaryKeyMixin`, and every model
  (`User`, `Role`, `RoleName`, `Permission`, `PermissionScope`,
  `UserRole`, `RolePermission`). This is also the module Alembic's
  `env.py` imports (`from core.models import *`) to register every model
  on `Base.metadata` before autogeneration runs — new model modules must
  be imported here as they're added.
- `core/models/mixins.py`:
  - `UUIDPrimaryKeyMixin` — `id: Mapped[uuid.UUID]` using SQLAlchemy's
    `Uuid(as_uuid=True)` type (maps to PostgreSQL's native `uuid` column),
    `default=uuid.uuid4` generated application-side before insert. API
    clients never supply a primary key; IDs are never sequential/guessable.
  - `CreatedAtMixin` — timezone-aware `created_at` only
    (`server_default=func.now()`), for rows that are never edited in
    place (the RBAC association tables — see §6b).
  - `TimestampMixin(CreatedAtMixin)` — adds `updated_at` (also
    `server_default=func.now()`, plus `onupdate=func.now()`). Both
    columns populated by PostgreSQL, not application code — never
    accepted as input from an API client, never a naive/local
    `datetime.now()`.
- **No universal `SoftDeleteMixin` and no universal audit-field mixin**
  (`created_by`/`updated_by`/...) exist, deliberately. Deletion and audit
  semantics differ per domain (e.g. `Service`/`Material` are plausibly
  soft-deletable; `Order`/`Payment`/`Invoice` generally are not) and will
  be added explicitly per model in later phases, not forced onto every
  table from a shared base. `User`/`Role` use `is_active` for lifecycle
  instead of a `deleted_at` column.
- Naming convention on `Base.metadata` (defined in `core/database/base.py`):
  ```python
  {
      "ix": "ix_%(column_0_label)s",
      "uq": "uq_%(table_name)s_%(column_0_name)s",
      "ck": "ck_%(table_name)s_%(constraint_name)s",
      "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
      "pk": "pk_%(table_name)s",
  }
  ```
- A model follows this shape:
  ```python
  from core.database.base import Base
  from core.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


  class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
      __tablename__ = "users"
      ...
  ```
- Money columns (once financial models exist) must use `NUMERIC`/`Decimal`,
  never `FLOAT`/`DOUBLE` — noted here as a standing rule for later phases,
  not something implemented yet.

### 6b. Identity & RBAC models (`core/models/{user,role,permission,user_role,role_permission}.py`) — Phase 1B–1D

Five tables forming `User -> UserRole -> Role -> RolePermission ->
Permission`. All use `UUIDPrimaryKeyMixin`; `User`/`Role`/`Permission`
also use `TimestampMixin`, while `UserRole`/`RolePermission` use only
`CreatedAtMixin` (association rows are immutable — created or removed,
never edited in place, so there's no `updated_at` to maintain).

- **`User`** (`users`): `email` (unique), `phone` (nullable, unique),
  `password_hash`, `first_name`, `last_name` (nullable), `is_active`
  (default `true`), `is_verified` (default `false`). No `role`/`role_id`
  column — roles come from `UserRole` so a user can hold several. No
  domain profile fields (Customer/Partner profile models are a later
  phase, kept separate from identity).
  - **Email normalization** happens in
    `washy_washy/repositories/user_repo.py::normalize_email` (strip +
    lowercase) before every write/lookup — `Amal@Example.com` and
    `amal@example.com` collide as the same identity. `users.email` then
    only needs a plain UNIQUE constraint over the already-normalized
    value; no PostgreSQL `citext` extension.
  - `phone`'s plain UNIQUE constraint already allows unlimited `NULL`s
    alongside at most one occurrence of each non-`NULL` value — exactly
    "unique when present," no special handling needed.
- **`Role`** (`roles`): `name` (unique), `description`, `is_active`
  (default `true`). `core/models/role.py::RoleName` is a `StrEnum` of the
  four foundational names (`CUSTOMER`, `LAUNDRY_PARTNER`, `SUPERVISOR`,
  `ADMIN`) for seed data/tests to reference — **not** DB-enforced;
  `roles.name` stays a plain string so a new role can be added without a
  migration.
- **`Permission`** (`permissions`): `resource`, `action`, `scope`,
  `description`; `UNIQUE (resource, action, scope)`;
  `CHECK (scope IN ('OWN','ASSIGNED','ALL'))`.
  - **Design decision** (`core/models/permission.py::PermissionScope`):
    the action vocabulary already encodes scope in its name for some
    actions (`READ_OWN`, `READ_ASSIGNED`, `READ_ALL`, `UPDATE_OWN`,
    `UPDATE_ASSIGNED`, `UPDATE_ALL`). Rather than let `scope` be an
    independently-settable field that could contradict that suffix,
    `scope` for those actions must always equal the suffix exactly.
    Actions with no scope in their name (`CREATE`, `ASSIGN`, `REASSIGN`,
    `APPROVE`, `CANCEL`, `OVERRIDE`) are inherently
    administrative/global here, so `scope = ALL`. This keeps `scope`
    always populated (never `NULL`), which is what lets
    `(resource, action, scope)` work as a real uniqueness constraint — a
    nullable `scope` would let PostgreSQL silently accept duplicate
    `(resource, action, NULL)` rows, since `NULL`s never compare equal
    under a standard `UNIQUE` constraint.
  - No permissions are seeded (only roles are) — permissions for
    unimplemented modules would be speculative.
- **`UserRole`** (`user_roles`): `user_id -> users.id`,
  `role_id -> roles.id`, `UNIQUE (user_id, role_id)`, extra index
  `ix_user_roles_role_id`.
- **`RolePermission`** (`role_permissions`): `role_id -> roles.id`,
  `permission_id -> permissions.id`,
  `UNIQUE (role_id, permission_id)`, extra index
  `ix_role_permissions_permission_id`.
  - Both association tables' foreign keys are `ON DELETE CASCADE` —
    intentional and one-directional: deleting a
    `User`/`Role`/`Permission` removes its now-meaningless grants, but
    deleting an association row can never cascade back up to delete the
    parent (FK cascade only flows parent → child).
  - The extra indexes exist because the composite `UNIQUE` constraints
    only efficiently serve lookups on their *leading* column (`user_id`,
    `role_id` respectively) — "users with this role" / "roles containing
    this permission" queries filter on the *trailing* column alone.
  - The database constraints — not an application-level existence check
    — are the real guard against a duplicate grant under concurrent
    requests: `assign_role`/`assign_permission` in the repositories below
    do not pre-check and let a duplicate surface as `IntegrityError`.

Repositories (`washy_washy/repositories/`, all persistence-only — inject
an `AsyncSession`, never commit, never raise `HTTPException`, never make
authorization decisions):
`user_repo.py` (`UserRepository` + module-level `normalize_email`),
`role_repo.py` (`RoleRepository`), `permission_repo.py`
(`PermissionRepository`), `user_role_repo.py` (`UserRoleRepository`),
`role_permission_repo.py` (`RolePermissionRepository`).

### 6c. Authentication (`washy_washy/{services/auth_service,api/v1/routes/auth,api/v1/controllers/auth,dependencies/auth,schemas/auth}.py`) — Phase 2

```text
POST /api/v1/auth/register
  → routes/auth.py :: register()          [HTTP only: schema, status code]
      → controllers/auth.py :: register()  [orchestration]
          → AuthService.register()          [normalize email, reject dupes, hash password]
              → UserRepository.create()      [flush]
          ← User
      controller: await db_session.commit()  — the only auth endpoint that writes
  ← SuccessResponse(data=UserResponse)  — never password/password_hash

POST /api/v1/auth/login
  → AuthService.login(): get_by_email → verify_password → check is_active
                          → create_access_token + create_refresh_token
  ← SuccessResponse(data=TokenResponse)  — no commit, no writes

POST /api/v1/auth/refresh
  → AuthService.refresh(): decode_or_raise (type must be "refresh")
                            → get_active_user(sub) → create_access_token
  ← SuccessResponse(data={"access_token": ...})

Authorization: Bearer <access_token>  (dependency, not yet wired to any route)
  → dependencies/auth.py :: get_current_user()
      HTTPBearer(auto_error=False) → decode_or_raise (type must be "access")
      → AuthService.get_active_user(sub) → UserRepository.get_by_id()
  ← User (or raises UnauthorizedException)
```

- **Registration**: `AuthService.register` normalizes the email
  (`user_repo.normalize_email`), rejects a duplicate email/phone
  (`ConflictException` + `AUTH_EMAIL_ALREADY_EXISTS`/
  `AUTH_PHONE_ALREADY_EXISTS`), hashes the password
  (`core.security.hash_password`, unchanged primitive), and creates the
  `User` via `UserRepository.create` (flush only). The controller is the
  transaction boundary — it's the only auth controller method that calls
  `db_session.commit()`, since it's the only one that writes.
- **Password policy**: `washy_washy/schemas/auth.py::RegisterRequest`
  enforces `MIN_PASSWORD_LENGTH = 8` via a Pydantic `field_validator` —
  deliberately simple, no invented complexity rules. Malformed emails are
  rejected by the same file's `_validate_email_format` (a plain regex,
  not `pydantic.EmailStr`, to avoid adding the `email-validator`
  dependency for a sanity check this simple).
- **Login**: **the same `AUTH_INVALID_CREDENTIALS` failure covers both
  "no such user" and "wrong password"** — deliberate, so a caller can
  never learn which one was wrong. `is_active` is checked after password
  verification, with its own distinct `AUTH_USER_INACTIVE`.
- **Tokens**: `create_access_token`/`create_refresh_token`
  (`core/security/security.py`, untouched by this phase) embed only
  `sub` (user id, a UUID string), `type` (`access`/`refresh`), `iat`,
  `exp` — never the full `User`, never anything sensitive.
- **Refresh**: only accepts `type: refresh` (an access token is rejected
  with `AUTH_REFRESH_TOKEN_REQUIRED`), re-verifies the user is still
  active, issues a new access token. **No refresh-token
  rotation/persistent storage** (would need a new database table) — out
  of scope until a design explicitly requires it, per the Phase 2 prompt.
- **`decode_token_strict`** (new, additive — `core/security/security.py`,
  the original `decode_token` is untouched): raises
  `TokenExpiredError`/`TokenInvalidError` distinctly (using
  `jose.ExpiredSignatureError` vs. the broader `JWTError`), instead of
  `decode_token`'s single `None` for any failure. This is what lets
  `AUTH_TOKEN_EXPIRED` and `AUTH_TOKEN_INVALID` actually mean different
  things, as both `AuthService.decode_or_raise` (used by `refresh`) and
  `get_current_user` need.
- **`get_current_user`** lives in `washy_washy/dependencies/` (new
  top-level package, mirroring `core/dependencies/`) — not `core/`,
  because it needs `UserRepository` and `washy_washy`'s own error
  codes, which `core` must never depend on. It only resolves *who* the
  caller is; no role/permission decision is made here — that's
  `require_role`/`require_permission` in Phase 3, built on top of it.
  **Not wired to any route yet** — Phase 2 adds no protected endpoints,
  so this dependency currently has no caller in the running app; it's
  exercised directly in tests (see §8).
- All `AUTH_*` codes/messages live in
  `washy_washy/constants/error_codes.py`/`error_messages.py`; every auth
  failure raises the existing `UnauthorizedException`/`ConflictException`
  — no new exception types were added.

**Dependency bug found and fixed by this phase (not introduced by it):**
Phase 0 pinned `bcrypt>=4.1.0`. That's incompatible with
`passlib==1.7.4` (unmaintained since 2020): passlib's own internal
bcrypt self-test (`detect_wrap_bug`, run lazily on first use) raises
`ValueError: password cannot be longer than 72 bytes` under bcrypt
4.1+'s stricter validation — so `hash_password`/`verify_password` were
completely non-functional before this phase, latent because nothing had
called them yet (Phase 0/1 never exercised `core/security/security.py`'s
password functions). Fixed by pinning `bcrypt>=4.0.0,<4.1` in
`pyproject.toml` (confirmed: 4.0.1 works with passlib 1.7.4, 5.0.0 —
what was actually installed — does not); reinstalled and verified
`hash_password`/`verify_password` round-trip correctly.

### 6d. RBAC runtime (`washy_washy/{services/rbac_service,dependencies/rbac}.py`) — Phase 3

Turns Phase 1's RBAC data model into actual authorization decisions.

```text
require_role("ADMIN") / require_permission("orders", "READ_ALL", "ALL")
  → returns a FastAPI dependency (a factory, not the dependency itself)
      → get_current_user()   [Phase 2 — 401 if unauthenticated]
      → RBACService.has_role() / has_permission()
          [SELECT ... JOIN user_roles JOIN roles JOIN role_permissions
           JOIN permissions WHERE user_id = ... AND roles.is_active]
      → ForbiddenException (403) if not granted, else returns the User
```

- **`RBACService`** (`washy_washy/services/rbac_service.py`) is the one
  place authorization SQL lives — routes/dependencies never write their
  own role/permission queries. `get_user_roles`, `get_user_permissions`,
  `has_role(user_id, role_name)`, `has_permission(user_id, resource,
  action, scope)`, plus `assign_role`/`remove_role` (thin delegations to
  `UserRoleRepository`, kept here so RBAC has one service-level entry
  point rather than callers reaching into repositories directly).
  **Only active roles grant anything** — `get_user_roles` filters out
  `is_active=False` roles in Python after fetching (reusing
  `UserRoleRepository.get_roles_for_user` rather than duplicating its
  join), while `get_user_permissions`/`has_role`/`has_permission` filter
  `Role.is_active` directly in their SQL joins. An inactive role is
  treated as if it were never assigned, without touching the underlying
  `UserRole` row (Phase 1's `is_active` lifecycle model, not a delete).
- **`require_role`/`require_permission`**
  (`washy_washy/dependencies/rbac.py`) are dependency *factories* — each
  call (`require_role("ADMIN")`) returns a fresh async dependency
  function closing over its argument(s). Both depend on
  `get_current_user` first (so authentication failures still surface as
  401 through the existing path) and only then call `RBACService` (403
  `ForbiddenException` if not granted). Authorization is never a
  hard-coded check (`if user.role == "ADMIN"`) — it always queries the
  real Role/Permission tables, so a role/permission change takes effect
  immediately without a code change.
- **Not wired to any route** — Phase 3 adds no protected endpoint (there
  isn't a meaningful one until a real domain exists), so both
  dependencies currently have no caller in the running app; exercised
  directly in tests (see §8), same pattern as `get_current_user` in
  Phase 2.
- No admin API for managing role/permission assignments was added — out
  of scope until an actual admin surface is needed.

### 6e. API documentation (`washy_washy/{docs,static}/`)

`main.py` sets `docs_url=None, redoc_url=None` on the `FastAPI(...)`
constructor and replaces both with its own routes so the docs carry
Washy Washy's own branding instead of the stock swagger-ui-dist/ReDoc
look — layered on top of those CDN assets, never replacing them:

```text
GET /docs   → washy_washy/docs/swagger_ui.py :: swagger_ui()
                → fastapi.openapi.docs.get_swagger_ui_html(...)   [stock HTML]
                → inject <link rel="stylesheet" href="/static/swagger-custom.css">
                → inject branded <header class="ww-header"> before <div id="swagger-ui">
GET /redoc  → same file :: redoc()  — same two injections, ReDoc's own HTML
GET /openapi.json → app.openapi()  → washy_washy/docs/openapi.py :: custom_openapi()
```

- `docs/openapi.py::custom_openapi(app, tags, title, version, description)`
  — builds `app.openapi_schema` via `fastapi.openapi.utils.get_openapi`
  and caches it there (checked at the top of the function), the same
  cache-on-`app.openapi_schema` pattern FastAPI's own docs recommend for
  a custom `openapi()`. `main.py` assigns `app.openapi = _openapi` (a
  closure capturing `app`/`settings`) rather than calling it once at
  startup, so it still runs (schema-build-then-cache) on the first
  `/openapi.json`/`/docs`/`/redoc` request, not eagerly.
  - `TAGS_METADATA` — one entry per router tag (`root`, `health`, `auth`)
    with a one-line description shown above that tag's operations in
    both UIs. A new route with a new `tags=[...]` value needs an entry
    here too, or it renders untagged/without a group description.
  - `API_DESCRIPTION` — short top-level markdown description;
    `custom_openapi` appends a fixed `_RESPONSE_ENVELOPE_NOTE` documenting
    the `{success, message, data}`/`{success, message, code, data}`
    envelope once (matching `schemas/common.py`) instead of repeating it
    on every endpoint's docstring.
- `docs/swagger_ui.py` — `get_swagger_ui_html`/`get_redoc_html` return a
  ready `HTMLResponse`; both handlers decode `.body`, do two string
  `.replace()`s (inject the CSS `<link>` before `</head>`, inject
  `_BRAND_HEADER` right after `<body>`), and return a fresh
  `HTMLResponse`. Both routes are `APIRouter(include_in_schema=False)` —
  they don't appear as operations in the schema they render.
- `static/swagger-custom.css` — brand color tokens (`--ww-primary` etc.)
  on `:root`, redefined under `@media (prefers-color-scheme: dark)`;
  restyles `.opblock` (rounded/shadowed), `.btn.execute`/`.btn.authorize`,
  inputs/selects, and the injected `.ww-header` banner. Method badge
  colors (GET=blue/POST=green/PUT=orange/DELETE=red, swagger-ui's
  defaults) are deliberately left alone — that convention is what
  developers already scan for.
- `static/favicon.svg` — a small droplet mark, used as the favicon for
  both `/docs` and `/redoc`.
- Both served from `/static` via `app.mount("/static", StaticFiles(...))`
  in `main.py`, pointed at `washy_washy/static/`.
- No security scheme (`HTTPBearer`) was added to the OpenAPI schema
  globally — `dependencies/auth.py`'s `_bearer_scheme` only shows up in
  the schema for a route that actually depends on it via
  `get_current_user`. Through Phase 3 no route did; **as of Phase 4,
  most do** (everything except `/`, `/health*`, and
  `/auth/register|login|refresh`), so the "Authorize" padlock now
  appears on those operations in both `/docs` and `/redoc`. A global
  requirement was still deliberately avoided — it would incorrectly mark
  the intentionally-public auth/health endpoints as needing a token too.

### 6f. Users, profiles, addresses & service areas (`washy_washy/{services/{profile_service,address_service,service_area_service},repositories/{customer_profile_repo,partner_profile_repo,address_repo,service_area_repo},api/v1/{routes,controllers}/{users,customers,addresses,service_areas},dependencies/rbac}.py`) — Phase 4

The first phase with real protected HTTP endpoints — `get_current_user`
(Phase 2) and `require_role` (Phase 3) get their first callers here.

```text
GET  /users/me            → get_current_user only → UserResponse (reused from auth)
GET/POST /customers/me     → get_current_user only → ProfileService
GET/POST /addresses         → get_current_user only → AddressService (ownership enforced in service)
GET/PATCH/DELETE /addresses/{id}
POST /addresses/{id}/set-default
GET  /service-areas         → get_current_user only
POST /service-areas          → get_current_user AND require_role(RoleName.ADMIN.value)
```

- **`CustomerProfile`/`PartnerProfile`**
  (`core/models/{customer_profile,partner_profile}.py`) — one per user
  (`user_id` UNIQUE FK, `ON DELETE CASCADE`), holding only fields
  specific to that role — never `email`/`password_hash`/`is_active`
  (those stay on `User`). Profile existence is independent of role
  assignment: creating a `CustomerProfile` doesn't grant the `CUSTOMER`
  role, and vice versa — a role grants permissions, a profile holds
  domain data, and neither implies the other.
  `PartnerProfile.status` (`PartnerStatus`: `PENDING`/`ACTIVE`/
  `SUSPENDED`/`INACTIVE`, plain string, not DB-enforced) models
  business-onboarding maturity, distinct from `User.is_active` (an
  auth-account flag) — the full onboarding *workflow* is Phase 9's job,
  this phase only adds the field it will drive.
  **Only `CustomerProfile` is exposed via `/customers/me`** —
  `PartnerProfile`'s model/repository/service (`ProfileService.
  create_partner_profile`/`get_partner_profile`) exist and are tested,
  but no `/partners/me` route was added: Phase 4's own endpoint list
  (`4.8`) doesn't include one, matching the "build the piece, don't
  force a premature endpoint" pattern from `get_current_user`/
  `require_role` in Phase 2/3.
- **`Address`** (`core/models/address.py`) — a user can have several;
  never stored on `User` itself. `ON DELETE CASCADE` on `user_id`
  (unlike the Phase 1 RBAC association tables, this genuinely is owned
  data, not a many-to-many grant).
  - **Ownership** is enforced in `AddressService.get_own_address`, not
    the route layer: an address that exists but belongs to someone else
    raises `NotFoundException`, not `ForbiddenException` — deliberately,
    so a caller can never learn whether an ID they don't own exists at
    all, the same posture as `AuthService.login`'s generic
    invalid-credentials failure.
  - **At most one default per user**, enforced by a partial unique index
    (`uq_addresses_one_default_per_user`, `UNIQUE (user_id) WHERE
    is_default = true`) — not expressible as a plain `UniqueConstraint`
    (those can't have a `WHERE` clause). Verified directly: a raw
    duplicate-default insert bypassing `AddressService` entirely raises
    `IntegrityError` (`tests/integration/test_addresses.py::
    test_database_rejects_two_default_addresses_for_same_user`).
  - **`set_default_address`** unsets the old default (if any) and
    flushes *before* setting the new one — two separate flushes, not
    one — so the two rows are never simultaneously `is_default = true`
    mid-flush, which the partial index would reject even within the
    same transaction.
- **`ServiceArea`/`ServiceAreaPostalCode`**
  (`core/models/service_area{,_postal_code}.py`) — deliberately two
  tables, not a `postal_code` column on `ServiceArea` itself: one area
  can cover many postal codes, and a different boundary representation
  (city, polygon, ...) could be added later without reworking
  `ServiceArea`. `ServiceAreaPostalCode.postal_code` is globally unique
  (not just unique within its area) — two overlapping zones both
  claiming the same postal code would make "which area serves this
  address" ambiguous.
  - **Design decision (§4.6 of the Phase 4 spec)**: no direct
    `User <-> ServiceArea` relationship/association table exists.
    Serviceability is a property of a *location* (a postal code,
    typically reached through an `Address`), not of a user — a customer
    can have addresses in several service areas at once, so "this user
    belongs to this area" isn't a coherent statement to model. Verified
    by `tests/unit/test_phase4_models.py::
    test_no_direct_user_service_area_relationship_table`.
  - **`ServiceAreaService.is_postal_code_serviceable`** is purely
    informational — it does **not** gate address creation. A customer
    can save an address anywhere, even outside every current service
    area; availability/slot-capacity enforcement is Phase 7's job, not
    this one's.
  - `POST /service-areas` is the first route in this project to actually
    enforce Phase 3's RBAC mechanism, via
    `dependencies=[Depends(require_role(RoleName.ADMIN.value))]`.

**Real bug found and fixed by this phase** (discovered via live
`uvicorn` smoke testing, not by the integration test suite — see below
for why): creating an address with `is_default=true` does an INSERT via
`AddressService.create_address`, then — inside the same request — a
second flush (the default-flip `UPDATE`) via `set_default_address`.
SQLAlchemy's per-mapper `eager_defaults` was at its `"auto"` default,
which didn't eagerly refetch `updated_at` (whose value changed via
`onupdate=func.now()`) after that `UPDATE`, so the attribute came back
"expired." Reading it afterward — inside `AddressResponse.model_validate(...)`,
a *synchronous* Pydantic call, exactly what the real controller does —
tried to lazily refresh it via an async DB round-trip that a sync call
can't perform, raising `MissingGreenlet: greenlet_spawn has not been
called` (surfaced to the client as a 500, even though the row itself was
correctly written and already committed).

Fixed by adding `__mapper_args__ = {"eager_defaults": True}` to
`core/models/mixins.py::CreatedAtMixin` — inherited by every model via
plain MRO attribute lookup (both `CreatedAtMixin`-only models and
`TimestampMixin` ones, since `TimestampMixin(CreatedAtMixin)`), forcing
`RETURNING` on every INSERT/UPDATE so server-computed columns are always
populated immediately after flush, regardless of what touches the
object next. (Not a `Session`/`async_sessionmaker` constructor
parameter, despite that being the first, wrong place this was tried —
`eager_defaults` is Mapper-level configuration, set via
`__mapper_args__`.)

**Why the integration test suite didn't catch this originally**: the
existing `test_create_address_with_is_default_true` test only asserted
`address.is_default is True` — it never touched `updated_at` or called
`AddressResponse.model_validate`, so it never exercised the code path
that actually failed. A new regression test,
`test_create_default_address_response_serializes_without_error`, was
added that does call `model_validate` (mirroring the real controller
exactly); it was confirmed to fail with the same `MissingGreenlet` error
when temporarily run against the pre-fix code, then confirmed to pass
against the fix, before being left in place.

### 6g. Admin role management (`washy_washy/{api/v1/{routes,controllers}/roles,schemas/role}.py`) — post-Phase-4 addendum

Closes a gap Phase 3/4 explicitly deferred ("no admin API for managing
role assignments"). `GET /roles`, `GET/POST /users/{id}/roles`,
`DELETE /users/{id}/roles/{name}` — all `ADMIN`-only via a
router-level `dependencies=[Depends(require_role(RoleName.ADMIN.value))]`.
Logic in `RBACService.{list_assignable_roles,get_user,get_user_by_email,
grant_role_by_name,revoke_role_by_name}`. Existence is pre-checked for a
clean 409/404 (granting a duplicate / revoking an unassigned role), with
the DB's `(user_id, role_id)` unique constraint as the final race guard,
same pattern as everywhere else. **An admin cannot revoke their own
`ADMIN` role** (`BusinessRuleException`/`CANNOT_REMOVE_OWN_ADMIN_ROLE`)
— a different admin still can, so this only prevents accidental
self-lockout, not a real block on removing a rogue admin.

This work, plus a `RequestValidationError` handler improvement (returns
structured per-field errors instead of a bare message, deliberately
excluding Pydantic's raw `input`/`ctx` since those can leak secrets or
hold non-serializable objects), was found already drafted but
uncommitted from an interrupted prior session and finished here rather
than discarded.

**Pre-commit installed** per explicit request: `.pre-commit-config.yaml`
(check-yaml, end-of-file-fixer, trailing-whitespace, detect-private-key,
pretty-format-json, ruff, ruff-format), hook active at
`.git/hooks/pre-commit`, added to `pyproject.toml` dev deps.

### 6h. Catalog (`washy_washy/{services/{catalog_service,partner_capability_service},repositories/{service_repo,material_repo,service_material_repo,partner_capability_repo},api/v1/{routes,controllers}/catalog,schemas/catalog}.py`) — Phase 5

```text
GET/POST /services, GET/PATCH /services/{id}                    -> Service CRUD + activate/deactivate
GET/POST /services/{id}/materials, DELETE .../materials/{mid}   -> compatibility
GET/POST /materials, GET/PATCH /materials/{id}                  -> Material CRUD + activate/deactivate
GET      /materials/{id}/services                                -> reverse compatibility lookup
```

All reads require only `get_current_user`; all writes additionally
require `require_role(RoleName.ADMIN.value)` — same router-level
`dependencies=[...]` pattern as `service-areas`/`roles`.

- **`Service`/`Material`** — plain string `name` (unique), no enum, no
  `ServiceCategory`. The example services (Wash, Dry Clean, Iron, Wash +
  Iron, Express) don't naturally group into anything, and the spec's own
  guidance is to avoid unnecessary hierarchy — add one later only if a
  real grouping need appears.
- **`ServiceMaterial`** uses `TimestampMixin` (mutable, has
  `updated_at`) — a deliberate departure from the Phase 1 association-
  table pattern (`CreatedAtMixin` only, immutable). Care instructions
  and max temperature are real content that gets corrected over time,
  not a pure yes/no grant like `UserRole`. `CatalogService.
  set_compatibility` creates the row or updates it in place; there's no
  separate "update" vs. "create" call for a caller to get wrong.
- The Phase 5 spec's "customer-declared vs. facility-verified material"
  distinction (final pricing only after inspection) is **not** modeled
  here on purpose — that's an `OrderItem` field pair for Phase 8. This
  table is only the shared vocabulary those future fields will
  reference.
- **`PartnerCapability`** — which services a partner can perform,
  capability only (no capacity/scheduling — Phase 7). Modeled as an
  immutable grant (`CreatedAtMixin`, `ON DELETE CASCADE` both ways,
  parent → grant only) — the opposite mutability choice from
  `ServiceMaterial`, and deliberately so: a partner either can perform a
  service or can't, no in-between state to edit.
  **No API endpoint** — `PartnerCapabilityService` exists and is fully
  tested, but Phase 5's own endpoint list (§5.7) doesn't ask for one;
  same "build the piece, don't force a premature endpoint" pattern as
  `PartnerProfile` in Phase 4.
- Constraint/index name lengths were checked against PostgreSQL's
  63-byte identifier limit before naming the table
  `partner_capabilities` — an earlier working name,
  `partner_service_capabilities`, would have produced a 63-byte unique
  constraint name, uncomfortably exactly at the limit.

### 6i. Pricing (`washy_washy/{services/pricing_service,repositories/{pricing_rule_repo,material_pricing_rule_repo},api/v1/{routes,controllers}/pricing,schemas/pricing}.py`) — Phase 6

```text
POST /pricing/estimate
  → PricingService.calculate_price(service_id, material_id, quantity|weight_kg|custom_charge, rush, delivery, tax, discount)
      → get_active_service_pricing(service_id)      [404 NO_ACTIVE_PRICING_RULE if none]
      → material_pricing_rules.get_active_for_material(material_id)  [None → adjustment 0]
      → service_materials.get(service_id, material_id)               [None → care_adjustment 0]
      → _compute_quantity_charge(pricing_rule, ...)   [dispatches on pricing_model]
  ← PriceBreakdown  (base, material_adjustment, care_adjustment, quantity_charge,
                      rush_charge, delivery_charge, tax, discount, subtotal, total,
                      pricing_rule_id, material_pricing_rule_id)
```

- **`PricingRule`/`MaterialPricingRule`** — each row *is* a version (no
  separate `*_version` table): `set_service_pricing`/
  `set_material_pricing` close the current active row
  (`effective_to = now()`) then insert a new one, in two separate
  flushes — same reasoning as `AddressService.set_default_address`
  (Phase 4): the two rows must never both be "active" mid-flush, which
  the partial unique index (`WHERE effective_to IS NULL`, one per
  service/material) would reject even within one transaction. A rate
  change therefore never rewrites an existing row — the old row's
  `base_price`/`unit_price` stay exactly what they were, forever.
- **`PricingModel`** dispatch: `PER_ITEM`/`PER_BAG` need `quantity`;
  `PER_KG`/`BASE_PLUS_WEIGHT` need `weight_kg`; `CUSTOM` uses
  `custom_charge` (defaulting to zero if omitted). Passing the wrong
  input for the active model raises `BusinessRuleException`
  (`QUANTITY_REQUIRED`/`WEIGHT_REQUIRED`) rather than silently
  producing a zero charge.
- **Rush charge, delivery charge, tax, and discount are parameters to
  `calculate_price`, not stored catalog rates** — matching the Phase 6
  spec's own framing of these as *inputs* to the pricing service. No
  "global tax rate"/policy table exists; that's deferred until a real
  need appears (plausibly Phase 10, payments/invoices).
- **`ServiceMaterial.care_adjustment`** (new nullable column, Phase 5's
  table) is deliberately *not* independently versioned like the two
  rules above — it's a smaller modifier tied directly to the care
  requirement it corresponds to, edited in place, not a rate significant
  enough to warrant its own history.
- **No separate estimate/final method** — `calculate_price` is the one
  call; an "estimated" price (customer-declared material/quantity) and
  a "final" price (facility-verified, post-inspection) are just two
  invocations with different inputs, not a different formula. Snapshotting
  which rule versions produced a *stored* price — so a later rate change
  can't retroactively alter an existing order's total — is Phase 8's job
  once `Order`/`OrderItem` exist; `PriceBreakdown` already carries
  `pricing_rule_id`/`material_pricing_rule_id` for exactly that.
- All money fields are `Numeric(10, 2)`/`Decimal`, never `float` —
  verified by a dedicated precision test
  (`test_calculate_price_is_decimal_precise_not_float`) using inputs
  that would accumulate floating-point error (`0.10 + 0.20*3`) if this
  slipped to `float` anywhere in the chain.

### 6j. Availability / Slots / Capacity (`washy_washy/{services/availability_service,repositories/{operating_hours_repo,partner_availability_repo,pickup_slot_repo,delivery_slot_repo,pickup_slot_reservation_repo,delivery_slot_reservation_repo},api/v1/{routes,controllers}/availability,schemas/availability}.py`) — Phase 7

```text
GET/POST /service-areas/{id}/operating-hours    -> per-day opening/closing time (ADMIN writes)
GET/POST /partners/{id}/availability             -> per-day partner working hours (ADMIN writes)
GET/POST /service-areas/{id}/pickup-slots        -> dated capacity-bearing slots (ADMIN writes)
GET/POST /service-areas/{id}/delivery-slots      -> same, separate table
POST     /pickup-slots/{id}/reservations         -> book (any authenticated caller)
DELETE   /pickup-slots/reservations/{id}         -> cancel own reservation (404 if not owner)
POST     /delivery-slots/{id}/reservations       -> book
DELETE   /delivery-slots/reservations/{id}        -> cancel own reservation
```

- **`OperatingHours`/`PartnerAvailability`** — one row per
  `(service_area_id, day_of_week)` / `(partner_profile_id, day_of_week)`,
  `UNIQUE` on that pair, `TimestampMixin` (hours get corrected in place,
  not versioned — unlike `PricingRule`, a wrong closing time isn't
  something worth keeping history of). `DayOfWeek` is a plain `StrEnum`
  of the seven day names, not DB-enforced (same reasoning as `RoleName`
  in §6b — a string column, not a Postgres enum type, so no migration is
  needed if a new value scheme is ever needed). `AvailabilityService.
  set_operating_hours`/`set_partner_availability` create-or-update in
  place (one row per day, no history) — `close_day` sets `is_active =
  false` rather than deleting the row, so the configured hours aren't
  lost, just switched off.
- **`PickupSlot`/`DeliverySlot`** — deliberately two separate tables,
  not one table with a `direction`/`kind` discriminator column, per the
  spec's explicit instruction. Each carries `capacity_unit` (a plain
  string against `CapacityUnit`'s vocabulary — `ORDERS`/`WEIGHT_KG`/
  `ITEMS`/`BAGS` — same "not DB-enforced" reasoning as `DayOfWeek`),
  `capacity_total`, and `capacity_reserved` (`Numeric(10,2)`, defaults
  `0`). Two `CHECK` constraints (`capacity_reserved <= capacity_total`,
  `capacity_reserved >= 0`) are the last-resort database-level guard —
  belt-and-suspenders under the application-level atomic `UPDATE` below,
  not the primary mechanism. `UNIQUE (service_area_id, slot_date,
  start_time, end_time)` prevents creating the same slot window twice.
- **Race-free capacity reservation — the core mechanism of this phase**
  (`PickupSlotRepository.try_reserve_capacity`/`DeliverySlotRepository.
  try_reserve_capacity`):
  ```python
  stmt = (
      update(PickupSlot)
      .where(
          PickupSlot.id == slot_id,
          PickupSlot.is_active.is_(True),
          PickupSlot.capacity_reserved + amount <= PickupSlot.capacity_total,
      )
      .values(capacity_reserved=PickupSlot.capacity_reserved + amount)
  )
  result = await self._session.execute(stmt)
  return result.rowcount == 1
  ```
  The capacity check and the increment happen in the *same* statement,
  evaluated atomically by PostgreSQL against the current row — there is
  no read-then-write window for two concurrent requests to both pass a
  Python-side check against a value that's since gone stale. If the
  `WHERE` clause doesn't match (already full, or someone else's
  concurrent `UPDATE` got there first), `rowcount` is `0` and
  `AvailabilityService.book_pickup_slot`/`book_delivery_slot` raises
  `BusinessRuleException`/`SLOT_CAPACITY_EXCEEDED` — no `SELECT FOR
  UPDATE`, no advisory lock, no Redis-backed counter. **Verified under
  real concurrency, not just sequential logic** —
  `tests/integration/test_availability_concurrency.py` fires 10 truly
  concurrent booking attempts (separate connections via independent
  `session_factory()` calls + `asyncio.gather`, deliberately bypassing
  the shared savepoint-based `db_session` fixture, since a genuine race
  needs separate connections) against a slot with capacity for only 3;
  exactly 3 succeed and `capacity_reserved` lands exactly on `3`, never
  over.
- **Cancellation releases capacity** via the mirrored unconditional
  `release_capacity` (`UPDATE ... SET capacity_reserved =
  capacity_reserved - amount`) and flips the reservation's `status` to
  `CANCELLED`. **Idempotent** — cancelling an already-cancelled
  reservation is a silent no-op (checked via `status == ACTIVE` before
  touching capacity), so a duplicate cancel request can never double-free
  capacity that was already released.
- **Ownership enforced the same way as `AddressService`** (§6f): a
  reservation that exists but belongs to a different customer raises
  `NotFoundException`, not `ForbiddenException` — a caller can't learn
  whether a reservation ID they don't own exists at all.
- **`PickupSlotReservation`/`DeliverySlotReservation` deliberately have
  no `partner_profile_id` and no `order_id` column.** A reservation is
  against the *slot's* capacity, not a specific partner — assigning a
  partner to fulfil a booking is Phase 9 (Partner Operations), and
  `Order` doesn't exist until Phase 8, so there's nothing yet to link a
  reservation to. Adding either column now would be speculative ahead of
  those phases actually needing it.
- **Known, documented scope gap**: `AvailabilityService.
  has_capable_partner(service_id)` checks only whether *any* partner
  anywhere holds the capability for a service (`PartnerCapabilityRepository.
  has_any_capability_for_service`) — it is **not** scoped to the service
  area being booked, and it is **not** enforced inside `book_pickup_slot`/
  `book_delivery_slot`. A real "is a capable partner actually available
  in this area for this slot" check needs a `PartnerProfile <->
  ServiceArea` association that doesn't exist in the current schema —
  adding it now would be speculative ahead of Phase 9, which is where
  partner-to-area/partner-to-order assignment actually belongs. This
  limitation is documented in `availability_service.py`'s own module
  docstring, not silently glossed over.

### Migrations (`core/migrations/`, Alembic)
- Owned by `core` since models live in `core/models/`. `washy_washy` has no
  migrations folder of its own.
- `env.py` is async (`async_engine_from_config` + `connection.run_sync`),
  reads the DB URL from `get_core_settings().database_url` (never
  hardcoded), and imports `core.models` — not `washy_washy.main` — to
  build `target_metadata = Base.metadata`. Running migrations therefore
  never starts the FastAPI app and never needs the ASGI app to exist.
- `alembic.ini`: `script_location = src/core/migrations`,
  `prepend_sys_path = . src`, `path_separator = os`,
  `version_path_separator = os`.
- `script.py.mako` generates modern-style revision files
  (`str | None`, `from collections.abc import Sequence`) so every future
  `alembic revision` output passes this project's ruff config as-is.
- Seven revisions exist, in this order (each hand-written to match the
  models exactly rather than trusted from a raw `--autogenerate` dump —
  reviewed per the project's migration-safety rule):
  1. `0a91544a311e` create identity and rbac core tables — `users`,
     `roles`, `permissions` (independent parents).
  2. `e8dc958f2e5e` create rbac association tables — `user_roles`,
     `role_permissions` (reference the tables from #1; downgrade drops
     in reverse dependency order).
  3. `db9e1e1a26b8` seed foundational roles — idempotent data-only
     migration: inserts the four `RoleName` roles with
     `uuid.uuid5`-derived deterministic IDs and
     `ON CONFLICT (name) DO NOTHING`; `downgrade` deletes those four rows
     by name. No permissions are seeded.
  4. `3587faef9553` create profile and address tables — `customer_profiles`,
     `partner_profiles`, `addresses` (all independently reference only
     `users`, so they share a revision). Includes the partial unique
     index on `addresses (user_id) WHERE is_default = true`.
  5. `9ad4f2884494` create service area tables — `service_areas`,
     `service_area_postal_codes` (the latter references the former, so
     it must come second within this revision).
  6. `368d5df746fb` create catalog tables — `services`,
     `materials` (independent parents), then `service_materials`
     (references both) and `partner_capabilities` (references
     `services` and the existing `partner_profiles`).
  7. `f04acb897ec2` create pricing tables + care_adjustment —
     `pricing_rules`, `material_pricing_rules` (both independent,
     versioned, partial-unique-indexed), plus `ALTER TABLE
     service_materials ADD COLUMN care_adjustment`.
  8. `01a11e11a45d` (head) create availability, slots, and capacity
     tables — `operating_hours`, `partner_availabilities` (both
     independent, reference `service_areas`/`partner_profiles`
     respectively), then `pickup_slots`/`delivery_slots` (each with its
     two capacity `CHECK` constraints) and `pickup_slot_reservations`/
     `delivery_slot_reservations` (reference their own slot table and
     `users`).
  `alembic upgrade head` has been run against real PostgreSQL — both a
  local install and, separately, the `docker-compose` `postgres`
  container — and verified: all 21 tables exist (`alembic_version` +
  the 20 above) with the four `RoleName` roles seeded. Every multi-table
  revision's full `downgrade` → `upgrade head` round-trip has been run
  and verified at the time it was added (tables dropped cleanly,
  recreated identically) — see §9/§10.
- `alembic heads` runs cleanly with no DB connection required;
  `alembic current`/`upgrade`/`downgrade`/`revision --autogenerate`
  require a reachable PostgreSQL instance.
- Commands: `alembic revision --autogenerate -m "..."`, `alembic upgrade
  head`, `alembic downgrade -1`, `alembic heads`, `alembic current`.

### Errors (`core/exceptions/handlers.py`)
- `AppException` base (with `status_code`, `code`, `message`) and subclasses:
  `ValidationException` (422), `UnauthorizedException` (401),
  `ForbiddenException` (403), `NotFoundException` (404),
  `ConflictException` (409), `BusinessRuleException` (422),
  `InternalErrorException` (500).
- `register_exception_handlers(app)` wires three handlers:
  1. `AppException` → `{success: false, message, code, data: null}` at
     `exc.status_code`.
  2. `RequestValidationError` (Pydantic/FastAPI validation) → 422 with
     code `VALIDATION_ERROR`.
  3. Any other `Exception` → logged via `logger.exception(...)`, returned
     as 500 `INTERNAL_SERVER_ERROR` (never leaks internals to the client).
- Matching stable string codes live in
  `washy_washy/constants/error_codes.py`; default messages in
  `washy_washy/constants/error_messages.py`. Route/service code should
  reference these constants, not hardcode strings.
- This module is intentionally free of any `washy_washy` import so `core`
  stays independent.

### Response envelope (`washy_washy/schemas/common.py`)
- `SuccessResponse[DataT]` → `{success: true, message, data}`.
- `ErrorResponse` → `{success: false, message, code, data: null}`.
- Every endpoint returns one of these two shapes — this is the contract
  all API consumers (Flutter apps, admin web) rely on.

### Middleware (`core/middleware/request_id.py`)
- `RequestIDMiddleware`: reuses an inbound `X-Request-ID` header or
  generates a UUID4, stores it on `request.state.request_id`, echoes it
  back on the response header. Lets route/controller/service code attach
  it to log records for correlation.

### Logging (`core/logging/logging_config.py`)
- `configure_logging(log_level)` (called once, in `main.py`'s lifespan):
  stdout `StreamHandler`, format includes `request_id`, `user_id`,
  `order_id` (defaulted to `-` via `_RequestContextFilter` when not
  supplied). Quiets `uvicorn.access` and `sqlalchemy.engine` to WARNING
  unless `log_level == DEBUG`.

### Security primitives (`core/security/security.py`)
- Password hashing: `hash_password` / `verify_password` (bcrypt via
  passlib). See §6c for a dependency-pin bug this pairing had until
  Phase 2 (bcrypt needed pinning to `<4.1`).
- JWT: `create_access_token`, `create_refresh_token` (embed `type: access|
  refresh`), `decode_token` (returns `None` on `JWTError` instead of
  raising), and `decode_token_strict` (Phase 2, additive) which raises
  `TokenExpiredError`/`TokenInvalidError` distinctly instead of
  collapsing both into `None` — see §6c for why the auth flow needs that
  distinction.
- **Primitives only** — login/refresh-rotation *workflows* live in
  `washy_washy/services/auth_service.py` (Phase 2, see §6c), not here.

## 7. Infrastructure

### Docker (`Dockerfile`, `docker-compose.yml`)
- `Dockerfile`: `python:3.12-slim`, installs `build-essential`/`libpq-dev`,
  `pip install .` from `pyproject.toml` + `src/`, copies `tests/`, exposes
  `8000`, CMD runs Uvicorn directly (no `--reload` in the image).
- `docker-compose.yml`: two services —
  - `postgres` (16-alpine) with a healthcheck (`pg_isready`).
  - `api`, built from the local `Dockerfile`, `env_file: .env`, overrides
    `DATABASE_URL`/`POSTGRES_HOST` to point at the `postgres` service
    name, `depends_on: postgres` gated on `service_healthy`.
- Redis, Celery, APISIX are **not** part of compose yet (Phase 11/12).

### Packaging (`pyproject.toml`)
- `hatchling` build backend, `src/` layout, packages =
  `["src/core", "src/washy_washy"]`.
- Runtime deps: fastapi, uvicorn[standard], pydantic/pydantic-settings,
  sqlalchemy[asyncio] 2.x, asyncpg, alembic, python-jose[cryptography],
  passlib[bcrypt], `bcrypt>=4.0.0,<4.1` (pinned below 4.1 — see §6c for
  why; was `>=4.1.0` in Phase 0, which broke password hashing).
- Dev extra (`.[dev]`): httpx, pytest, pytest-asyncio, ruff.
- `pytest`: `asyncio_mode = "auto"`, `pythonpath = ["src"]`,
  `testpaths = ["tests"]`, `asyncio_default_fixture_loop_scope = "session"`
  + `asyncio_default_test_loop_scope = "session"` — see §8's note on why
  (asyncpg connections are bound to the event loop that created them;
  `core/database/engine.py`'s cached singletons need one loop for the
  whole test run, matching production).
- `ruff`: line-length 100, target py312, rule sets `E,F,I,UP,B`,
  `fastapi.Depends/Query/Path/Body` marked immutable for B008.

## 8. Tests (`tests/`)
- **Event loop scope bug fixed (found only by running the full suite
  against a live DB)**: pytest-asyncio's default is a fresh event loop
  per test *function*. `core/database/engine.py`'s `get_engine()`/
  `get_session_factory()` are process-wide `@lru_cache` singletons (by
  design — matching production, where one event loop runs for the
  process's whole lifetime), but asyncpg binds each connection to the
  loop that created it. With per-function loops, the first integration
  test to use the cached engine/pool works; every later one intermittently
  fails with `RuntimeError: ...Task ... attached to a different loop` or
  `'NoneType' object has no attribute 'send'` depending on pool timing.
  Fixed in `pyproject.toml` (`asyncio_default_fixture_loop_scope =
  "session"` + `asyncio_default_test_loop_scope = "session"` — both are
  required; setting only the fixture scope still splits tests and
  fixtures across different loops). No code under test was wrong.
- `conftest.py` — shared fixtures (ASGI transport client), plus a
  `DATABASE_URL`/`JWT_SECRET` fallback so importing the app never fails
  on missing required settings in a bare checkout with no `.env`.
  - **Bug fixed**: this fallback used to apply unconditionally via
    `os.environ.setdefault(...)`. Since an OS environment variable always
    outranks `CoreSettings`' `.env` file (pydantic-settings' standard
    precedence), setting it — even via `setdefault`, since a bare shell
    has neither var set — permanently shadowed the real, already-correct
    `.env` (e.g. a locally customized `POSTGRES_PASSWORD`) for the rest
    of the pytest process. Every integration test's DB connection then
    failed authentication, which `db_session`'s broad `except Exception:
    pytest.skip(...)` silently reported as "PostgreSQL is not reachable"
    — indistinguishable from a genuinely absent database. This is why
    every phase's changelog entry up to and including Phase 3 reported
    integration tests skipping even after Postgres became reachable:
    the fixture was never actually attempting a connection with the
    right credentials unless the invoking shell happened to already have
    `DATABASE_URL` exported (which is how the "DB verification" and
    "Docker fully verified" entries above got 114/114 — their shell had
    it set from prior `alembic`/`docker exec` commands in the same
    session; a fresh shell did not). Fixed by only applying the fallback
    when no `.env` file exists at the repo root, so a present `.env` is
    never shadowed. Verified: `pytest` now reproducibly reports
    `114 passed` with **zero skips** from a cold shell with no
    pre-exported environment, not just from a shell that happens to have
    the right history.
- `test_health.py` — exercises the health endpoints end-to-end via
  `httpx.ASGITransport` (no separately running server needed).
- `test_import.py` — sanity import check + an AST-based guard asserting no
  file under `src/core` imports anything from `washy_washy`.
- `unit/test_database_foundation.py` (Phase 1A) — `Base.metadata` exists,
  the naming convention is exactly as specified, `UUIDPrimaryKeyMixin`
  produces a `Uuid`-typed primary key whose default generates a real
  `uuid.UUID`, and `TimestampMixin`'s columns are timezone-aware,
  non-nullable, and server-controlled (`server_default`/`onupdate`, not a
  Python-side default). Uses a throwaway, never-persisted model class
  purely to inspect column shapes.
- `unit/test_alembic_wiring.py` (Phase 1A) — the Alembic script directory
  resolves correctly from `alembic.ini`, and `core.models` imports cleanly
  on its own (proving `env.py`'s `from core.models import *` can't drag in
  `washy_washy` or require a live DB/running app).
- `integration/test_database_connection.py` (Phase 1A) — runs a real
  `SELECT 1` through the async engine/session against PostgreSQL;
  **skips** (does not fail) if PostgreSQL isn't reachable, so the default
  `pytest` run never depends on external services. Washy Washy is
  PostgreSQL-first — this suite intentionally does not fall back to
  SQLite for PostgreSQL-specific behavior.
- `unit/test_rbac_models.py` (Phase 1B–1D) — no DB required: mapper
  configuration succeeds, all five tables are registered on
  `Base.metadata`, `User` has no `role`/`role_id` column, column
  nullability/defaults match spec, uniqueness constraints are exactly
  `(email,)`/`(phone,)`/`(name,)`/`(resource, action, scope)`/
  `(user_id, role_id)`/`(role_id, permission_id)`, `permissions.scope`
  is non-nullable with its `CHECK` constraint present, the association
  tables have `created_at` but no `updated_at` and `ON DELETE CASCADE`
  on every FK, `RoleName` matches the four foundational roles, and
  `normalize_email` behaves as documented.
- `integration/conftest.py`'s `db_session` fixture (Phase 1B–1D) — used
  by every file under `integration/`. Skips cleanly if PostgreSQL is
  unreachable *or* if `users` hasn't been migrated yet (`SELECT
  to_regclass('public.users') IS NULL` — i.e. `alembic upgrade head`
  hasn't run). Wraps each test in its own outer transaction
  (`connection.begin()` + `AsyncSession(bind=connection,
  join_transaction_mode="create_savepoint")`) that's always rolled back
  on teardown, so a `commit()`/`rollback()` inside the code under test
  only affects a savepoint and tests never leave rows behind in a shared
  dev database.
  - **Bug fixed (found only by running against a live DB)**:
    `connection.begin()` used to run *after* the
    `SELECT to_regclass('public.users')` reachability check on the same
    connection. SQLAlchemy 2.0's "autobegin" means that `SELECT` already
    opens an implicit transaction, so the later explicit `begin()` raised
    `InvalidRequestError: This connection has already initialized a
    SQLAlchemy Transaction()...` — every integration test errored, not
    skipped, as soon as a real PostgreSQL was reachable. Fixed by moving
    `connection.begin()` before any query runs on the connection (the
    reachability `SELECT` now runs inside that transaction; skip path
    rolls it back before returning). No code under test was wrong — this
    was a bug in the *fixture*, latent since Phase 1B because no earlier
    session in this environment had reachable Postgres to expose it.
- `integration/test_user_identity.py` (Phase 1B) — create generates a
  UUID + timezone-aware server timestamps, default `is_active`/
  `is_verified`, `get_by_id` round-trip, email normalization on both
  write and lookup, duplicate normalized email rejected
  (`IntegrityError`), duplicate phone rejected, multiple `NULL` phones
  allowed, stored `password_hash` differs from the raw password and
  verifies via `core.security`, and a mid-transaction failure + rollback
  leaves no partial record.
- `integration/test_rbac_associations.py` (Phase 1C–1D) — `Role`/
  `Permission` creation and uniqueness rejection, the `scope` `CHECK`
  constraint rejects an invalid value, `UserRole`/`RolePermission`
  assign+retrieve, duplicate-assignment rejection, FK-integrity
  rejection for a nonexistent parent, removing an association doesn't
  touch its parents, and deleting a `User` cascades to its `UserRole`
  rows without touching the `Role`.
- `unit/test_auth_tokens_and_schemas.py` (Phase 2) — no DB required:
  `hash_password`/`verify_password` round-trip (and that the hash isn't
  the raw password), access vs. refresh tokens carry the right distinct
  `type` claim, `decode_token_strict` raises `TokenInvalidError` for a
  garbage/wrong-signature token and `TokenExpiredError` for a genuinely
  expired one (built by hand with a past `exp`), `RegisterRequest`/
  `LoginRequest` reject short passwords and malformed emails, and
  `UserResponse` has no `password`/`password_hash` field at all.
- `integration/test_auth.py` (Phase 2) — full `AuthService` flow against
  real PostgreSQL: register success, duplicate email/phone rejected,
  login success issues distinct access+refresh tokens, wrong password/
  nonexistent user/inactive user all rejected, refresh issues a new
  access token, refresh rejects an access token, and `get_current_user`
  (called directly, not over HTTP — see below) resolves a valid token,
  rejects a missing header/refresh-token-as-access/malformed token, and
  rejects an inactive user.
- `api/test_auth_routes.py` (Phase 2) — HTTP-level, via the ASGI
  transport `client` fixture, limited to paths that never touch the
  database (request validation on register/login, and refresh-token
  decoding, which happens before any DB access) — the first tests to
  populate what was previously an empty `tests/api/` scaffold.
- `integration/test_rbac_runtime.py` (Phase 3) — `RBACService` against
  real PostgreSQL: `get_user_roles` returns only active assigned roles,
  role → permission resolution through the full join, `has_permission`
  false without any grant, permissions from multiple roles accumulate,
  a permission shared by two of a user's roles isn't returned twice
  (exercises the query's `.distinct()`), `assign_role`/`remove_role`
  round-trip through `has_role`, and `require_role`/`require_permission`
  each allow a granted role/permission and raise `ForbiddenException`
  for one that isn't granted. Doesn't re-test `get_current_user`'s own
  401 paths (no token/invalid token/expired token) — those are Phase 2's
  `test_auth.py`'s job; this file is about the authorization layer built
  on top.
- `unit/test_phase4_models.py` (Phase 4) — no DB required: mapper
  configuration succeeds, `CustomerProfile`/`PartnerProfile.user_id` are
  each unique with no auth-field duplication, `PartnerProfile.status`
  defaults to `PENDING`, every `Address`/`ServiceAreaPostalCode` foreign
  key is `ON DELETE CASCADE`, `Address.is_default` defaults `False`,
  `addresses` carries exactly one partial unique index (`WHERE
  is_default = true`) on `user_id` plus a plain index on the same
  column, `service_areas.name` and `service_area_postal_codes.
  postal_code` are unique, the latter has `created_at` but no
  `updated_at`, and there is no `user_service_areas`-style table on
  `Base.metadata` (see §6f's design decision).
- `integration/test_profiles.py` (Phase 4) — `ProfileService` against
  real PostgreSQL: create/get customer and partner profiles, duplicate
  profile of either kind rejected (`ConflictException`), profile not
  found raises `NotFoundException`, and a user can hold both profile
  kinds independently (creating one doesn't preclude the other).
- `integration/test_addresses.py` (Phase 4) — `AddressService` against
  real PostgreSQL: create, list returns only the caller's own,
  cross-user access (get/update/delete) raises `NotFoundException`
  rather than confirming the address exists, partial update changes
  only the given fields, delete, `set_default_address` flips the
  previous default off, creating with `is_default=true` works
  end-to-end including response serialization (the regression test for
  §6f's `eager_defaults` bug), and a raw duplicate-default insert that
  bypasses `AddressService` entirely still raises `IntegrityError` —
  proving the partial unique index, not just application logic, is the
  real guard.
- `integration/test_service_areas.py` (Phase 4) — `ServiceAreaService`
  against real PostgreSQL: create with initial postal codes, duplicate
  name rejected, an unmapped postal code isn't serviceable, a postal
  code under an `is_active=False` area isn't serviceable,
  `list_active` excludes inactive areas, and `require_role(ADMIN)`
  allows a user actually granted the (already-seeded) `ADMIN` role while
  rejecting one with no role or with `CUSTOMER` instead — assigned via
  `UserRoleRepository`/`RoleRepository` directly, the same pattern
  Phase 3's own RBAC tests used (there is still no admin API for
  granting roles — see §9's Current Status).
- `api/test_protected_routes_require_auth.py` (Phase 4) — HTTP-level,
  via the ASGI transport `client` fixture, no DB required: every new
  Phase 4 endpoint (`GET/POST` on `/users/me`, `/customers/me`,
  `/addresses`, `/service-areas`) returns 401 `AUTH_TOKEN_INVALID` with
  no `Authorization` header and with a malformed Bearer token — proving
  empirically that FastAPI resolves `get_current_user` (and therefore
  rejects) *before* attempting body validation, so a missing/short
  request body never masks the auth failure as a 422 instead.

`get_current_user` and `require_role`/`require_permission` were
exercised only as plain async functions (no protected route existed)
through Phase 3; Phase 4 both wires real protected routes (tested at the
HTTP level in `api/test_protected_routes_require_auth.py`) and continues
calling them directly for deeper RBAC-specific scenarios in
`integration/test_service_areas.py`, matching the pattern Phase 3
established.
- `integration/test_role_management.py` (admin role management
  addendum) — `list_assignable_roles` includes the seeded roles; grant/
  revoke round-trip; duplicate grant is `ConflictException`; granting/
  revoking for a nonexistent user, a nonexistent role, or an inactive
  role all raise `NotFoundException`; revoking an unassigned role raises
  `NotFoundException`; an admin cannot revoke their own `ADMIN` role but
  a *different* admin can; `get_user`/`get_user_by_email` round-trip and
  404 when not found.
- `unit/test_phase5_models.py` (Phase 5) — no DB required: `Service`/
  `Material` name uniqueness and `is_active` default, `ServiceMaterial`
  uniqueness on `(service_id, material_id)` and that it *has*
  `updated_at` (the deliberate mutability departure — see §6h),
  `PartnerCapability` uniqueness on `(partner_profile_id, service_id)`
  and that it does *not* have `updated_at`, and `ON DELETE CASCADE` on
  every FK in both tables.
- `integration/test_catalog.py` (Phase 5) — `CatalogService` against
  real PostgreSQL: service/material creation + duplicate-name rejection
  + not-found, activation/deactivation, `list_services`/`list_materials`
  excluding inactive by default, setting compatibility twice updates the
  same row in place (not a duplicate) and its care metadata changes,
  compatibility for a nonexistent service/material raises
  `NotFoundException`, removing compatibility, and an unset pair reports
  not compatible. `PartnerCapabilityService`: grant/check/list, duplicate
  grant rejected, revoke, and granting for a nonexistent partner profile
  or service raises `NotFoundException`.
- `api/test_protected_routes_require_auth.py` extended with the new
  `/roles`, `/services`, `/materials` paths (Phase 5) — still no DB
  required, same reasoning as Phase 4's version of this file.
- `unit/test_phase6_models.py` (Phase 6) — no DB required: `PricingModel`
  matches the five spec'd values, `effective_to` is nullable on both
  rule tables, each has exactly one partial unique index on its
  `(service_id,)`/`(material_id,)`, `ON DELETE CASCADE` on both FKs, and
  `service_materials.care_adjustment` exists and is nullable.
- `integration/test_pricing.py` (Phase 6) — `PricingService` against
  real PostgreSQL: set/get a service's active rule, setting a new price
  closes the previous version (and the old row's own rate is
  unchanged), same for material pricing, `calculate_price` for every
  `PricingModel` (`PER_ITEM`/`PER_KG`/`PER_BAG`/`BASE_PLUS_WEIGHT`/
  `CUSTOM`) with the matching required input and a rejection when the
  wrong one is supplied, material/care adjustments included in the
  subtotal, rush/delivery/tax/discount applied to reach the total,
  `Decimal` precision holds for an input that would drift under
  `float`, the "estimate vs. final" split is just two calls with
  different inputs (not a different formula), and a breakdown computed
  under an old rule version keeps referencing that exact `pricing_rule_id`
  even after a newer version supersedes it.
- `api/test_protected_routes_require_auth.py` extended with
  `POST /pricing/estimate` (Phase 6).
- `unit/test_phase7_models.py` (Phase 7) — no DB required: mapper
  configuration succeeds, `DayOfWeek` has exactly the seven spec'd
  names, `CapacityUnit` matches `ORDERS`/`WEIGHT_KG`/`ITEMS`/`BAGS`,
  `OperatingHours`/`PartnerAvailability` are each uniquely constrained
  on their `(parent_id, day_of_week)` pair, `PickupSlot`/`DeliverySlot`
  (and their reservation tables) are genuinely separate classes/tables
  — not one table with a discriminator, `PickupSlot` carries both named
  `CHECK` constraints (`ck_pickup_slots_capacity_within_total`/
  `ck_pickup_slots_capacity_reserved_non_negative` — the naming
  convention's `ck_%(table_name)s_%(constraint_name)s` prefix applies
  here same as everywhere else) and defaults `capacity_reserved` to
  `Decimal("0")`, its four-column uniqueness constraint is present,
  every slot-table FK is `ON DELETE CASCADE`, `ReservationStatus.ACTIVE`
  is the status default, and `PickupSlotReservation` has neither a
  `partner_profile_id` nor an `order_id` column (§6j's deliberate design
  decision).
- `integration/test_availability.py` (Phase 7) — `AvailabilityService`
  against real PostgreSQL, sequential logic and business rules: set/get
  operating hours, setting them twice updates the same row in place,
  `is_open` true within hours and false outside/on an undefined day,
  `close_day` overrides previously-set hours, partner availability
  round-trip (`is_partner_available` true within hours, false outside
  and on an unset day), `has_capable_partner` false before a grant and
  true after, create/list pickup slots, pickup and delivery slots stay
  independent (booking one never touches the other's capacity), booking
  reserves capacity, booking past remaining capacity raises
  `BusinessRuleException`, booking a nonexistent slot raises
  `NotFoundException`, cancelling releases capacity, cancelling
  someone else's reservation raises `NotFoundException` (ownership,
  same posture as `AddressService`), cancelling twice is a no-op (no
  double-release), and a full delivery-slot book+cancel round-trip.
- `integration/test_availability_concurrency.py` (Phase 7) — the one
  test in the suite that deliberately bypasses the shared savepoint
  `db_session` fixture (a genuine race needs independent connections,
  not one connection's savepoints): 10 truly concurrent booking
  attempts via separate `session_factory()` sessions + `asyncio.gather`
  against a slot with capacity for exactly 3 — exactly 3 succeed,
  `capacity_reserved` lands exactly on `3`, proving the atomic
  conditional `UPDATE` in `try_reserve_capacity` (§6j) actually prevents
  overbooking under real concurrent load, not just in sequential-logic
  tests. Uses real commits and manually cleans up everything it wrote
  in a `finally` block, since nothing here is rolled back automatically.

## 9. Current status (keep this section accurate)

| Layer | State |
|---|---|
| `core/config`, `core/database`, `core/dependencies`, `core/logging`, `core/middleware`, `core/exceptions`, `core/security` | Implemented |
| `core/models` — infrastructure | Implemented (naming convention, `UUIDPrimaryKeyMixin`, `CreatedAtMixin`, `TimestampMixin`) |
| `core/models` — identity/RBAC | Implemented: `User`, `Role`/`RoleName`, `Permission`/`PermissionScope`, `UserRole`, `RolePermission` |
| `core/models` — operational user domain | Implemented (Phase 4): `CustomerProfile`, `PartnerProfile`/`PartnerStatus`, `Address`/`AddressLabel`, `ServiceArea`, `ServiceAreaPostalCode` |
| `core/models` — catalog | Implemented (Phase 5): `Service`, `Material`, `ServiceMaterial` (+ `care_adjustment` since Phase 6), `PartnerCapability` |
| `core/models` — pricing | Implemented (Phase 6): `PricingRule`/`PricingModel`, `MaterialPricingRule` |
| `core/models` — availability/slots | Implemented (Phase 7): `OperatingHours`/`DayOfWeek`, `PartnerAvailability`, `CapacityUnit`, `PickupSlot`, `DeliverySlot`, `PickupSlotReservation`/`ReservationStatus`, `DeliverySlotReservation` — **no other domain models yet** (orders, payments, ... are later phases) |
| `core/models` — infra fix | `CreatedAtMixin`/`TimestampMixin` now set `__mapper_args__ = {"eager_defaults": True}` (Phase 4) — see §6f for the `MissingGreenlet` bug this fixes, affecting every model, not just `Address` |
| `core/migrations` | Implemented: async env, settings-driven URL, deterministic naming, 8 revisions (identity+RBAC → RBAC associations → seed roles → profile/address → service area → catalog → pricing → availability/slots/capacity). **Verified**: `alembic upgrade head`/`downgrade`/`upgrade` round-trip run against real PostgreSQL (both local and the `docker-compose` container) — all 21 tables exist, 4 roles seeded, full `pytest` suite (265 tests) passes with 0 skips against it |
| `washy_washy/api/v1` | `health`, `auth`, `users`, `customers`, `addresses`, `service-areas`, `roles`, `catalog`, `pricing`, `availability` (routes + controllers) — most endpoints require authentication; writes on `service-areas`, `roles`, `catalog`, `pricing`, and most of `availability` require `ADMIN` (booking/cancelling your own reservation only needs authentication) |
| `washy_washy/services` | Implemented: `auth_service`, `rbac_service`, `profile_service`, `address_service`, `service_area_service`, `catalog_service`, `partner_capability_service`, `pricing_service`, `availability_service` |
| `washy_washy/repositories` | Implemented: `user_repo`, `role_repo`, `permission_repo`, `user_role_repo`, `role_permission_repo`, `customer_profile_repo`, `partner_profile_repo`, `address_repo`, `service_area_repo`, `service_repo`, `material_repo`, `service_material_repo`, `partner_capability_repo`, `pricing_rule_repo`, `material_pricing_rule_repo`, `operating_hours_repo`, `partner_availability_repo`, `pickup_slot_repo`, `delivery_slot_repo`, `pickup_slot_reservation_repo`, `delivery_slot_reservation_repo` |
| `washy_washy/dependencies` | Implemented: `get_current_user`, `require_role`, `require_permission` — wired since Phase 4 |
| `washy_washy/docs`, `washy_washy/static` | Implemented: branded `/docs`/`/redoc`, `custom_openapi` (tag metadata for all 11 tags + response-envelope description) |
| `washy_washy/utils` | Empty scaffold |
| Auth (`/auth/register\|login\|refresh`, JWT issuance/verification) | Implemented (Phase 2) |
| RBAC runtime (`require_role`/`require_permission`) | Implemented (Phase 3), enforced on `service-areas`/`roles`/`catalog`/`pricing`/`availability` writes; no authorization *middleware* (route-level `dependencies=[...]` only) |
| Admin role management (`GET /roles`, `GET/POST /users/{id}/roles`, `DELETE /users/{id}/roles/{name}`) | Implemented (post-Phase-4 addendum) — an admin cannot revoke their own `ADMIN` role |
| Catalog (`Service`/`Material`/compatibility/`PartnerCapability`) | Implemented (Phase 5) — `PartnerCapability` has a service layer but no API endpoint yet |
| Pricing (`PricingRule`/`MaterialPricingRule`/`calculate_price`) | Implemented (Phase 6) — no order to snapshot a computed price onto yet (Phase 8) |
| Availability (operating hours, partner availability, pickup/delivery slots + race-free capacity reservation) | Implemented (Phase 7) — `has_capable_partner` exists but is a global, unenforced check, not scoped to a service area (see §6j's documented scope gap; real enforcement needs Phase 9's partner↔area link) |
| Orders / Payments | Not started |
| Redis / Celery / APISIX | Not introduced |
| Docker (`docker compose up --build`) | **Verified** repeatedly, including with Phase 6's changes. Docker's engine has intermittently needed the `wsl --shutdown` + relaunch fix again (same root cause as before, not a new bug) — see the changelog below for the original diagnosis. |

Roadmap (see `README.md` for the full phase list): Phase 0 (foundation) →
Phase 1A–1D (database + identity/RBAC models) → Phase 2 Authentication →
Phase 3 RBAC runtime → Phase 4: Users/Profiles/Addresses/Service Areas →
admin role management addendum → Phase 5: Catalog → Phase 6: Pricing
Engine → **(this update) Phase 7: Availability / Slots / Capacity** →
Phase 8 Orders → ... → Phase 14 Production/AWS.

## 10. Changelog

- **2026-09-27 (latest)** — Phase 7, Availability / Slots / Capacity:
  - Added `core/models/{operating_hours,partner_availability,
    capacity_unit,pickup_slot,delivery_slot,pickup_slot_reservation,
    delivery_slot_reservation}.py` (`DayOfWeek`, `OperatingHours`,
    `PartnerAvailability`, `CapacityUnit`, `PickupSlot`, `DeliverySlot`,
    `ReservationStatus`, `PickupSlotReservation`,
    `DeliverySlotReservation`), all registered in
    `core/models/__init__.py`.
  - Added Alembic revision `01a11e11a45d` (head) — `operating_hours`,
    `partner_availabilities`, `pickup_slots`/`delivery_slots` (each with
    two `CHECK` constraints), `pickup_slot_reservations`/
    `delivery_slot_reservations`. Run against live PostgreSQL;
    `downgrade`/`upgrade` round-trip verified (tables confirmed gone via
    `\dt` after downgrade, back via `\d` after re-upgrade).
  - Added `washy_washy/repositories/{operating_hours,
    partner_availability,pickup_slot,delivery_slot,
    pickup_slot_reservation,delivery_slot_reservation}_repo.py` (the
    slot repos' `try_reserve_capacity`/`release_capacity` are the core
    mechanism — see §6j), a new `has_any_capability_for_service` method
    on the existing `partner_capability_repo.py`,
    `washy_washy/services/availability_service.py`
    (`AvailabilityService`), `washy_washy/schemas/availability.py`,
    `washy_washy/api/v1/{routes,controllers}/availability.py` — `GET/POST
    /service-areas/{id}/operating-hours`, `GET/POST
    /partners/{id}/availability`, `GET/POST
    /service-areas/{id}/{pickup,delivery}-slots`, `POST
    /{pickup,delivery}-slots/{id}/reservations`, `DELETE
    /{pickup,delivery}-slots/reservations/{id}`. Added
    `SLOT_CAPACITY_EXCEEDED`/`RESERVATION_NOT_ACTIVE` to
    `error_{codes,messages}.py`; added an `availability` tag to
    `docs/openapi.py`.
  - **Design decisions** (see §6j for full rationale): `PickupSlot`/
    `DeliverySlot` are genuinely separate tables, not one table with a
    discriminator column; capacity reservation is a single atomic
    conditional `UPDATE` (check-and-increment in one statement), not
    `SELECT FOR UPDATE` or a Redis-backed counter; reservations carry no
    `partner_profile_id`/`order_id` (out of scope until Phase 8/9 exist);
    ownership enforcement on cancel mirrors `AddressService`'s
    404-not-403 posture; `has_capable_partner` is a known, documented,
    *unenforced* scope gap (global, not area-scoped) rather than a
    silently-wrong area-scoped check.
  - Added `tests/unit/test_phase7_models.py`,
    `tests/integration/test_availability.py`, and
    `tests/integration/test_availability_concurrency.py` — the latter
    proves, under 10 genuinely concurrent booking attempts across
    independent database connections (not just sequential-logic
    assertions), that the atomic `UPDATE` actually prevents overbooking:
    exactly 3 of 10 attempts succeed against a slot with capacity for 3,
    and `capacity_reserved` never exceeds `capacity_total`.
  - **Not implemented, by design**: no partner-to-area or
    partner-to-order assignment (Phase 9), no order to attach a booking
    to (Phase 8), no enforcement of `has_capable_partner` inside the
    booking flow.
  - **Verification**: `ruff check .` and `ruff format --check .` clean;
    `pytest` — **265 passed, 0 failed** against live PostgreSQL (up from
    235). Migration round-trip run for real. Live `uvicorn` smoke test:
    registered an admin and a customer, granted `ADMIN` via direct SQL,
    confirmed a non-admin gets `403` creating a pickup slot, created one
    as admin, booked it as the customer (`capacity_reserved` moved
    `0` → `2`), cancelled it (`capacity_reserved` back to `0`), then
    cleaned up all test data.
- **2026-09-27** — Phase 6, Pricing Engine:
  - Added `core/models/{pricing_rule,material_pricing_rule}.py`
    (`PricingRule`/`PricingModel`, `MaterialPricingRule`), registered in
    `core/models/__init__.py`; added `care_adjustment` to
    `core/models/service_material.py` (Phase 5's table).
  - Added Alembic revision `f04acb897ec2` (head) — `pricing_rules`,
    `material_pricing_rules`, `ALTER TABLE service_materials ADD
    COLUMN care_adjustment`. Run against live PostgreSQL;
    `downgrade`/`upgrade` round-trip verified.
  - Added `washy_washy/repositories/{pricing_rule,material_pricing_rule}_repo.py`,
    `washy_washy/services/pricing_service.py` (`PricingService`,
    `PriceBreakdown`), `washy_washy/schemas/pricing.py`,
    `washy_washy/api/v1/{routes,controllers}/pricing.py` — `GET/POST
    /services/{id}/pricing`, `GET/POST /materials/{id}/pricing`, `POST
    /pricing/estimate`. Extended `CatalogService.set_compatibility`/
    `SetCompatibilityRequest` with `care_adjustment`. Added
    `NO_ACTIVE_PRICING_RULE`/`QUANTITY_REQUIRED`/`WEIGHT_REQUIRED`/
    `UNKNOWN_PRICING_MODEL` to `error_{codes,messages}.py`.
  - **Design decisions** (see §6i for full rationale): each pricing-rule
    row *is* a version (no separate version table); rush/delivery/tax/
    discount are `calculate_price` inputs, not stored rates;
    `care_adjustment` is not independently versioned; no separate
    estimate/final method (same call, different inputs) — persisting a
    computed price onto an order is deferred to Phase 8.
  - Added `tests/unit/test_phase6_models.py`,
    `tests/integration/test_pricing.py` (incl. a `Decimal`-vs-`float`
    precision regression check); extended
    `tests/api/test_protected_routes_require_auth.py` with
    `POST /pricing/estimate`.
  - **Not implemented, by design**: no order/invoice to snapshot a
    price onto, no tax/rush/delivery policy tables, no availability/
    capacity (Phase 7).
  - **Verification**: `ruff check .` clean (first try); `pytest` —
    **235 passed, 0 failed** against live PostgreSQL (up from 209).
    Migration round-trip run for real. Live `uvicorn` smoke test: a
    non-admin authenticated user gets `403` setting a service's price.
- **2026-09-27** — Phase 5, Catalog / Services / Materials:
  - Added `core/models/{service,material,service_material,
    partner_capability}.py`, all registered in `core/models/__init__.py`;
    added the back-reference relationship on `PartnerProfile`.
  - Added Alembic revision `368d5df746fb` (head) — `services`,
    `materials`, `service_materials`, `partner_capabilities`. Run
    against live PostgreSQL; `downgrade`/`upgrade` round-trip verified.
  - Added `washy_washy/repositories/{service,material,service_material,
    partner_capability}_repo.py`,
    `washy_washy/services/{catalog_service,partner_capability_service}.py`,
    `washy_washy/schemas/catalog.py`,
    `washy_washy/api/v1/{routes,controllers}/catalog.py` — `GET/POST
    /services`, `GET/PATCH /services/{id}`, `GET/POST
    /services/{id}/materials`, `DELETE .../materials/{mid}`, `GET/POST
    /materials`, `GET/PATCH /materials/{id}`, `GET
    /materials/{id}/services`. Added `SERVICE_NAME_ALREADY_EXISTS`/
    `MATERIAL_NAME_ALREADY_EXISTS`/`SERVICE_MATERIAL_ALREADY_EXISTS`/
    `PARTNER_CAPABILITY_ALREADY_EXISTS` to `error_{codes,messages}.py`.
  - **Design decisions** (see §6h for the full rationale): no
    `ServiceCategory` (no real grouping need); `ServiceMaterial` uses
    `TimestampMixin` (mutable care metadata) while `PartnerCapability`
    uses `CreatedAtMixin` (pure grant) — a deliberate split, not an
    inconsistency; customer-declared-vs-verified material is explicitly
    deferred to Phase 8's `OrderItem`; table renamed
    `partner_capabilities` (from a draft `partner_service_capabilities`)
    after checking constraint-name length against PostgreSQL's 63-byte
    identifier limit.
  - Added `tests/unit/test_phase5_models.py`,
    `tests/integration/test_catalog.py`; extended
    `tests/api/test_protected_routes_require_auth.py` with the new paths.
  - **Not implemented, by design**: no `PartnerCapability` API endpoint
    (service layer exists, tested, unexposed — Phase 5's own endpoint
    list doesn't ask for one), no pricing, no availability/capacity.
  - **Verification**: `ruff check .` clean; `pytest` — **209 passed, 0
    failed** against live PostgreSQL (up from 175). Live `uvicorn`
    smoke test: a non-admin authenticated user gets `403` creating a
    service but `200`s listing them.
- **2026-09-27** — Admin role management API (closes a gap
  Phase 3/4 explicitly left open):
  - Added `RBACService.{list_assignable_roles,get_user,get_user_by_email,
    grant_role_by_name,revoke_role_by_name}`; `washy_washy/schemas/role.py`
    (`GrantRoleRequest`, `RoleResponse`); `washy_washy/api/v1/
    {routes,controllers}/roles.py` — `GET /roles`, `GET/POST
    /users/{id}/roles`, `DELETE /users/{id}/roles/{name}`, all
    `ADMIN`-only via router-level `dependencies=[Depends(require_role(...))]`.
    Added `ROLE_ALREADY_ASSIGNED`/`ROLE_NOT_ASSIGNED`/
    `CANNOT_REMOVE_OWN_ADMIN_ROLE` to `error_{codes,messages}.py`.
  - Also picked up and finished a second pending improvement found
    already-drafted but uncommitted from an interrupted prior session:
    `core/exceptions/handlers.py`'s `RequestValidationError` handler now
    returns structured per-field errors (`{"errors": [{"field",
    "message", "type"}, ...]}` in `data`) instead of a bare message, and
    logs the failure — deliberately excluding Pydantic's raw `"input"`
    (can echo secrets like passwords) and `"ctx"` (can hold
    non-JSON-serializable objects).
  - Installed and configured **pre-commit** per an explicit request:
    `.pre-commit-config.yaml` (check-yaml, end-of-file-fixer,
    trailing-whitespace, detect-private-key, pretty-format-json, ruff,
    ruff-format), `pre-commit install` run (hook active at
    `.git/hooks/pre-commit`), added to `pyproject.toml` dev deps.
    `pre-commit run --all-files` passed clean; ruff-format reformatted
    a number of files (collapsing short multi-line calls) as a
    one-time consequence of enabling it — not a logic change.
  - **Verification**: `ruff check .` clean; `pytest` — **175 passed, 0
    failed** against live PostgreSQL (up from 163 — 12 new role-
    management tests). Live `uvicorn` smoke test: registered a user,
    granted them `ADMIN` via direct SQL (the only way in, by design),
    confirmed `GET /roles` lists all four seeded roles, and confirmed
    the self-revoke protection returns `422
    CANNOT_REMOVE_OWN_ADMIN_ROLE`. Docker Desktop's engine had stopped
    again since the last verification (same intermittent WSL2 issue,
    not a new bug) — recovered with the documented `wsl --shutdown` +
    relaunch fix, then re-verified against the container's Postgres too.
- **2026-09-23** — Phase 4, Users / Profiles / Addresses /
  Service Areas:
  - Added `core/models/{customer_profile,partner_profile,address,
    service_area,service_area_postal_code}.py`
    (`CustomerProfile`, `PartnerProfile`/`PartnerStatus`,
    `Address`/`AddressLabel`, `ServiceArea`, `ServiceAreaPostalCode`),
    all registered in `core/models/__init__.py`.
  - Added Alembic revisions `3587faef9553` (profile + address tables,
    including the partial unique default-address index) and
    `9ad4f2884494` (service area tables, head). Both hand-written, and
    both actually run — `upgrade`, `downgrade -2`, `upgrade` again —
    against a live PostgreSQL in this session (see §"Migrations").
  - Added `washy_washy/repositories/{customer_profile,partner_profile,
    address,service_area}_repo.py` and
    `washy_washy/services/{profile,address,service_area}_service.py`.
  - Added `washy_washy/api/v1/{routes,controllers}/{users,customers,
    addresses,service_areas}.py`, wired into `api_v1_router` — the
    first real protected endpoints in this project. Added
    `washy_washy/schemas/{profile,address,service_area}.py`.
  - `washy_washy/constants/error_{codes,messages}.py`: added
    `CUSTOMER_PROFILE_ALREADY_EXISTS`, `PARTNER_PROFILE_ALREADY_EXISTS`,
    `SERVICE_AREA_NAME_ALREADY_EXISTS`.
  - `washy_washy/docs/openapi.py`: added `TAGS_METADATA` entries for
    `users`/`customers`/`addresses`/`service-areas`; updated
    `API_DESCRIPTION` to reflect that most endpoints now require
    authentication.
  - **Fixed a real bug this phase's own code surfaced** (not
    pre-existing/latent from an earlier phase): `core/models/mixins.py::
    CreatedAtMixin` now sets `__mapper_args__ = {"eager_defaults": True}`
    (inherited by every model). Without it, creating an address with
    `is_default=true` (INSERT then, same request, a default-flip UPDATE)
    left `updated_at` "expired" after the UPDATE; serializing it via
    `AddressResponse.model_validate(...)` — a synchronous Pydantic call,
    exactly what the real controller does — raised `MissingGreenlet`
    (a 500), even though the row was correctly written and committed.
    Found via live `uvicorn` smoke testing of the actual HTTP flow (the
    integration test suite's existing `is_default=true` test didn't
    touch `updated_at` and so didn't catch it); fixed; then a genuine
    regression test was added and confirmed to fail against the
    pre-fix code before being left in place. Full explanation in §6f.
  - **Not implemented, by design**: `/partners/me` endpoint (model/
    repo/service exist, unexposed — Phase 4's own endpoint list doesn't
    include one), authorization middleware (route-level
    `dependencies=[...]` only), any admin API for granting roles,
    serviceability-gated address creation (informational only, per
    spec), catalog/orders/payments/any other domain.
  - **Verification**: `ruff check .` clean. `pytest` — **163 passed, 0
    skipped, 0 failed** against live PostgreSQL (up from 114 — 48 new
    Phase 4 tests, all passing, none skipped). Migration round-trip run
    for real (`upgrade`/`downgrade -2`/`upgrade`), schema inspected
    directly via `psql`. Full HTTP happy path smoke-tested via a
    running `uvicorn` instance: register → login → `/users/me` →
    create customer profile → create two addresses (one triggering the
    default-flip bug above, confirmed fixed) → list addresses (exactly
    one `is_default=true`) → `POST /service-areas` as a non-admin
    correctly 403s. Docker rebuilt and re-verified end-to-end with all
    of the above (`docker compose up -d --build`, migrations applied
    inside the `api` container, registration + address flow hit through
    the container on port `8080`). Test-only user data cleaned up from
    the dev database afterward.
- **2026-09-22** — Test suite reliability fix (infra/tooling):
  - **Found and fixed the real reason integration tests kept reporting
    "skipped" across every phase in this environment**, even after
    Docker/Postgres genuinely became reachable in the two entries below:
    `tests/conftest.py` set `DATABASE_URL`/`JWT_SECRET` via
    `os.environ.setdefault(...)`, which — since an OS env var always
    outranks `CoreSettings`' `.env` file — permanently shadowed the
    real, already-correct `.env` (its `POSTGRES_PASSWORD` differs from
    the hardcoded fallback's) for any shell that didn't already have
    `DATABASE_URL` exported. Every DB connection then failed
    authentication, and `db_session`'s broad exception handler reported
    that as "PostgreSQL is not reachable" — indistinguishable from a
    genuinely absent database. See §8 for the full explanation and fix
    (only apply the fallback when no `.env` file exists).
  - **Verified**: `ruff check .` clean; `pytest` — **114 passed, 0
    skipped, 0 failed**, reproducibly, from a cold shell with nothing
    pre-exported (not contingent on shell history like the two entries
    below were). No application code changed — this was purely a test
    fixture bug.
- **2026-09-22** — Docker fully verified (infra/tooling):
  - **Root-caused why Docker Desktop's engine never started in this
    environment**, instead of continuing to treat it as unavailable:
    `com.docker.backend.exe.log` showed `dockerd failed to start:
    resolving host IP: resolving host.docker.internal: ... i/o timeout`
    — the engine's own internal DNS proxy inside its WSL2 VM was
    unreachable. A plain Docker Desktop app restart (tried in every
    earlier session) does not fix this because it never resets WSL's
    network state. Fix: fully quit Docker Desktop's processes, `wsl
    --shutdown` (tears down and rebuilds the whole WSL2 subsystem,
    including networking), relaunch — engine came up in ~20s.
  - **Found and fixed a second, independent bug this then uncovered**:
    `.dockerignore` excluded `tests/` and `README.md`, but `Dockerfile`
    explicitly `COPY`s both (`README.md` because `pyproject.toml`'s
    `readme=` field makes `pip install .` require it present) —
    `docker compose up --build` had never actually succeeded in any
    prior session (every earlier phase's changelog just recorded "no
    reachable Docker daemon," never got far enough to hit this). Fixed
    by un-ignoring both in `.dockerignore`.
  - `docker-compose.yml`: `api`'s host port moved from `8000` to `8080`
    (container still listens on `8000` — `Dockerfile`/`main.py`
    unchanged) — `8000` collides with an unrelated project's own compose
    stack already running on this machine; not something to fight over
    on a shared dev box.
  - **Verified, for real, via running containers** (not just `docker
    compose config`'s syntax check, which is all any earlier session
    managed): `docker compose up -d --build` brings up `postgres`
    (healthy) and `api`; `docker exec washy_washy-api-1 python -m
    alembic upgrade head` applied all 3 revisions against the
    containerized Postgres — same 6 tables + 4 seeded roles as the
    non-Docker verification below; `curl localhost:8080/api/v1/health/
    ready` → `"postgres": true`; `/docs` → 200.
- **2026-09-22** — DB verification + Swagger/ReDoc branding
  (infra/tooling, not a numbered domain phase):
  - **Verified the database foundation end-to-end for the first time**:
    Docker Desktop's engine still doesn't come up in this sandbox (tried
    again — full restart, ~5 min wait, same failure as every earlier
    phase), so used a portable, admin-rights-free PostgreSQL
    (`postgresql-binaries` on PyPI, dev/CI tool only, not a project
    dependency) to actually run one. `alembic upgrade head` applied
    cleanly; verified all 6 tables and the 4 seeded roles directly via
    `psql`; full `pytest` suite: **114 passed, 0 skipped, 0 failed**
    (previously always partially skipped for lack of a reachable DB).
  - **Found and fixed two real bugs, both latent since earlier phases and
    only visible once tests actually ran against a live database** (see
    §6b/§8 and §8 for full detail):
    1. `tests/integration/conftest.py`'s `db_session` fixture called
       `connection.begin()` *after* a `SELECT` had already run on the
       connection — SQLAlchemy 2.0 "autobegin" made that raise
       `InvalidRequestError`. Fixed by moving `begin()` first.
    2. `pyproject.toml` was missing an explicit pytest-asyncio event-loop
       scope, so each async test got its own event loop while
       `core/database/engine.py`'s cached `AsyncEngine`/session-factory
       singletons (and their asyncpg connections) stayed loop-bound from
       the first test — later tests intermittently failed. Fixed by
       setting `asyncio_default_fixture_loop_scope = "session"` and
       `asyncio_default_test_loop_scope = "session"`.
  - Added Swagger/ReDoc branding: `washy_washy/docs/openapi.py`
    (`custom_openapi`, `TAGS_METADATA`, `API_DESCRIPTION`),
    `washy_washy/docs/swagger_ui.py` (branded `/docs`/`/redoc` routes,
    replacing FastAPI's defaults — `main.py` now sets `docs_url=None,
    redoc_url=None`), `washy_washy/static/{swagger-custom.css,
    favicon.svg}`, mounted at `/static`. See §6e for the full design.
  - Added a "Local PostgreSQL without Docker (fallback)" section to
    `README.md` documenting the `postgresql-binaries` path used above,
    for whoever hits the same broken-Docker-Desktop situation.
  - **Verification**: `ruff check .` clean; `pytest` 114/114 passing
    against a live, migrated PostgreSQL (see above); manually hit
    `/docs`, `/redoc`, `/openapi.json`, `/static/swagger-custom.css`,
    `/static/favicon.svg` on a running `uvicorn` instance — all 200,
    correct content-types, branded header present in both docs pages'
    HTML, `openapi.json`'s `tags`/`info.version` match `TAGS_METADATA`/
    `APP_VERSION`. `docker compose up --build` **still not run** — see
    the Current Status table.
- **2026-09-22** — Phase 3, RBAC Runtime:
  - Added `washy_washy/services/rbac_service.py` (`RBACService`:
    `get_user_roles`, `get_user_permissions`, `has_role`,
    `has_permission`, `assign_role`, `remove_role`) and
    `washy_washy/dependencies/rbac.py` (`require_role`,
    `require_permission` — dependency factories built on Phase 2's
    `get_current_user`, raising `ForbiddenException`/403 when the
    role/permission isn't granted). Both exported from
    `washy_washy/dependencies/__init__.py`.
  - Added `tests/integration/test_rbac_runtime.py`.
  - **Not implemented, by design**: no route uses `require_role`/
    `require_permission` (no protected endpoint exists to attach one
    to), no authorization middleware, no admin API for managing role or
    permission assignments.
  - **Verification**: `ruff check .` clean; confirmed no new HTTP routes
    were introduced (RBAC is dependency-only this phase) via the
    OpenAPI schema; `pytest` — 63 passed, 51 skipped (up from 38 skipped
    in Phase 2 — the 13 new `test_rbac_runtime.py` tests are all
    Postgres-dependent and correctly skip, not fail, without a live DB;
    no reachable PostgreSQL/Docker daemon in this sandbox, same
    limitation as every phase so far) — recommend running them before
    merging.
- **2026-09-22 (Phase 2)** — Phase 2, Authentication:
  - Added `washy_washy/schemas/auth.py` (`RegisterRequest`,
    `LoginRequest`, `RefreshTokenRequest`, `UserResponse`,
    `TokenResponse`), `washy_washy/services/auth_service.py`
    (`AuthService`, plus shared `decode_or_raise`/`parse_subject_uuid`
    helpers), `washy_washy/api/v1/controllers/auth.py`,
    `washy_washy/api/v1/routes/auth.py` (`POST /api/v1/auth/{register,
    login,refresh}`, wired into `api_v1_router`), and a new
    `washy_washy/dependencies/` package with `auth.py::get_current_user`.
  - `core/security/security.py`: added `TokenExpiredError`,
    `TokenInvalidError`, `decode_token_strict` (additive — `decode_token`
    unchanged).
  - `washy_washy/constants/error_codes.py`/`error_messages.py`: added
    `AUTH_INVALID_CREDENTIALS`, `AUTH_TOKEN_INVALID`,
    `AUTH_TOKEN_EXPIRED`, `AUTH_REFRESH_TOKEN_REQUIRED`,
    `AUTH_USER_INACTIVE`, `AUTH_EMAIL_ALREADY_EXISTS`,
    `AUTH_PHONE_ALREADY_EXISTS`.
  - **Fixed a real, pre-existing bug**: `pyproject.toml`'s
    `bcrypt>=4.1.0` (from Phase 0) is incompatible with
    `passlib==1.7.4` and made `hash_password`/`verify_password` raise on
    first use; repinned to `bcrypt>=4.0.0,<4.1` and reinstalled. This had
    been latent since Phase 0 because nothing called those functions
    before this phase's tests did. See §6c for the full explanation.
  - Added `tests/unit/test_auth_tokens_and_schemas.py`,
    `tests/integration/test_auth.py`, `tests/api/test_auth_routes.py`
    (first file in the previously-empty `tests/api/`).
  - **Not implemented, by design**: `require_role`/`require_permission`,
    any authorization/permission-enforcement middleware, any protected
    endpoint, refresh-token rotation/persistent storage, logout,
    email-verification/password-reset workflows.
  - **Verification**: `ruff check .` and `pytest` both run clean in this
    environment (63 passed, 38 skipped — skips are the Postgres-dependent
    integration tests; no live PostgreSQL/Docker daemon available here,
    same limitation as Phase 1). All three auth endpoints were smoke
    tested against a running `uvicorn` instance (validation paths, and
    the refresh endpoint's expired/invalid/wrong-token-type handling,
    using hand-crafted JWTs) — register/login's actual database
    round-trip was **not** exercised live in this session; recommend
    running `tests/integration/test_auth.py` against a real DB before
    merging.
- **2026-09-22 (Phase 1)** — Phase 1, Complete Database Foundation
  (Phase 1B–1D — User identity + RBAC persistence, on top of the
  Phase 1A foundation):
  - Added `core/models/user.py` (`User`), `core/models/role.py`
    (`Role`, `RoleName`), `core/models/permission.py` (`Permission`,
    `PermissionScope`), `core/models/user_role.py` (`UserRole`),
    `core/models/role_permission.py` (`RolePermission`). All registered
    in `core/models/__init__.py` for Alembic discovery.
  - `core/models/mixins.py`: extracted `CreatedAtMixin` (previously
    inline in `TimestampMixin`) so association tables can have
    `created_at` without `updated_at`; `TimestampMixin` now subclasses it
    — no behavior change for existing users of `TimestampMixin`.
  - Added 3 Alembic revisions (`0a91544a311e`, `e8dc958f2e5e`,
    `db9e1e1a26b8` — head) creating `users`/`roles`/`permissions`, then
    `user_roles`/`role_permissions`, then seeding the four foundational
    roles idempotently. See §6b and §"Migrations" for details.
  - `core/migrations/script.py.mako`: modernized generated-revision
    imports (`str | None`, `collections.abc.Sequence`) so future
    `alembic revision` output passes this project's ruff config
    out of the box — a Phase 0 template gap this phase needed fixed.
  - Added `washy_washy/repositories/{user,role,permission,user_role,
    role_permission}_repo.py`.
  - Added `tests/unit/test_rbac_models.py`,
    `tests/integration/conftest.py` (`db_session` fixture),
    `tests/integration/test_user_identity.py`,
    `tests/integration/test_rbac_associations.py`.
  - **Not implemented, by design**: any `/auth/*` endpoint, JWT
    issuance/verification workflow, `get_current_user`/`require_role`/
    `require_permission`, permission-enforcement middleware, permission
    seed data (only roles are seeded), Customer/Partner profile models,
    or any other domain model.
  - **Verification gap**: no PostgreSQL instance and no running Docker
    daemon were available in this environment, so the actual
    `alembic upgrade head` / `downgrade -1` / `upgrade head` round-trip
    and `docker compose up --build` were **not** executed — only
    `alembic heads`/`history` (chain validity, no DB needed) and the
    unit test suite were run. The three integration test files exist and
    are ready to run once a database is available; they were not
    executed successfully in this session (they skip, not fail, without
    one). Recommend running both before merging.
- **2026-09-22 (Phase 1A)** — Production Database Foundation:
  - `core/database/base.py`: added deterministic naming convention
    (`ix`/`uq`/`ck`/`fk`/`pk`) to `Base.metadata`.
  - Added `core/models/mixins.py`: `UUIDPrimaryKeyMixin`,
    `TimestampMixin`. Exported from `core/models/__init__.py`.
  - `alembic.ini`: added `path_separator = os` (removes an Alembic
    deprecation warning; no behavior change).
  - Added `tests/unit/test_database_foundation.py`,
    `tests/unit/test_alembic_wiring.py`,
    `tests/integration/test_database_connection.py`.
  - No domain models, migrations, request-flow, Docker, or dependency
    changes. `core/models/base.py` remains a thin re-export of the one
    canonical `Base` (no second `Base` was created).
- **2026-09-22 (earlier)** — Initial version of this document, written
  against the Phase 0 foundation (health-check vertical slice only; all
  services/repositories/utils empty scaffolds).
