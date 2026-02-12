"""
Comprehensive error logging and monitoring utilities for the Auto-Pay application.

This module provides centralized logging, error tracking, and monitoring capabilities
to ensure production-ready observability and debugging capabilities.
"""

import logging
import time
import traceback
from typing import Dict, Any, Optional
from functools import wraps
from datetime import datetime, timezone
from app.core.exceptions import BaseAppError


class ErrorMonitor:
    """Centralized error monitoring and logging utility"""
    
    def __init__(self):
        self.logger = logging.getLogger("auto_pay.monitor")
        self.persistence_file = "error_metrics.json"
        self._load_metrics()
        
    def _load_metrics(self):
        """Simple persistence: Load metrics from file if exists"""
        import json
        import os
        if os.path.exists(self.persistence_file):
            try:
                with open(self.persistence_file, 'r') as f:
                    data = json.load(f)
                    self.error_counts = data.get("error_counts", {})
                    self.last_errors = data.get("last_errors", {})
            except Exception:
                self.error_counts = {}
                self.last_errors = {}
        else:
            self.error_counts = {}
            self.last_errors = {}

    def _save_metrics(self):
        """Simple persistence: Save metrics to file"""
        import json
        try:
            with open(self.persistence_file, 'w') as f:
                json.dump({
                    "error_counts": self.error_counts,
                    "last_errors": self.last_errors
                }, f)
        except Exception as e:
            self.logger.error(f"Failed to save metrics: {str(e)}")

    def log_error(self, error: Exception, context: Dict[str, Any] = None):
        """
        Log error with comprehensive context and tracking
        
        Args:
            error: The exception that occurred
            context: Additional context information
        """
        error_type = type(error).__name__
        error_id = f"{error_type}_{int(time.time())}"
        
        # Increment error count
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        # Store last error details
        self.last_errors[error_type] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_id": error_id,
            "message": str(error),
            "context": context or {},
            "traceback": traceback.format_exc()
        }
        
        # Persist to disk
        self._save_metrics()
        
        # Log with structured information
        log_data = {
            "error_id": error_id,
            "error_type": error_type,
            "error_message": str(error),
            "context": context or {},
            "count": self.error_counts[error_type]
        }
        
        if isinstance(error, BaseAppError):
            self.logger.error(
                f"Application Error [{error_id}]: {error.message}",
                extra=log_data,
                exc_info=True
            )
        else:
            self.logger.error(
                f"System Error [{error_id}]: {str(error)}",
                extra=log_data,
                exc_info=True
            )
    
    def log_performance(self, operation: str, duration: float, context: Dict[str, Any] = None):
        """
        Log performance metrics
        
        Args:
            operation: Name of the operation
            duration: Duration in seconds
            context: Additional context information
        """
        log_data = {
            "operation": operation,
            "duration": duration,
            "context": context or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if duration > 5.0:  # Log slow operations
            self.logger.warning(
                f"Slow operation detected: {operation} took {duration:.2f}s",
                extra=log_data
            )
        else:
            self.logger.info(
                f"Performance: {operation} completed in {duration:.2f}s",
                extra=log_data
            )
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of recent errors and statistics"""
        return {
            "error_counts": self.error_counts,
            "last_errors": self.last_errors,
            "total_errors": sum(self.error_counts.values()),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global error monitor instance
error_monitor = ErrorMonitor()


def monitor_errors(operation_name: str = None):
    """
    Decorator for monitoring function errors and performance
    
    Args:
        operation_name: Name of the operation for logging
    """
    def decorator(func):
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
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys())
                }
                error_monitor.log_error(e, context)
                raise
        
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
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys())
                }
                error_monitor.log_error(e, context)
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def setup_monitoring():
    """Setup comprehensive logging configuration for monitoring"""
    
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('auto_pay.log', encoding='utf-8')
        ]
    )
    
    # Configure specific loggers
    loggers = [
        'auto_pay.monitor',
        'app.services.payment_service',
        'app.services.ai_service',
        'app.security',
        'app.database',
        'app.routes'
    ]
    
    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        
        # Add file handler for each service
        file_handler = logging.FileHandler(f'{logger_name.replace(".", "_")}.log', encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    logging.info("✅ Monitoring and logging system initialized")
