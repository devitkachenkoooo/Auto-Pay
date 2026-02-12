"""
Auto-Pay Application Entry Point.

Fixes applied:
    - Middleware actually registered with app.add_middleware()
    - /monitoring/errors secured with API key authentication
    - close_database() called on shutdown
    - Removed redundant limiter (using app.state.limiter only)
    - Health check no longer leaks error counts
    - Single get_error_summary() call instead of double
"""

from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from app.database import init_db, close_database
from app.routes.payments import router as payments_router
from app.core.handlers import setup_exception_handlers
from app.core.middleware import RequestLoggingMiddleware
from app.core.monitoring import setup_monitoring, error_monitor, monitor_errors
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os
import hmac
import logging

logger = logging.getLogger(__name__)


async def verify_monitoring_access(
    x_monitoring_key: str = Header(None),
):
    """
    Simple API key authentication for internal monitoring endpoints.
    Prevents public access to error details and stack traces.
    """
    expected_key = os.getenv("MONITORING_API_KEY")

    if not expected_key:
        # If no key is configured, deny all access (fail-closed)
        raise HTTPException(status_code=403, detail="Monitoring access not configured")

    if not x_monitoring_key or not hmac.compare_digest(x_monitoring_key, expected_key):
        raise HTTPException(status_code=403, detail="Invalid monitoring credentials")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle events"""
    # Startup
    try:
        # Setup monitoring first
        setup_monitoring()

        # Initialize database
        await init_db()
        logger.info("AutoPay AI started successfully")

        error_summary = error_monitor.get_error_summary()
        logger.info(f"Startup complete - Errors tracked: {error_summary['total_errors']}")

    except Exception as e:
        error_monitor.log_error(e, {"context": "application_startup"})
        logger.error(f"Failed to start AutoPay AI: {str(e)}")
        raise

    yield

    # Shutdown
    logger.info("AutoPay AI shutting down")
    await close_database()

    final_summary = error_monitor.get_error_summary()
    logger.info(f"Shutdown - Total errors handled: {final_summary['total_errors']}")


app = FastAPI(
    title="AutoPay AI",
    description="Secure webhook payment processing system",
    lifespan=lifespan,
)

# Initialize rate limiter (single instance, shared via app.state)
limiter = Limiter(key_func=get_remote_address, default_limits=["100 per minute"])
app.state.limiter = limiter

# Add global exception handler for rate limit exceeded
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Setup custom exception handlers (single generic handler for all BaseAppError subclasses)
setup_exception_handlers(app)

# Register request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Include payment routes
app.include_router(payments_router)


@app.get("/")
@limiter.limit("30/minute")
async def health_check(request: Request):
    return {
        "status": "active",
        "service": "AutoPay AI",
        "description": "Secure webhook payment processing system is running",
    }


@app.get("/monitoring/errors", dependencies=[Depends(verify_monitoring_access)])
@limiter.limit("10/minute")
@monitor_errors("monitoring_endpoint")
async def get_monitoring_info(request: Request):
    """Internal endpoint for monitoring error statistics (authenticated)."""
    return error_monitor.get_error_summary()
