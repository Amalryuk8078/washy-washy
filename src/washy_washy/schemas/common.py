"""Shared API response envelopes.

Every endpoint returns one of these shapes so consumers (Flutter apps, admin
web) can rely on a single, predictable response contract.
"""

from pydantic import BaseModel


class SuccessResponse[DataT](BaseModel):
    success: bool = True
    message: str = "Request successful"
    data: DataT | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    code: str
    data: None = None
