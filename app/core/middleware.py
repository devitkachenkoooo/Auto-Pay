"""
Request/Response logging middleware for comprehensive API observability.

Fixes applied:
    - Fixed Body Consumption: Read once in dispatch, override receive channel for downstream.
    - Cloud-Native: Removed local FileHandlers (logs now go to stdout via global config).
    - Performance: Cached body in request.state.body for HMAC/Route handlers.
    - Sanitization: Recursive, case-insensitive logic remains robust.
"""

import time
import logging
import json
from typing import Any, Callable, Set
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.monitoring import error_monitor


# Comprehensive set of sensitive field names
SENSITIVE_KEYS: Set[str] = {
    "password", "passwd", "pass",
    "token", "access_token", "refresh_token", "auth_token", "bearer",
    "secret", "secret_key", "client_secret",
    "key", "api_key", "apikey", "private_key",
    "authorization", "auth",
    "credit_card", "card_number", "cvv", "cvc", "expiry",
    "ssn", "social_security",
    "pin", "otp",
    "session_id", "session", "cookie",
    "hmac", "signature", "x_signature",
}

# Headers that should never be logged
SENSITIVE_HEADERS: Set[str] = {
    "authorization", "cookie", "set-cookie",
    "x-signature", "x-api-key", "x-auth-token",
}


def _sanitize_value(data: Any, depth: int = 0) -> Any:
    """Recursively sanitize sensitive data from dicts, lists, and nested structures."""
    if depth > 10:
        return "[DEPTH_LIMIT]"

    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            if key.lower() in SENSITIVE_KEYS:
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = _sanitize_value(value, depth + 1)
        return sanitized

    elif isinstance(data, list):
        return [_sanitize_value(item, depth + 1) for item in data]

    return data


def _sanitize_headers(headers: dict) -> dict:
    """Remove sensitive headers before logging."""
    return {
        k: ("[REDACTED]" if k.lower() in SENSITIVE_HEADERS else v)
        for k, v in headers.items()
    }


def _sanitize_query_params(params: dict) -> dict:
    """Remove sensitive values from query parameters."""
    return {
        k: ("[REDACTED]" if k.lower() in SENSITIVE_KEYS else v)
        for k, v in params.items()
    }


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses with safe sanitization."""

    def __init__(self, app, logger_name: str = "auto_pay.requests"):
        super().__init__(app)
        self.logger = logging.getLogger(logger_name)
        # Using root-configured StreamHandler only

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        # Generate unique request ID for tracking
        request_id = f"req_{int(start_time * 1000)}"
        request.state.request_id = request_id

        # CRITICAL FIX: Read body once and re-construct the receive channel
        # This prevents "Body Already Consumed" errors in downstream HMAC verify/handlers
        body = await request.body()
        request.state.body = body

        async def receive():
            return {"type": "http.request", "body": body}
        
        request._receive = receive

        # Log request details (uses cached body)
        self._log_request(request, request_id)

        try:
            response = await call_next(request)

            # Calculate processing time
            process_time = time.time() - start_time

            # Log response details
            self._log_response(request, response, request_id, process_time)

            # Add request ID to response headers for debugging
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Log the error with request context
            process_time = time.time() - start_time
            error_monitor.log_error(e, {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "process_time": process_time,
                "context": "middleware_error",
            })
            raise

    def _log_request(self, request: Request, request_id: str):
        """Log incoming request details with sanitized data."""
        client_ip = request.client.host if request.client else "unknown"

        self.logger.info(
            f"[{request_id}] {request.method} {request.url.path} - Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": _sanitize_query_params(dict(request.query_params)),
                "client_ip": client_ip,
            },
        )

        # Log request body for mutation requests (excluding sensitive endpoints)
        if request.method in ("POST", "PUT", "PATCH"):
            body = request.state.body
            if body and self._should_log_body(request):
                try:
                    body_json = json.loads(body.decode())
                    sanitized = _sanitize_value(body_json)
                    self.logger.debug(
                        f"[{request_id}] Request body: {json.dumps(sanitized, indent=2)}"
                    )
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass

    def _log_response(self, request: Request, response: Response, request_id: str, process_time: float):
        """Log response details with sanitized headers."""
        status_code = response.status_code
        level = logging.INFO if status_code < 400 else logging.WARNING if status_code < 500 else logging.ERROR

        self.logger.log(
            level,
            f"[{request_id}] {request.method} {request.url.path} - {status_code} - {process_time:.3f}s",
            extra={
                "request_id": request_id,
                "status_code": status_code,
                "process_time": process_time,
                "response_headers": _sanitize_headers(dict(response.headers)),
            },
        )

    def _should_log_body(self, request: Request) -> bool:
        """Determine if request body should be logged."""
        # Never log bodies for sensitive endpoints (webhooks contain secrets)
        sensitive_paths = ["/webhook", "/auth", "/login"]

        if any(request.url.path.startswith(path) for path in sensitive_paths):
            return False

        content_length = request.headers.get("content-length", "0")
        try:
            if int(content_length) > 10000:  # 10KB limit
                return False
        except (ValueError, TypeError):
            pass

        return True

