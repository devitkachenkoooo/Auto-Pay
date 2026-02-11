from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from app.database import init_db
from app.routes.payments import router as payments_router
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
        await init_db()
        logger.info("AutoPay AI started successfully")
    except Exception as e:
        logger.error(f"Failed to start AutoPay AI: {str(e)}")
        raise

    yield

    # Shutdown (if needed)
    logger.info("AutoPay AI shutting down")


app = FastAPI(
    title="AutoPay AI",
    description="Secure webhook payment processing system",
    lifespan=lifespan,
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Add global exception handler for rate limit exceeded
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
