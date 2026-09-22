"""Shared exception types and FastAPI exception handlers.

These are generic, HTTP-shaped exceptions (NotFound, Conflict, ...). They
carry no Washy Washy business meaning and must stay free of any import from
``washy_washy`` so ``core`` remains independent of the service package.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppException(Exception):
    """Base class for all predictable, handled application errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_SERVER_ERROR"

    def __init__(self, message: str, code: str | None = None) -> None:
        self.message = message
        if code is not None:
            self.code = code
        super().__init__(message)


class ValidationException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "VALIDATION_ERROR"


class UnauthorizedException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "UNAUTHORIZED"


class ForbiddenException(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"


class NotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class ConflictException(AppException):
    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"


class BusinessRuleException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "BUSINESS_RULE_ERROR"


class InternalErrorException(AppException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "INTERNAL_SERVER_ERROR"


def _error_body(message: str, code: str) -> dict:
    return {"success": False, "message": message, "code": code, "data": None}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.message, exc.code),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_body("Request validation failed", "VALIDATION_ERROR"),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception while processing request", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("An unexpected error occurred", "INTERNAL_SERVER_ERROR"),
        )
