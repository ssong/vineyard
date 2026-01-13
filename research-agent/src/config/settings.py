"""Configuration settings for the research agent."""

from typing import Optional

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
    max_opportunities: int = 5

    # Diversity settings
    # Comma-separated list of frameworks to focus on (empty = all)
    # Options: unbundling, productized_service, integration, boring_business, developer_tools, automation
    focus_frameworks: Optional[str] = None

    # Comma-separated list of industries to focus on (empty = random sample)
    focus_industries: Optional[str] = None

    # Number of industries to sample per run (if not focusing)
    industries_per_run: int = 8

    # Total search queries per run
    queries_per_run: int = 10

    # History lookback period in days (for deduplication)
    history_lookback_days: int = 90

    # Similarity threshold for deduplication (0-1, higher = stricter)
    similarity_threshold: float = 0.6

    # Logging
    log_level: str = "INFO"


settings = Settings()
