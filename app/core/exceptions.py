"""
Production-grade exception hierarchy for the Auto-Pay application.

This module defines specific exception classes that map to appropriate HTTP status codes,
providing clear error semantics and better debugging capabilities.

Design:
    - Each exception carries an `http_status_code` for automatic handler mapping.
    - `to_dict()` returns full internal details (for logging).
    - `to_safe_dict()` returns a sanitized response (for client-facing APIs).
"""

from typing import Optional, Dict, Any


class BaseAppError(Exception):
    """Base exception for all application-specific errors"""

    http_status_code: int = 500

    def __init__(self, message: str, details: str = None, context: Dict[str, Any] = None):
        self.message = message
        self.details = details
        self.context = context or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Full details for internal logging — never send to client."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
            "context": self.context,
        }

    def to_safe_dict(self) -> Dict[str, Any]:
        """Sanitized response safe for end-users — no internal details."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
        }


class PaymentValidationError(BaseAppError):
    """Raised when payment data fails validation (e.g., negative amounts, empty fields)"""

    http_status_code: int = 400

    def __init__(self, message: str, field: str = None, value: Any = None):
        self.field = field
        self.value = value
        context = {}

        if field:
            context["field"] = field
            if value is not None:
                context["invalid_value"] = str(value)

        details = f"Validation failed for field: {field}" if field else None
        super().__init__(message, details, context)

    def to_safe_dict(self) -> Dict[str, Any]:
        result = super().to_safe_dict()
        if self.field:
            result["field"] = self.field
        return result


class IdempotencyError(BaseAppError):
    """Raised when attempting to process a duplicate transaction (same tx_id)"""

    http_status_code: int = 409

    def __init__(self, tx_id: str):
        self.tx_id = tx_id
        super().__init__(
            f"Transaction {tx_id} already processed",
            f"Duplicate tx_id: {tx_id}",
            {"tx_id": tx_id},
        )

    def to_safe_dict(self) -> Dict[str, Any]:
        result = super().to_safe_dict()
        result["tx_id"] = self.tx_id
        return result


class NotFoundError(BaseAppError):
    """Raised when a requested resource is not found"""

    http_status_code: int = 404

    def __init__(self, resource: str, identifier: str):
        self.resource = resource
        self.identifier = identifier
        super().__init__(
            f"{resource} not found",
            f"{resource} with id '{identifier}' does not exist",
            {"resource": resource, "identifier": identifier},
        )


class SecurityError(BaseAppError):
    """Raised for authentication/authorization failures (e.g., invalid HMAC signatures)"""

    http_status_code: int = 401

    def __init__(self, message: str, security_context: str = None):
        self.security_context = security_context
        context = {}
        if security_context:
            context["security_context"] = security_context

        details = f"Security failure in: {security_context}" if security_context else None
        super().__init__(message, details, context)

    def to_safe_dict(self) -> Dict[str, Any]:
        """Never expose security_context to clients."""
        return {
            "error": "SecurityError",
            "message": self.message,
        }


class DatabaseError(BaseAppError):
    """Raised for database operation failures"""

    http_status_code: int = 500

    def __init__(self, message: str, operation: str = None, database_error: str = None):
        self.operation = operation
        self.database_error = database_error
        context = {}
        if operation:
            context["operation"] = operation
        if database_error:
            context["database_error"] = database_error

        details = f"Failed database operation: {operation}" if operation else None
        super().__init__(message, details, context)

    def to_safe_dict(self) -> Dict[str, Any]:
        """Never expose operation names or DB errors to clients."""
        return {
            "error": "DatabaseError",
            "message": "An internal error occurred. Please try again later.",
        }


class ConfigurationError(BaseAppError):
    """Raised for configuration-related issues (missing env vars, invalid settings)"""

    http_status_code: int = 500

    def __init__(self, message: str, config_key: str = None, expected_value: str = None):
        self.config_key = config_key
        self.expected_value = expected_value
        context = {}
        if config_key:
            context["config_key"] = config_key
        if expected_value:
            context["expected_value"] = expected_value

        details = f"Configuration error for: {config_key}" if config_key else None
        super().__init__(message, details, context)

    def to_safe_dict(self) -> Dict[str, Any]:
        """Never expose config internals to clients."""
        return {
            "error": "ConfigurationError",
            "message": "A server configuration error occurred.",
        }


class RateLimitError(BaseAppError):
    """Raised when rate limits are exceeded"""

    http_status_code: int = 429

    def __init__(self, message: str, limit: int = None, window: str = None):
        self.limit = limit
        self.window = window
        context = {}
        if limit:
            context["limit"] = limit
        if window:
            context["window"] = window

        details = f"Rate limit exceeded: {limit}/{window}" if limit and window else None
        super().__init__(message, details, context)
