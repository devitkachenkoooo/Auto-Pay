"""
Centralized exception handlers for the FastAPI application.

Design:
    - A single generic handler catches all BaseAppError subclasses.
    - HTTP status codes come from the exception's `http_status_code` attribute.
    - Client responses use `to_safe_dict()` — internal details are logged, not sent.
    - No @monitor_errors decorator here to prevent double-counting (the middleware
      and service layer already log errors before they reach the handler).
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.core.exceptions import BaseAppError
import logging

logger = logging.getLogger(__name__)


async def app_exception_handler(request: Request, exc: BaseAppError) -> JSONResponse:
    """
    Generic handler for all BaseAppError subclasses.
    
    - Logs full internal details (to_dict) for debugging.
    - Returns sanitized response (to_safe_dict) to the client.
    """
    # Determine log level based on status code
    if exc.http_status_code >= 500:
        logger.error(
            f"[{exc.__class__.__name__}] {exc.message}",
            extra=exc.to_dict(),
        )
    elif exc.http_status_code >= 400:
        logger.warning(
            f"[{exc.__class__.__name__}] {exc.message}",
            extra=exc.to_dict(),
        )
    else:
        logger.info(
            f"[{exc.__class__.__name__}] {exc.message}",
            extra=exc.to_dict(),
        )

    return JSONResponse(
        status_code=exc.http_status_code,
        content=exc.to_safe_dict(),
    )


def setup_exception_handlers(app: FastAPI):
    """
    Register the single generic exception handler.
    
    Because BaseAppError is the base class, this catches all subclasses
    (PaymentValidationError, SecurityError, DatabaseError, etc.)
    automatically — no need to register each one individually.
    """
    app.add_exception_handler(BaseAppError, app_exception_handler)
