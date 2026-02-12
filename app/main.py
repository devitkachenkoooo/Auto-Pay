from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager
from app.database import init_db
from app.routes.payments import router as payments_router
from app.core.handlers import setup_exception_handlers
from app.core.monitoring import setup_monitoring, error_monitor, monitor_errors
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging

logger = logging.getLogger(__name__)


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
        
        # Log startup summary
        error_summary = error_monitor.get_error_summary()
        logger.info(f"Startup complete - Errors tracked: {error_summary['total_errors']}")
        
    except Exception as e:
        error_monitor.log_error(e, {"context": "application_startup"})
        logger.error(f"Failed to start AutoPay AI: {str(e)}")
        raise

    yield

    # Shutdown (if needed)
    logger.info("AutoPay AI shutting down")
    
    # Log final error summary
    final_summary = error_monitor.get_error_summary()
    logger.info(f"Shutdown - Total errors handled: {final_summary['total_errors']}")


app = FastAPI(
    title="AutoPay AI",
    description="Secure webhook payment processing system",
    lifespan=lifespan,
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["100 per minute"])
app.state.limiter = limiter

# Add global exception handler for rate limit exceeded
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Setup custom exception handlers
setup_exception_handlers(app)

# Include payment routes
app.include_router(payments_router)


@app.get("/")
@limiter.limit("30/minute")
@monitor_errors("health_check")
async def health_check(request: Request):
    return {
        "status": "active",
        "service": "AutoPay AI",
        "description": "Secure webhook payment processing system is running",
        "monitoring": {
            "errors_tracked": error_monitor.get_error_summary()["total_errors"],
            "timestamp": error_monitor.get_error_summary()["timestamp"]
        }
    }


@app.get("/monitoring/errors")
@limiter.limit("10/minute")
@monitor_errors("monitoring_endpoint")
async def get_monitoring_info(request: Request):
    """Internal endpoint for monitoring error statistics"""
    return error_monitor.get_error_summary()
