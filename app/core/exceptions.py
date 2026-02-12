"""
Production-grade exception hierarchy for the Auto-Pay application.

This module defines specific exception classes that map to appropriate HTTP status codes,
providing clear error semantics and better debugging capabilities.
"""

from typing import Optional, Dict, Any


class BaseAppError(Exception):
    """Base exception for all application-specific errors"""
    
    def __init__(self, message: str, details: str = None, context: Dict[str, Any] = None):
        self.message = message
        self.details = details
        self.context = context or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
            "context": self.context
        }


class PaymentValidationError(BaseAppError):
    """Raised when payment data fails validation (e.g., negative amounts, empty fields)"""
    
    def __init__(self, message: str, field: str = None, value: Any = None, **kwargs):
        self.field = field
        self.value = value
        context = kwargs.pop('context', {})
        
        if field:
            context.update({
                "field": field,
                "invalid_value": str(value) if value is not None else None
            })
        
        super().__init__(message, f"Validation failed for field: {field}" if field else None, context, **kwargs)


class IdempotencyError(BaseAppError):
    """Raised when attempting to process a duplicate transaction (same tx_id)"""
    
    def __init__(self, tx_id: str, **kwargs):
        self.tx_id = tx_id
        context = kwargs.pop('context', {})
        context.update({"tx_id": tx_id})
        
        super().__init__(f"Transaction {tx_id} already processed", f"Duplicate tx_id: {tx_id}", context, **kwargs)


class SecurityError(BaseAppError):
    """Raised for authentication/authorization failures (e.g., invalid HMAC signatures)"""
    
    def __init__(self, message: str, security_context: str = None, **kwargs):
        self.security_context = security_context
        context = kwargs.pop('context', {})
        
        if security_context:
            context.update({"security_context": security_context})
        
        super().__init__(message, f"Security failure in: {security_context}" if security_context else None, context, **kwargs)


class DatabaseError(BaseAppError):
    """Raised for database operation failures"""
    
    def __init__(self, message: str, operation: str = None, database_error: str = None, **kwargs):
        self.operation = operation
        self.database_error = database_error
        context = kwargs.pop('context', {})
        
        if operation:
            context.update({"operation": operation})
        if database_error:
            context.update({"database_error": database_error})
        
        super().__init__(message, f"Failed database operation: {operation}" if operation else None, context, **kwargs)


class ConfigurationError(BaseAppError):
    """Raised for configuration-related issues (missing env vars, invalid settings)"""
    
    def __init__(self, message: str, config_key: str = None, expected_value: str = None, **kwargs):
        self.config_key = config_key
        self.expected_value = expected_value
        context = kwargs.pop('context', {})
        
        if config_key:
            context.update({
                "config_key": config_key,
                "expected_value": expected_value
            })
        
        super().__init__(message, f"Configuration error for: {config_key}" if config_key else None, context, **kwargs)


class RateLimitError(BaseAppError):
    """Raised when rate limits are exceeded"""
    
    def __init__(self, message: str, limit: int = None, window: str = None, **kwargs):
        self.limit = limit
        self.window = window
        context = kwargs.pop('context', {})
        
        if limit:
            context.update({"limit": limit})
        if window:
            context.update({"window": window})
        
        super().__init__(message, f"Rate limit exceeded: {limit}/{window}" if limit and window else None, context, **kwargs)
