"""
Database initialization and connection management.

Fixes applied:
    - Replaced deprecated asyncio.get_event_loop() with datetime for timestamps
    - Removed logging of connection kwargs (could contain sensitive info)
    - health_check uses wall-clock time instead of loop time
    - Clearer error handling without exposing raw exception messages
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.models import Transaction
from app.core.exceptions import DatabaseError, ConfigurationError
from app.core.monitoring import monitor_errors
from dotenv import load_dotenv
import logging
import asyncio
from datetime import datetime, timezone
from tenacity import retry, stop_after_attempt, wait_exponential
from typing import Dict, Any

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Global database client instance
_db_client = None


@monitor_errors("database_init")
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def init_db():
    """
    Initialize MongoDB connection and Beanie ODM with optimized connection handling.

    Raises:
        DatabaseError: If database connection fails
        ConfigurationError: If configuration is invalid
    """
    global _db_client

    try:
        # Validate configuration
        mongo_url = os.getenv("MONGO_URL")
        if not mongo_url:
            raise ConfigurationError(
                "MONGO_URL environment variable is not set",
                config_key="MONGO_URL",
                expected_value="mongodb://localhost:27017/autopay",
            )

        # Validate MongoDB URL format
        if not mongo_url.startswith(("mongodb://", "mongodb+srv://")):
            raise ConfigurationError(
                "Invalid MONGO_URL format",
                config_key="MONGO_URL",
                expected_value="mongodb://localhost:27017/autopay",
            )

        # Connection options for production
        connection_kwargs = {
            "maxPoolSize": int(os.getenv("MONGO_MAX_POOL_SIZE", "10")),
            "minPoolSize": int(os.getenv("MONGO_MIN_POOL_SIZE", "2")),
            "maxIdleTimeMS": int(os.getenv("MONGO_MAX_IDLE_TIME_MS", "30000")),
            "serverSelectionTimeoutMS": int(os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000")),
            "connectTimeoutMS": int(os.getenv("MONGO_CONNECT_TIMEOUT_MS", "10000")),
            "socketTimeoutMS": int(os.getenv("MONGO_SOCKET_TIMEOUT_MS", "45000")),
            "retryWrites": os.getenv("MONGO_RETRY_WRITES", "true").lower() == "true",
            "w": int(os.getenv("MONGO_WRITE_CONCERN", "1")),
        }

        # Log pool settings only (no connection string or credentials)
        logger.info(
            f"Connecting to MongoDB (pool: min={connection_kwargs['minPoolSize']}, "
            f"max={connection_kwargs['maxPoolSize']})"
        )

        # Create MongoDB client with optimized settings
        client = AsyncIOMotorClient(mongo_url, **connection_kwargs)

        # Test the connection with timeout
        try:
            await asyncio.wait_for(
                client.admin.command("ping"),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            raise DatabaseError("Database connection timeout", operation="ping_test")

        # Initialize Beanie with the database and document models
        await init_beanie(
            database=client.get_default_database(),
            document_models=[Transaction],
        )

        # Store client for reuse
        _db_client = client

        logger.info("MongoDB connected and Beanie initialized successfully")

        return client

    except ConfigurationError:
        raise
    except DatabaseError:
        raise
    except Exception as e:
        logger.error("Failed to initialize database", exc_info=True)
        raise DatabaseError(
            "Database initialization failed",
            operation="init_db",
        ) from e


async def get_database_client() -> AsyncIOMotorClient:
    """
    Get the database client instance.

    Returns:
        AsyncIOMotorClient: The database client

    Raises:
        DatabaseError: If database is not initialized
    """
    global _db_client

    if _db_client is None:
        raise DatabaseError(
            "Database not initialized. Call init_db() first.",
            operation="get_client",
        )

    return _db_client


async def close_database():
    """Close the database connection gracefully."""
    global _db_client

    if _db_client:
        _db_client.close()
        _db_client = None
        logger.info("Database connection closed")


async def health_check() -> Dict[str, Any]:
    """
    Perform database health check.

    Returns:
        Dict with health status information
    """
    try:
        client = await get_database_client()

        # Test database connectivity
        await client.admin.command("ping")

        # Test Beanie models
        await Transaction.find_one({})

        return {
            "status": "healthy",
            "database": "connected",
            "beanie": "initialized",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "beanie": "not_initialized",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
