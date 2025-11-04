"""Health check endpoints"""
from fastapi import APIRouter, status
from pydantic import BaseModel
from datetime import datetime

from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    version: str = "1.0.0"


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat()
    )


@router.get("/ready", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def readiness_check():
    """Readiness check endpoint"""
    # TODO: Add checks for dependencies (Azure services, Redis, etc.)
    return HealthResponse(
        status="ready",
        timestamp=datetime.utcnow().isoformat()
    )