"""Configuration module for OpsSentinel."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Google Gemini Settings
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3.8-flash", alias="GEMINI_MODEL")
    gemini_embedding_model: str = Field(
        default="gemini-embedding-001", alias="GEMINI_EMBEDDING_MODEL"
    )

    # Database Settings
    postgres_user: str = Field(default="postgres", alias="POSTGRES_USER")
    postgres_password: str = Field(default="postgres", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="opssentinel", alias="POSTGRES_DB")
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/opssentinel",
        alias="DATABASE_URL",
    )

    # n8n Automation Engine Settings
    n8n_host: str = Field(default="localhost", alias="N8N_HOST")
    n8n_port: int = Field(default=5678, alias="N8N_PORT")
    n8n_protocol: str = Field(default="http", alias="N8N_PROTOCOL")
    n8n_webhook_url: str = Field(
        default="http://localhost:5678/webhook/incident-alert",
        alias="N8N_WEBHOOK_URL",
    )
    n8n_webhook_test_url: str = Field(
        default="http://localhost:5678/webhook-test/incident-alert",
        alias="N8N_WEBHOOK_TEST_URL",
    )

    # App Settings
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


settings = Settings()
