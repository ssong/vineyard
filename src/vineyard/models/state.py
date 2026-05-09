"""Run state machine."""

from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from vineyard.models.handoff import Handoff


class Phase(str, Enum):
    PRD_ANALYSIS = "prd_analysis"
    DESIGN = "design"
    SPEC = "spec"
    BUILD = "build"


class PhaseStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    COMPLETED = "completed"
    FAILED = "failed"


PHASE_ORDER: list[Phase] = [Phase.PRD_ANALYSIS, Phase.DESIGN, Phase.SPEC, Phase.BUILD]


class RunState(BaseModel):
    run_id: str
    handoff: Handoff
    output_dir: Path

    current_phase: Phase = Phase.PRD_ANALYSIS
    phase_statuses: dict[str, PhaseStatus] = Field(default_factory=dict)
    phase_outputs: dict[str, Any] = Field(default_factory=dict)
    checkpoints_cleared: list[str] = Field(default_factory=list)

    cost_usd: float = 0.0
    logfire_trace_id: str | None = None

    errors: list[dict[str, Any]] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    def update_phase_status(self, phase: Phase, status: PhaseStatus) -> None:
        self.phase_statuses[phase.value] = status
        self.last_updated_at = datetime.now(UTC)

    def store_output(self, phase: Phase, output: Any) -> None:
        self.phase_outputs[phase.value] = output
        self.last_updated_at = datetime.now(UTC)

    def clear_checkpoint(self, checkpoint: str) -> None:
        if checkpoint not in self.checkpoints_cleared:
            self.checkpoints_cleared.append(checkpoint)
        self.last_updated_at = datetime.now(UTC)

    def add_cost(self, usd: float) -> None:
        self.cost_usd += usd
        self.last_updated_at = datetime.now(UTC)
