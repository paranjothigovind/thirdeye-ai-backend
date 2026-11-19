"""Main FastAPI application entry point"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.core.config import settings
from app.core.logging import get_logger, setup_logging

# Setup logging before importing routes: route modules create the LLM provider
# at import time, and its configuration warnings must use the JSON format.
setup_logging()
startup_logger = get_logger("app.startup")

from app.api import (  # noqa: E402
    routes_chat,
    routes_ingest,
    routes_jobs,
    routes_health,
    routes_graph,
    routes_auth,
    routes_lms_catalog,
    routes_lms_admin,
    routes_lms_learner,
    routes_lms_payments,
)

from app.models.provider_factory import close_llm_provider  # noqa: E402


def log_startup_warnings() -> list[str]:
    """Warn about configurations that are unsafe for a public deployment."""
    from app.rag.guardrails import guardrails

    warnings = []
    if settings.LLM_PROVIDER == "anthropic" and not settings.LLM_DAILY_TOKEN_BUDGET:
        warnings.append("LLM_PROVIDER=anthropic with no LLM_DAILY_TOKEN_BUDGET: daily Claude spend is not capped")
    if not settings.RATE_LIMIT_ENABLED:
        warnings.append("RATE_LIMIT_ENABLED=false: public chat endpoints have no rate limits")
    if settings.RATE_LIMIT_ENABLED and settings.USAGE_STORE == "memory":
        warnings.append("USAGE_STORE=memory: limits are per process; use USAGE_STORE=redis with several instances")
    if not guardrails.policy.contacts:
        warnings.append("No approved emergency contacts (EMERGENCY_POLICY_FILE): generic emergency guidance is shown")
    if not guardrails.policy.keywords:
        warnings.append("No reviewed regional emergency keywords: emergency detection is English-only")
    for warning in warnings:
        startup_logger.warning(warning)
    return warnings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Log configuration warnings; release the LLM provider's HTTP resources on shutdown."""
    log_startup_warnings()
    yield
    await close_llm_provider()


# Create FastAPI app
app = FastAPI(
    lifespan=lifespan,
    title="Nettrikkan AI Chatbot",
    description="RAG-powered chatbot for Nettrikkan (Inner Awareness) teachings",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(routes_health.router, prefix="/api", tags=["health"])
app.include_router(routes_chat.router, prefix="/api", tags=["chat"])
app.include_router(routes_graph.router, prefix="/api", tags=["chat-advanced"])
app.include_router(routes_ingest.router, prefix="/api", tags=["ingestion"])
app.include_router(routes_jobs.router, prefix="/api", tags=["jobs"])
app.include_router(routes_auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(routes_lms_catalog.router, prefix="/api/lms/catalog", tags=["lms-catalog"])
app.include_router(routes_lms_admin.router, prefix="/api/lms/admin", tags=["lms-admin"])
app.include_router(routes_lms_learner.router, prefix="/api/lms/learner", tags=["lms-learner"])
app.include_router(routes_lms_payments.router, prefix="/api/lms/payments", tags=["lms-payments"])


# Mount static files for UI
static_path = os.path.join(os.path.dirname(__file__), "ui", "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")
    
    @app.get("/")
    async def serve_ui():
        """Serve the main UI"""
        return FileResponse(os.path.join(static_path, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.APP_ENV == "development"
    )
