"""PRD input + build preferences + handoff payload."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from vineyard.config import ExecutorName, StackName

AuthChoice = Literal["none", "magic_link", "oauth", "credentials", "devise"]
PaymentsChoice = Literal["none", "stripe", "paddle"]
DBChoice = Literal["sqlite", "postgresql", "mysql"]


class PRDInput(BaseModel):
    name: str
    slug: str
    prd_text: str
    submitted_by: str = "local"
    additional_context: str | None = None


class BuildPreferences(BaseModel):
    stack: StackName
    auth: AuthChoice = "magic_link"
    payments: PaymentsChoice = "none"
    db: DBChoice = "postgresql"


class Handoff(BaseModel):
    handoff_id: str
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    triggered_by: str = "local"
    prd_input: PRDInput
    build_preferences: BuildPreferences
    executor: ExecutorName = "pydantic_ai"
    approval_checkpoints: list[str] = Field(default_factory=lambda: ["design", "build"])
