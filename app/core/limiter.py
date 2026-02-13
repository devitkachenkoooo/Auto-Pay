"""
Rate limiter configuration for the Auto-Pay application.

This module provides a centralized Limiter instance used across the application.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Global rate limiter instance
limiter = Limiter(key_func=get_remote_address, default_limits=["100 per minute"])
