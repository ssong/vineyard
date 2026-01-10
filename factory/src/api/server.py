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
        logger.info("No REDIS_URL set, using in-memory rate limiting storage")
        return "memory://"
    logger.info(f"Using Redis for rate limiting: {REDIS_URL.split('@')[-1]}")
    return REDIS_URL

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],  # Default rate limit
    storage_uri=_get_rate_limit_storage(),
)


def custom_rate_limit_handler(request: Request, exc: Exception):
    """Custom rate limit handler that handles connection errors gracefully."""
    if isinstance(exc, RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"error": f"Rate limit exceeded: {exc.detail}"}
        )
    else:
        # Handle connection errors or other exceptions gracefully
        logger.warning(f"Rate limiter error (not rate limit): {type(exc).__name__}: {exc}")
        # Let the request through if rate limiter has issues
        return None


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

    # Add rate limiter with custom handler
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)
    
    # Add handlers for connection issues to prevent slowapi crashes
    @app.exception_handler(ConnectionError)
    async def connection_error_handler(request: Request, exc: ConnectionError):
        logger.warning(f"Connection error in request: {exc}")
        return JSONResponse(
            status_code=503,
            content={"detail": "Service temporarily unavailable"}
        )
    
    @app.exception_handler(TimeoutError)
    async def timeout_error_handler(request: Request, exc: TimeoutError):
        logger.warning(f"Timeout error in request: {exc}")
        return JSONResponse(
            status_code=504,
            content={"detail": "Gateway timeout"}
        )
    
    @app.exception_handler(OSError)
    async def os_error_handler(request: Request, exc: OSError):
        logger.warning(f"OS error in request: {exc}")
        return JSONResponse(
            status_code=503,
            content={"detail": "Service temporarily unavailable"}
        )
    
    # Test Redis connection before enabling middleware
    redis_available = False
    if REDIS_URL:
        try:
            import redis
            r = redis.from_url(REDIS_URL, socket_timeout=2)
            r.ping()
            redis_available = True
            logger.info("Redis connection verified for rate limiting")
        except Exception as e:
            logger.warning(f"Redis not available for rate limiting: {e}")
    
    # Only add rate limit middleware if Redis is actually working
    if redis_available:
        app.add_middleware(SlowAPIMiddleware)
        logger.info("Rate limiting middleware enabled (Redis storage)")
    else:
        logger.info("Rate limiting middleware disabled (Redis not available)")

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
