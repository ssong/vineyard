"""Configuration settings for the factory."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Slack (Socket Mode)
    slack_bot_token: str
    slack_app_token: str

    # Anthropic
    anthropic_api_key: str

    # Linear
    linear_api_key: str = ""

    # Miro (optional)
    miro_access_token: str = ""

    # GitHub (optional)
    github_token: str = ""

    # Logging
    log_level: str = "INFO"


settings = Settings()
