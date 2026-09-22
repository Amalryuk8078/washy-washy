"""FastAPI application construction.

This module owns app wiring only: lifespan, middleware, CORS, routers, and
exception handlers. Business logic, database queries, and route handlers do
not belong here.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.exceptions import register_exception_handlers
from core.logging import configure_logging
from core.middleware import RequestIDMiddleware
from washy_washy.api.v1 import api_v1_router
from washy_washy.config import get_settings
from washy_washy.docs.openapi import API_DESCRIPTION, TAGS_METADATA, custom_openapi
from washy_washy.docs.swagger_ui import router as docs_router
from washy_washy.schemas.common import SuccessResponse

APP_VERSION = "0.1.0"
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=APP_VERSION,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(docs_router)

    def _openapi() -> dict:
        return custom_openapi(
            app,
            tags=TAGS_METADATA,
            title=settings.app_name,
            version=APP_VERSION,
            description=API_DESCRIPTION,
        )

    app.openapi = _openapi

    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    @app.get("/", response_model=SuccessResponse, tags=["root"])
    async def root() -> SuccessResponse:
        return SuccessResponse(
            message=f"{settings.app_name} is running",
            data={"docs": "/docs", "health": f"{settings.api_v1_prefix}/health"},
        )

    return app


app = create_app()
