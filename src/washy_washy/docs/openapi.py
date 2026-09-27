"""Custom OpenAPI schema: tag metadata + a branded top-level description.

FastAPI regenerates ``app.openapi()`` on every call by default; this
caches the schema on ``app.openapi_schema`` after the first build (the
same pattern FastAPI's own docs recommend for a custom ``openapi()``).
"""

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

TAGS_METADATA: list[dict[str, Any]] = [
    {
        "name": "root",
        "description": "Service identity — confirms the API is up and links to the docs.",
    },
    {
        "name": "health",
        "description": "Liveness/readiness probes. `/health/ready` also checks PostgreSQL "
        "connectivity — used by orchestrators and uptime monitoring, not by API consumers.",
    },
    {
        "name": "auth",
        "description": "Registration, login, and JWT access/refresh token issuance.",
    },
    {
        "name": "users",
        "description": "The authenticated caller's own identity.",
    },
    {
        "name": "customers",
        "description": "The authenticated caller's own customer profile (separate from identity "
        "— see `core/models/customer_profile.py`).",
    },
    {
        "name": "addresses",
        "description": "The authenticated caller's own pickup/delivery addresses. "
        "A caller can only ever see or modify their own.",
    },
    {
        "name": "service-areas",
        "description": "Where Washy Washy operates. Reading is open to any authenticated "
        "caller; creating a new one requires the `ADMIN` role.",
    },
    {
        "name": "catalog",
        "description": "Services, materials, and their compatibility. Reading is open to any "
        "authenticated caller; writes require the `ADMIN` role.",
    },
    {
        "name": "roles",
        "description": "Admin-only role management — granting/revoking roles on other users. "
        "Every operation here requires the `ADMIN` role.",
    },
]

API_DESCRIPTION = """
Backend API for **Washy Washy**, a laundry-service platform.

Currently exposes the Phase 0–4 foundation: health checks,
authentication/JWT issuance, and the user/profile/address/service-area
domain. `Bearer <access_token>` authorization is required by every
endpoint below except health checks and `/auth/register|login|refresh`
— see each tag's description for anything further restricted (e.g.
`service-areas`' `ADMIN`-only write). Further domain features (catalog,
orders, payments, ...) land in later phases.
"""

_RESPONSE_ENVELOPE_NOTE = """
---

Every endpoint returns one of two response shapes:

**Success**
```json
{"success": true, "message": "Request successful", "data": { }}
```

**Error**
```json
{"success": false, "message": "Resource not found", "code": "NOT_FOUND", "data": null}
```

`code` is a stable, machine-readable string (see `washy_washy/constants/error_codes.py`) —
build client-side error handling against `code`, not `message`.
"""


def custom_openapi(
    app: FastAPI,
    tags: list[dict[str, Any]],
    title: str,
    version: str,
    description: str = "",
) -> dict[str, Any]:
    """Build (and cache) the OpenAPI schema with tag metadata + description.

    Args:
        app: the FastAPI instance whose routes back the schema.
        tags: OpenAPI tag metadata, `[{"name": ..., "description": ...}, ...]`.
        title: API title.
        version: API version string.
        description: markdown description shown above the operation list;
            the response-envelope note is appended automatically.

    Returns:
        The (possibly cached) OpenAPI schema dict.
    """
    if app.openapi_schema:
        return app.openapi_schema

    app.openapi_schema = get_openapi(
        title=title,
        version=version,
        description=description + _RESPONSE_ENVELOPE_NOTE,
        routes=app.routes,
        tags=tags,
    )
    return app.openapi_schema
