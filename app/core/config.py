"""
Configuration validation and management for the Auto-Pay application.

This module provides comprehensive configuration validation, environment variable management,
and configuration loading with proper error handling and defaults.
"""

import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from app.core.exceptions import ConfigurationError
import logging

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    url: str
    max_pool_size: int = 10
    min_pool_size: int = 2
    max_idle_time_ms: int = 30000
    server_selection_timeout_ms: int = 5000
    connect_timeout_ms: int = 10000
    socket_timeout_ms: int = 45000
    retry_writes: bool = True
    write_concern: int = 1


@dataclass
class SecurityConfig:
    """Security configuration settings"""
    hmac_secret_key: str
    gemini_api_key: Optional[str] = None


@dataclass
class RateLimitConfig:
    """Rate limiting configuration settings"""
    webhook_rate_limit: str = "10/minute"
    api_rate_limit: str = "30/minute"
    monitoring_rate_limit: str = "10/minute"


@dataclass
class LoggingConfig:
    """Logging configuration settings"""
    level: str = "INFO"
    log_requests: bool = True
    log_responses: bool = False
    max_log_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


@dataclass
class AppConfig:
    """Main application configuration"""
    database: DatabaseConfig
    security: SecurityConfig
    rate_limit: RateLimitConfig
    logging: LoggingConfig
    environment: str = "development"
    debug: bool = False


class ConfigValidator:
    """Validates and loads application configuration"""
    
    REQUIRED_ENV_VARS = {
        "MONGO_URL": "mongodb://localhost:27017/autopay",
        "HMAC_SECRET_KEY": "your-secret-key-here",
    }
    
    OPTIONAL_ENV_VARS = {
        "GEMINI_API_KEY": None,
        "ENVIRONMENT": "development",
        "DEBUG": "false",
        "LOG_LEVEL": "INFO",
        "MONGO_MAX_POOL_SIZE": "10",
        "MONGO_MIN_POOL_SIZE": "2",
        "MONGO_MAX_IDLE_TIME_MS": "30000",
        "MONGO_SERVER_SELECTION_TIMEOUT_MS": "5000",
        "MONGO_CONNECT_TIMEOUT_MS": "10000",
        "MONGO_SOCKET_TIMEOUT_MS": "45000",
        "MONGO_RETRY_WRITES": "true",
        "MONGO_WRITE_CONCERN": "1",
        "WEBHOOK_RATE_LIMIT": "10/minute",
        "API_RATE_LIMIT": "30/minute",
        "MONITORING_RATE_LIMIT": "10/minute",
        "LOG_REQUESTS": "true",
        "LOG_RESPONSES": "false",
        "MAX_LOG_FILE_SIZE": "10485760",  # 10MB
        "LOG_BACKUP_COUNT": "5",
    }
    
    @classmethod
    def validate_environment(cls) -> Dict[str, str]:
        """
        Validate all required and optional environment variables
        
        Returns:
            Dict containing all validated environment variables
            
        Raises:
            ConfigurationError: If validation fails
        """
        errors = []
        config = {}
        
        # Check required environment variables
        for var_name, default_value in cls.REQUIRED_ENV_VARS.items():
            value = os.getenv(var_name)
            if not value:
                errors.append(f"Required environment variable {var_name} is not set")
                config[var_name] = default_value
            else:
                config[var_name] = value
        
        # Load optional environment variables with defaults
        for var_name, default_value in cls.OPTIONAL_ENV_VARS.items():
            config[var_name] = os.getenv(var_name, default_value)
        
        if errors:
            raise ConfigurationError(
                "Configuration validation failed: " + "; ".join(errors),
                config_key="environment_validation",
            )
        
        return config
    
    @classmethod
    def validate_mongo_url(cls, url: str) -> str:
        """Validate MongoDB URL format"""
        if not url.startswith(("mongodb://", "mongodb+srv://")):
            raise ConfigurationError(
                "Invalid MongoDB URL format",
                config_key="MONGO_URL",
                expected_value="mongodb://localhost:27017/autopay"
            )
        return url
    
    @classmethod
    def validate_rate_limit(cls, rate_limit: str) -> str:
        """Validate rate limit format (e.g., '10/minute')"""
        try:
            parts = rate_limit.split("/")
            if len(parts) != 2:
                raise ValueError()
            int(parts[0])  # Validate number
            if parts[1] not in ["second", "minute", "hour", "day"]:
                raise ValueError()
        except ValueError:
            raise ConfigurationError(
                "Invalid rate limit format",
                config_key="rate_limit",
                expected_value="10/minute"
            )
        return rate_limit
    
    @classmethod
    def validate_boolean(cls, value: str, default: bool = False) -> bool:
        """Validate boolean string values"""
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "on")
    
    @classmethod
    def validate_integer(cls, value: str, default: int, min_val: int = None, max_val: int = None) -> int:
        """Validate integer values with optional bounds"""
        try:
            int_val = int(value)
            if min_val is not None and int_val < min_val:
                raise ValueError(f"Value must be >= {min_val}")
            if max_val is not None and int_val > max_val:
                raise ValueError(f"Value must be <= {max_val}")
            return int_val
        except (ValueError, TypeError):
            return default
    
    @classmethod
    def load_config(cls) -> AppConfig:
        """
        Load and validate complete application configuration
        
        Returns:
            AppConfig: Validated application configuration
            
        Raises:
            ConfigurationError: If configuration validation fails
        """
        logger.info("Loading application configuration...")
        
        # Validate environment variables
        env_vars = cls.validate_environment()
        
        # Create database configuration
        database_config = DatabaseConfig(
            url=cls.validate_mongo_url(env_vars["MONGO_URL"]),
            max_pool_size=cls.validate_integer(env_vars["MONGO_MAX_POOL_SIZE"], 10, 1, 100),
            min_pool_size=cls.validate_integer(env_vars["MONGO_MIN_POOL_SIZE"], 2, 1, 50),
            max_idle_time_ms=cls.validate_integer(env_vars["MONGO_MAX_IDLE_TIME_MS"], 30000, 1000, 300000),
            server_selection_timeout_ms=cls.validate_integer(env_vars["MONGO_SERVER_SELECTION_TIMEOUT_MS"], 5000, 1000, 30000),
            connect_timeout_ms=cls.validate_integer(env_vars["MONGO_CONNECT_TIMEOUT_MS"], 10000, 1000, 60000),
            socket_timeout_ms=cls.validate_integer(env_vars["MONGO_SOCKET_TIMEOUT_MS"], 45000, 1000, 120000),
            retry_writes=cls.validate_boolean(env_vars["MONGO_RETRY_WRITES"], True),
            write_concern=cls.validate_integer(env_vars["MONGO_WRITE_CONCERN"], 1, 1, 5),
        )
        
        # Create security configuration
        security_config = SecurityConfig(
            hmac_secret_key=env_vars["HMAC_SECRET_KEY"],
            gemini_api_key=env_vars.get("GEMINI_API_KEY"),
        )
        
        # Create rate limit configuration
        rate_limit_config = RateLimitConfig(
            webhook_rate_limit=cls.validate_rate_limit(env_vars["WEBHOOK_RATE_LIMIT"]),
            api_rate_limit=cls.validate_rate_limit(env_vars["API_RATE_LIMIT"]),
            monitoring_rate_limit=cls.validate_rate_limit(env_vars["MONITORING_RATE_LIMIT"]),
        )
        
        # Create logging configuration
        logging_config = LoggingConfig(
            level=env_vars["LOG_LEVEL"],
            log_requests=cls.validate_boolean(env_vars["LOG_REQUESTS"], True),
            log_responses=cls.validate_boolean(env_vars["LOG_RESPONSES"], False),
            max_log_file_size=cls.validate_integer(env_vars["MAX_LOG_FILE_SIZE"], 10485760, 1024, 104857600),
            backup_count=cls.validate_integer(env_vars["LOG_BACKUP_COUNT"], 5, 1, 50),
        )
        
        # Create main application configuration
        app_config = AppConfig(
            database=database_config,
            security=security_config,
            rate_limit=rate_limit_config,
            logging=logging_config,
            environment=env_vars["ENVIRONMENT"],
            debug=cls.validate_boolean(env_vars["DEBUG"], False),
        )
        
        logger.info("Configuration loaded successfully")
        logger.info(f"Environment: {app_config.environment}")
        logger.info(f"Debug mode: {app_config.debug}")
        logger.info(f"Rate limits: webhook={app_config.rate_limit.webhook_rate_limit}, api={app_config.rate_limit.api_rate_limit}")
        
        return app_config


# Global configuration instance
_app_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """
    Get the application configuration
    
    Returns:
        AppConfig: Application configuration
        
    Raises:
        ConfigurationError: If configuration is not loaded
    """
    global _app_config
    
    if _app_config is None:
        raise ConfigurationError(
            "Configuration not loaded. Call load_config() first.",
            config_key="config_not_loaded"
        )
    
    return _app_config


def load_config() -> AppConfig:
    """
    Load and validate application configuration
    
    Returns:
        AppConfig: Loaded and validated configuration
    """
    global _app_config
    
    _app_config = ConfigValidator.load_config()
    return _app_config


def validate_required_config() -> bool:
    """
    Validate that required configuration is available
    
    Returns:
        bool: True if configuration is valid
        
    Raises:
        ConfigurationError: If configuration is invalid
    """
    try:
        config = get_config()
        
        # Validate critical configuration
        if not config.security.hmac_secret_key:
            raise ConfigurationError("HMAC_SECRET_KEY is required", config_key="HMAC_SECRET_KEY")
        
        if not config.database.url:
            raise ConfigurationError("MONGO_URL is required", config_key="MONGO_URL")
        
        return True
        
    except ConfigurationError:
        raise
    except Exception as e:
        raise ConfigurationError(f"Configuration validation failed: {str(e)}", config_key="validation_error") from e
