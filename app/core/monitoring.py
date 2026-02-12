"""
Comprehensive error logging and monitoring utilities for the Auto-Pay application.

This module provides centralized logging, error tracking, and monitoring capabilities
to ensure production-ready observability.

Fixes applied:
    - Cloud-Native: Removed file persistence and threading locks.
    - Structured Logging: Errors and performance metrics are logged as JSON to stdout.
    - Simplified setup: Removed FileHandlers, using only StreamHandler.
"""

import logging
import time
import json
import traceback
from typing import Dict, Any, Optional
from functools import wraps
from datetime import datetime, timezone
from app.core.exceptions import BaseAppError


class ErrorMonitor:
    """Centralized error monitoring and logging utility (Cloud-Native)"""

    def __init__(self):
        self.logger = logging.getLogger("auto_pay.monitor")
        self.error_counts_memory: Dict[str, int] = {}

    def log_error(self, error: Exception, context: Dict[str, Any] = None):
        """
        Log error with comprehensive context and tracking.
        Metrics are emitted as structured JSON logs.

        Args:
            error: The exception that occurred
            context: Additional context information
        """
        error_type = type(error).__name__
        error_id = f"{error_type}_{int(time.time())}"
        
        # Track in-memory for the current process lifetime (ephemeral)
        self.error_counts_memory[error_type] = self.error_counts_memory.get(error_type, 0) + 1
        count = self.error_counts_memory[error_type]

        log_data = {
            "event": "error",
            "error_id": error_id,
            "error_type": error_type,
            "error_message": str(error),
            "context": context or {},
            "count": count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Include stack trace for non-application errors or 500s
        if not isinstance(error, BaseAppError) or error.http_status_code >= 500:
            log_data["stack_trace"] = traceback.format_exc()

        # Emit as JSON string for cloud-native log collectors
        self.logger.error(json.dumps(log_data))

    def log_performance(self, operation: str, duration: float, context: Dict[str, Any] = None):
        """
        Log performance metrics as structured JSON.

        Args:
            operation: Name of the operation
            duration: Duration in seconds
            context: Additional context information
        """
        log_data = {
            "event": "performance",
            "operation": operation,
            "duration": duration,
            "context": context or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if duration > 5.0:
            self.logger.warning(json.dumps(log_data))
        else:
            self.logger.info(json.dumps(log_data))

    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of in-memory error statistics."""
        return {
            "error_counts": self.error_counts_memory,
            "total_errors": sum(self.error_counts_memory.values()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "ephemeral",
        }


# Global error monitor instance
error_monitor = ErrorMonitor()


def monitor_errors(operation_name: str = None):
    """
    Decorator for monitoring function errors and performance.
    """
    def decorator(func):
        import asyncio

        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                op_name = operation_name or f"{func.__module__}.{func.__name__}"
                start_time = time.time()

                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    error_monitor.log_performance(op_name, duration)
                    return result

                except Exception as e:
                    duration = time.time() - start_time
                    context = {
                        "operation": op_name,
                        "duration": duration,
                    }
                    error_monitor.log_error(e, context)
                    raise

            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                op_name = operation_name or f"{func.__module__}.{func.__name__}"
                start_time = time.time()

                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    error_monitor.log_performance(op_name, duration)
                    return result

                except Exception as e:
                    duration = time.time() - start_time
                    context = {
                        "operation": op_name,
                        "duration": duration,
                    }
                    error_monitor.log_error(e, context)
                    raise

            return sync_wrapper

    return decorator


def setup_monitoring():
    """
    Setup structured logging configuration for cloud-native environments.
    Only StreamHandler (stdout) is used.
    """
    # Configure root logger to output to stdout
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",  # JSON data already contains all context
        handlers=[
            logging.StreamHandler(),
        ],
    )

    # Ensure root logger doesn't double-log
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        if not isinstance(handler, logging.StreamHandler):
            root_logger.removeHandler(handler)

    logging.info(json.dumps({
        "event": "system_startup",
        "message": "Monitoring initialized in Cloud-Native mode (STDOUT only)",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }))

