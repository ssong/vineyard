"""FastAPI server for webhook endpoints."""

import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Vineyard Factory API server...")
    yield
    logger.info("Shutting down Vineyard Factory API server...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Vineyard Factory API",
        description="Webhook endpoints for Linear and other integrations",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Import and include routers
    from src.api.webhooks import router as webhooks_router

    app.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "vineyard-factory"}

    return app


def start_server(host: str = "0.0.0.0", port: int = 8000):
    """Start the API server."""
    app = create_app()
    logger.info(f"Starting API server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


async def start_server_async(host: str = "0.0.0.0", port: int = 8000):
    """Start the API server asynchronously (for running alongside other async tasks)."""
    app = create_app()
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()
