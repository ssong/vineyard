"""Vineyard runtime settings — loaded from env / .env / ~/.vineyard/config.env."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATA_DIR = Path.home() / ".vineyard"

StackName = Literal["rails", "nextjs", "fastapi", "django"]
ExecutorName = Literal["pydantic_ai", "managed_agents"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", str(DEFAULT_DATA_DIR / "config.env")),
        env_file_encoding="utf-8",
        env_prefix="VINEYARD_",
        extra="ignore",
    )

    pydantic_ai_gateway_api_key: str = ""
    logfire_token: str = ""
    logfire_read_token: str = ""
    anthropic_api_key: str = ""

    default_stack: StackName = "nextjs"
    build_executor: ExecutorName = "pydantic_ai"

    data_dir: Path = DEFAULT_DATA_DIR
    log_level: str = "INFO"

    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    def db_path(self) -> Path:
        return self.data_dir / "vineyard.db"

    def output_dir(self, run_id: str) -> Path:
        return self.runs_dir() / run_id / "output"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.runs_dir().mkdir(parents=True, exist_ok=True, mode=0o700)


settings = Settings()
