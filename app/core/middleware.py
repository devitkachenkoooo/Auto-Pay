"""
Request/Response logging middleware for comprehensive API observability.

This middleware provides detailed logging of all HTTP requests and responses
including headers, timing, and status codes for debugging and monitoring.
"""

import time
import logging
import json
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse
from app.core.monitoring import error_monitor


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses"""
    
    def __init__(self, app, logger_name: str = "auto_pay.requests"):
        super().__init__(app)
        self.logger = logging.getLogger(logger_name)
        
        # Configure request logger
        handler = logging.FileHandler(f"{logger_name}.log", encoding='utf-8')
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Generate unique request ID for tracking
        request_id = f"req_{int(start_time * 1000)}"
        request.state.request_id = request_id
        
        # Log request details
        await self._log_request(request, request_id)
        
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log response details
            await self._log_response(request, response, request_id, process_time)
            
            # Add request ID to response headers for debugging
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # Log the error with request context
            process_time = time.time() - start_time
            error_monitor.log_error(e, {
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "process_time": process_time,
                "context": "middleware_error"
            })
            
            # Re-raise the exception
            raise
    
    async def _log_request(self, request: Request, request_id: str):
        """Log incoming request details"""
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Log request
        self.logger.info(
            f"[{request_id}] {request.method} {request.url.path} - Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_ip": client_ip,
                "user_agent": request.headers.get("user-agent", "unknown"),
                "content_type": request.headers.get("content-type", "unknown"),
                "content_length": request.headers.get("content-length", "0")
            }
        )
        
        # Log request body for POST/PUT requests (excluding sensitive data)
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body and self._should_log_body(request):
                    # Try to parse as JSON for structured logging
                    try:
                        body_json = json.loads(body.decode())
                        # Remove sensitive fields
                        if isinstance(body_json, dict):
                            body_json = self._sanitize_body(body_json)
                        
                        self.logger.debug(
                            f"[{request_id}] Request body: {json.dumps(body_json, indent=2)}"
                        )
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # Log as string if not JSON
                        body_str = body.decode('utf-8', errors='replace')
                        if len(body_str) < 1000:  # Only log small bodies
                            self.logger.debug(
                                f"[{request_id}] Request body: {body_str}"
                            )
            except Exception:
                pass  # Ignore body logging errors
    
    async def _log_response(self, request: Request, response: Response, request_id: str, process_time: float):
        """Log response details"""
        status_code = response.status_code
        
        # Determine log level based on status code
        if 200 <= status_code < 300:
            level = logging.INFO
            status_type = "SUCCESS"
        elif 300 <= status_code < 400:
            level = logging.WARNING
            status_type = "REDIRECT"
        elif 400 <= status_code < 500:
            level = logging.WARNING
            status_type = "CLIENT_ERROR"
        else:
            level = logging.ERROR
            status_type = "SERVER_ERROR"
        
        self.logger.log(
            level,
            f"[{request_id}] {request.method} {request.url.path} - {status_type} ({status_code}) - {process_time:.3f}s",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "status_code": status_code,
                "status_type": status_type,
                "process_time": process_time,
                "response_headers": dict(response.headers),
                "content_type": response.headers.get("content-type", "unknown"),
                "content_length": response.headers.get("content-length", "0")
            }
        )
    
    def _should_log_body(self, request: Request) -> bool:
        """Determine if request body should be logged"""
        # Don't log sensitive endpoints
        sensitive_paths = ["/webhook/payment", "/auth", "/login"]
        
        if any(request.url.path.startswith(path) for path in sensitive_paths):
            return False
        
        # Don't log large requests
        content_length = request.headers.get("content-length", "0")
        try:
            if int(content_length) > 10000:  # 10KB limit
                return False
        except (ValueError, TypeError):
            pass
        
        return True
    
    def _sanitize_body(self, body: dict) -> dict:
        """Remove sensitive data from request body"""
        sensitive_keys = ["password", "token", "secret", "key", "credit_card", "ssn"]
        
        sanitized = body.copy()
        for key in sensitive_keys:
            if key in sanitized:
                sanitized[key] = "[REDACTED]"
        
        return sanitized


class ResponseLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging response content for debugging"""
    
    def __init__(self, app, logger_name: str = "auto_pay.responses"):
        super().__init__(app)
        self.logger = logging.getLogger(logger_name)
        
        # Configure response logger
        handler = logging.FileHandler(f"{logger_name}.log", encoding='utf-8')
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Only log successful JSON responses for debugging
        if (200 <= response.status_code < 300 and 
            "application/json" in response.headers.get("content-type", "")):
            
            try:
                # Get request ID from state if available
                request_id = getattr(request.state, "request_id", "unknown")
                
                # For non-streaming responses, try to log the body
                if not isinstance(response, StreamingResponse):
                    body = b""
                    async for chunk in response.body_iterator:
                        body += chunk
                    
                    try:
                        body_json = json.loads(body.decode())
                        self.logger.debug(
                            f"[{request_id}] Response body: {json.dumps(body_json, indent=2)}"
                        )
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        body_str = body.decode('utf-8', errors='replace')
                        if len(body_str) < 1000:
                            self.logger.debug(
                                f"[{request_id}] Response body: {body_str}"
                            )
            except Exception:
                pass  # Ignore response body logging errors
        
        return response
