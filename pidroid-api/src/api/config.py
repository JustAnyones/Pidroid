"""Application configuration."""

import os

from pydantic_settings import BaseSettings
from typing import Literal

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    APP_NAME: str = "Pidroid API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Server Configuration
    HOST: str = os.getenv("API_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("API_PORT", 8000))
    
    # RabbitMQ Configuration
    RABBITMQ_URL: str = os.getenv(
        "RABBITMQ_URL",
        "amqp://guest:guest@127.0.0.1:5672/"
    )
    
    # Environment
    ENVIRONMENT: Literal["development", "production", "testing"] = os.getenv(
        "ENVIRONMENT",
        "development"
    ) # pyright: ignore[reportAssignmentType]


settings = Settings()
