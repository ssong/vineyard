"""Configuration settings for the research agent."""

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

    # Web Search
    tavily_api_key: str = ""

    # Linear
    linear_api_key: str = ""

    # Research settings
    research_timeout_seconds: int = 180
    max_opportunities: int = 3

    # Logging
    log_level: str = "INFO"


settings = Settings()
