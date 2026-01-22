"""
Application configuration using pydantic-settings.

Environment Variables:
    DATABASE_URL: PostgreSQL connection string
    ADMIN_API_KEY: Admin endpoint authentication key
    CORS_ORIGINS: Comma-separated allowed origins
    REDIS_URL: Redis connection string (optional)
    LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR)
    RATE_LIMIT_REQUESTS: Rate limit requests per window
    RATE_LIMIT_WINDOW: Rate limit window in seconds
"""

import os
from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # ==========================================================================
    # Application
    # ==========================================================================
    environment: str = "development"
    debug: bool = False
    secret_key: str = "change-me-in-production"
    admin_api_key: str = "tl-admin-dev-key-change-in-production"
    api_version: str = "1.0.0"
    log_level: str = "INFO"
    
    # ==========================================================================
    # Database
    # ==========================================================================
    database_url: str = "postgresql://transferlens:transferlens_dev@localhost:5432/transferlens"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    
    # ==========================================================================
    # Redis (Optional)
    # ==========================================================================
    redis_url: Optional[str] = "redis://localhost:6379/0"
    
    # ==========================================================================
    # CORS
    # ==========================================================================
    # Can be set as comma-separated string: "https://example.com,https://www.example.com"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000"
    
    # ==========================================================================
    # Rate Limiting
    # ==========================================================================
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100  # Requests per window
    rate_limit_window: int = 60     # Window in seconds
    rate_limit_burst: int = 150     # Burst limit
    
    # ==========================================================================
    # Pagination
    # ==========================================================================
    default_page_size: int = 20
    max_page_size: int = 100
    
    # ==========================================================================
    # Computed Properties
    # ==========================================================================
    
    @property
    def async_database_url(self) -> str:
        """Convert sync database URL to async."""
        return self.database_url.replace("postgresql://", "postgresql+asyncpg://")
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if isinstance(self.cors_origins, list):
            return self.cors_origins
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
    
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment.lower() in ("production", "prod")
    
    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment.lower() in ("development", "dev", "local")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()


# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

import logging
import sys

def configure_logging():
    """Configure application logging."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    # Create formatter
    if settings.is_production:
        # JSON-like format for production (easier to parse)
        formatter = logging.Formatter(
            '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
        )
    else:
        # Human-readable format for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add stdout handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Reduce noise from libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    return root_logger

