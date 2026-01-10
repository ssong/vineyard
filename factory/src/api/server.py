"""FastAPI server for webhook endpoints."""

import logging
import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.config import settings

logger = logging.getLogger(__name__)

# Rate limiter configuration
# Use Redis for rate limiting if available, otherwise fall back to in-memory
REDIS_URL = os.getenv("REDIS_URL")

def _get_rate_limit_storage() -> str:
    """Get the storage URI for rate limiting."""
    if not REDIS_URL:
        return "memory://"
    # slowapi expects redis:// format (not rediss:// for TLS)
    # For TLS connections, you may need to configure Redis separately
    return REDIS_URL

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],  # Default rate limit
    storage_uri=_get_rate_limit_storage(),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Vineyard Factory API server...")
    storage_type = "Redis" if REDIS_URL else "in-memory"
    logger.info(f"Rate limiting enabled: 100 requests/minute per IP (storage: {storage_type})")
    yield
    logger.info("Shutting down Vineyard Factory API server...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Vineyard Factory API",
        description="Webhook endpoints for Linear and other integrations",
        version="1.0.0",
        lifespan=lifespan,
        # Security: Don't expose detailed errors in production
        debug=False,
    )

    # Add rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # Import and include routers
    from src.api.webhooks import router as webhooks_router

    app.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])

    # Health check endpoint (exempt from rate limiting)
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "vineyard-factory"}

    # Custom error handler for security
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        """Handle uncaught exceptions without leaking details."""
        logger.exception("Unhandled exception in request")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

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
