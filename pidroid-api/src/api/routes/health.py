"""Health check routes."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Health check",
    description="Check if the API is running",
    response_description="Status of the API",
)
async def health_check() -> dict[str, str]:
    """Return the health status of the API."""
    return {"status": "ok"}
