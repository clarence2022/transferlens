"""
Worker Configuration
====================

Environment-based configuration for the worker service.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Worker settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Database
    database_url: str = "postgresql://transferlens:transferlens_dev@localhost:5432/transferlens"
    
    # Redis (optional, for job queue)
    redis_url: str = "redis://localhost:6379/0"
    
    # Model storage
    model_storage_path: Path = Path("/app/models")
    
    # Feature building
    default_horizon_days: int = 90
    candidate_clubs_per_player: int = 20
    
    # ML Training
    min_training_samples: int = 50
    test_size: float = 0.2
    random_state: int = 42
    
    # Signal derivation
    user_attention_window_hours: int = 24
    user_cooccurrence_window_hours: int = 168  # 7 days
    derived_signal_confidence: float = 0.6
    
    # Logging
    log_level: str = "INFO"
    
    @property
    def sync_database_url(self) -> str:
        """Ensure sync database URL for pandas/sklearn."""
        url = self.database_url
        if url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql+asyncpg://", "postgresql://")
        return url


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
