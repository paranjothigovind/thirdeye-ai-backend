"""Main FastAPI application entry point"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.core.config import settings
from app.core.logging import setup_logging
from app.api import routes_chat, routes_ingest, routes_jobs, routes_health, routes_graph

# For Vercel deployment, use WSGI
if os.getenv("VERCEL"):
    from fastapi.middleware.wsgi import WSGIMiddleware

# Setup logging
setup_logging()

# Create FastAPI app
app = FastAPI(
    title="Third Eye Meditation AI Chatbot",
    description="RAG-powered chatbot for Third Eye (Ajna) meditation guidance",
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

# Mount static files for UI
static_path = os.path.join(os.path.dirname(__file__), "ui", "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")
    
    @app.get("/")
    async def serve_ui():
        """Serve the main UI"""
        return FileResponse(os.path.join(static_path, "index.html"))

# For Vercel deployment, wrap with WSGI
if os.getenv("VERCEL"):
    app = WSGIMiddleware(app)

# For Railway deployment, use dynamic port
if os.getenv("RAILWAY_ENVIRONMENT"):
    port = int(os.getenv("PORT", 8000))
    if __name__ == "__main__":
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=port,
            reload=False
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.APP_ENV == "development"
    )
