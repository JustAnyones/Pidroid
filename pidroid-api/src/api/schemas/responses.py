"""Response schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response."""

    status: str


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str
