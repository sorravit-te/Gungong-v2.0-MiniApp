"""Health check router."""

from fastapi import APIRouter
from pydantic import BaseModel
from ..core.config import get_settings

router = APIRouter()
settings = get_settings()


class HealthCheckResponse(BaseModel):
    """Health check response model."""
    status: str = "ok"
    app_name: str


@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    return HealthCheckResponse(app_name=settings.app_name)
