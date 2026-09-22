"""Branded ``/docs`` and ``/redoc`` pages.

``main.py`` disables FastAPI's default ``docs_url``/``redoc_url``; these
routes replace them so the docs load Washy Washy's own stylesheet/favicon
and a branded header, layered on top of the stock swagger-ui-dist/ReDoc
assets rather than replacing them outright.
"""

from fastapi import APIRouter
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse

router = APIRouter(include_in_schema=False)

SWAGGER_CSS_URL = "/static/swagger-custom.css"
FAVICON_URL = "/static/favicon.svg"

_BRAND_HEADER = """
<header class="ww-header">
  <a class="ww-header__brand" href="/">
    <svg class="ww-header__logo" viewBox="0 0 32 32" fill="none"
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <circle cx="16" cy="16" r="15" stroke="currentColor" stroke-width="2"/>
      <circle cx="16" cy="16" r="7" stroke="currentColor" stroke-width="2"/>
      <circle cx="16" cy="16" r="2.4" fill="currentColor"/>
      <path d="M16 3v3.2M16 25.8V29M3 16h3.2M25.8 16H29" stroke="currentColor"
            stroke-width="2" stroke-linecap="round"/>
    </svg>
    <span class="ww-header__title">Washy Washy API</span>
  </a>
  <nav class="ww-header__nav">
    <a href="/docs">Swagger</a>
    <a href="/redoc">Reference</a>
    <a href="/openapi.json">OpenAPI JSON</a>
  </nav>
</header>
"""


@router.get("/docs", include_in_schema=False)
async def swagger_ui() -> HTMLResponse:
    response = get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Washy Washy API — Swagger",
        swagger_favicon_url=FAVICON_URL,
        swagger_ui_parameters={
            "persistAuthorization": True,
            "displayRequestDuration": True,
            "docExpansion": "list",
            "filter": True,
            "tryItOutEnabled": True,
        },
    )
    body = response.body.decode()
    body = body.replace(
        "</head>",
        f'<link rel="stylesheet" href="{SWAGGER_CSS_URL}">\n</head>',
    ).replace(
        "<body>",
        f"<body>\n{_BRAND_HEADER}",
    )
    return HTMLResponse(body)


@router.get("/redoc", include_in_schema=False)
async def redoc() -> HTMLResponse:
    response = get_redoc_html(
        openapi_url="/openapi.json",
        title="Washy Washy API — Reference",
        redoc_favicon_url=FAVICON_URL,
    )
    body = response.body.decode()
    body = body.replace(
        "</head>",
        f'<link rel="stylesheet" href="{SWAGGER_CSS_URL}">\n</head>',
    ).replace(
        "<body>",
        f"<body>\n{_BRAND_HEADER}",
    )
    return HTMLResponse(body)
