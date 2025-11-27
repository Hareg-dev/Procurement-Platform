from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database settings
    database_url: str = Field(
        default="sqlite+aiosqlite:///./procurement.db",
        description="Database URL - SQLite for development",
    )

    # JWT settings
    secret_key: str = Field(
        default="your-secret-key-change-this-in-production",
        description="Secret key for JWT token generation",
    )
    algorithm: str = Field(
        default="HS256",
        description="Algorithm used for JWT token encoding",
    )
    access_token_expire_minutes: int = Field(
        default=30,
        description="Access token expiration time in minutes",
    )

    # API settings
    api_v1_str: str = Field(
        default="/api/v1",
        description="API version 1 prefix",
    )
    project_name: str = Field(
        default="Procurement Platform",
        description="Project name for API documentation",
    )
    project_version: str = Field(
        default="0.1.0",
        description="Project version",
    )

    # CORS settings
    backend_cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="List of allowed CORS origins",
    )

    # Environment
    environment: str = Field(
        default="development",
        description="Environment (development, staging, production)",
    )

    # Pagination
    default_page_size: int = Field(
        default=20,
        description="Default page size for paginated responses",
    )
    max_page_size: int = Field(
        default=100,
        description="Maximum page size for paginated responses",
    )

    # Ollama settings
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL for Ollama API",
    )
    ollama_model: str = Field(
        default="tinyllama",
        description="Ollama model to use",
    )
    ollama_temperature: float = Field(
        default=0.7,
        description="Temperature for Ollama responses (0.0 to 1.0)",
    )

    # Redis settings for Celery and chat history
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for Celery broker and chat history storage",
    )

    # Celery settings
    celery_broker_url: str = Field(
        default="redis://localhost:6379/0",
        description="Celery broker URL",
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/0",
        description="Celery result backend URL",
    )

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    This function uses lru_cache to ensure that settings are loaded only once
    and reused throughout the application lifecycle.
    """
    return Settings()


# Global settings instance
settings = get_settings()
