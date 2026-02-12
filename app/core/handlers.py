from fastapi import FastAPI, Request, HTTPException
from app.core.exceptions import BaseAppError, PaymentValidationError, IdempotencyError, SecurityError, DatabaseError
from app.core.monitoring import monitor_errors
import logging

logger = logging.getLogger(__name__)


@monitor_errors("payment_validation_error_handler")
async def payment_validation_exception_handler(request: Request, exc: PaymentValidationError):
    logger.warning(f"Payment validation error: {exc.message} (field: {exc.field})")
    raise HTTPException(
        status_code=400,
        detail={
            "error": "PaymentValidationError",
            "message": exc.message,
            "field": exc.field,
            "details": exc.details
        }
    )


@monitor_errors("idempotency_error_handler")
async def idempotency_exception_handler(request: Request, exc: IdempotencyError):
    logger.info(f"Idempotency protection triggered: {exc.message}")
    raise HTTPException(
        status_code=409,
        detail={
            "error": "IdempotencyError", 
            "message": exc.message,
            "tx_id": exc.tx_id,
            "details": exc.details
        }
    )


@monitor_errors("security_error_handler")
async def security_exception_handler(request: Request, exc: SecurityError):
    logger.warning(f"Security error: {exc.message} (context: {exc.security_context})")
    raise HTTPException(
        status_code=401,
        detail={
            "error": "SecurityError",
            "message": exc.message,
            "context": exc.security_context,
            "details": exc.details
        }
    )


@monitor_errors("database_error_handler")
async def database_exception_handler(request: Request, exc: DatabaseError):
    logger.error(f"Database error: {exc.message} (operation: {exc.operation})")
    raise HTTPException(
        status_code=500,
        detail={
            "error": "DatabaseError",
            "message": "Internal database error",
            "operation": exc.operation,
            "details": exc.details
        }
    )


@monitor_errors("base_app_error_handler")
async def base_app_exception_handler(request: Request, exc: BaseAppError):
    logger.error(f"Unexpected application error: {exc.message}")
    raise HTTPException(
        status_code=500,
        detail={
            "error": "BaseAppError",
            "message": "Internal application error",
            "details": exc.details
        }
    )


def setup_exception_handlers(app: FastAPI):
    """Register all exception handlers with the FastAPI application."""
    app.add_exception_handler(PaymentValidationError, payment_validation_exception_handler)
    app.add_exception_handler(IdempotencyError, idempotency_exception_handler)
    app.add_exception_handler(SecurityError, security_exception_handler)
    app.add_exception_handler(DatabaseError, database_exception_handler)
    app.add_exception_handler(BaseAppError, base_app_exception_handler)
