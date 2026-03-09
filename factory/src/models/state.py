"""Models for factory handoff and state."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class Phase(Enum):
    """Factory execution phases."""

    PRD_ANALYSIS = "prd_analysis"
    DESIGN = "design"
    SPEC = "spec"
    BUILD = "build"
    LAUNCH_PREP = "launch_prep"


class PhaseStatus(Enum):
    """Status of a phase."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PRDInput:
    """PRD input from user submission."""

    name: str
    slug: str
    prd_text: str
    submitted_by: str
    tech_stack_preference: Optional[str] = None
    additional_context: Optional[str] = None


@dataclass
class BuildPreferences:
    """Operator preferences for build phase."""

    tech_stack: dict[str, str] = field(
        default_factory=lambda: {
            "frontend": "rails",
            "backend": "ruby",
            "database": "postgresql",
        }
    )
    hosting_preference: str = "railway"
    database_preference: str = "railway"
    auth_preference: str = "devise"
    payments_preference: str = "stripe"


@dataclass
class FactoryHandoff:
    """Handoff payload from PRD submission to SaaS Factory."""

    handoff_id: str
    triggered_at: datetime
    triggered_by: str
    linear_project_id: str
    linear_project_url: str
    prd_input: PRDInput
    build_preferences: BuildPreferences = field(default_factory=BuildPreferences)
    approval_checkpoints: list[str] = field(
        default_factory=lambda: ["design", "build"]
    )


@dataclass
class FactoryState:
    """Persisted state for factory execution."""

    execution_id: str
    handoff: FactoryHandoff
    current_phase: Phase = Phase.PRD_ANALYSIS
    phase_statuses: dict[str, PhaseStatus] = field(default_factory=dict)
    phase_outputs: dict[str, Any] = field(default_factory=dict)
    checkpoints_cleared: list[str] = field(default_factory=list)
    linear_issues: dict[str, list[str]] = field(default_factory=dict)
    # Phase issue tracking (issue IDs for each phase placeholder)
    linear_phase_issues: dict[str, dict] = field(default_factory=dict)
    # Team ID for Linear operations (cached after first lookup)
    linear_team_id: Optional[str] = None
    errors: list[dict] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    # Slack channels created for this opportunity
    slack_channels: dict[str, str] = field(default_factory=dict)
    # GitHub repository info (set by CodeAgent, used by TestAgent, DevOpsAgent, QAAgent)
    github_repo: Optional[dict[str, str]] = None
    # Slack thread for PRD Q&A
    slack_qa_thread_ts: Optional[str] = None

    def update_phase_status(self, phase: Phase, status: PhaseStatus):
        """
        Update status of a phase.

        Args:
            phase: Phase enum instance (not string like "build")
            status: PhaseStatus enum instance (not string like "completed")
        """
        self.phase_statuses[phase.value] = status
        self.last_updated_at = datetime.utcnow()

    def store_output(self, phase: Phase, output: Any):
        """
        Store output from a phase.

        Args:
            phase: Phase enum instance (not string like "build")
            output: Output data for the phase (dict or dataclass)
        """
        self.phase_outputs[phase.value] = output
        self.last_updated_at = datetime.utcnow()

    def clear_checkpoint(self, checkpoint: str):
        """Mark a checkpoint as cleared."""
        if checkpoint not in self.checkpoints_cleared:
            self.checkpoints_cleared.append(checkpoint)
        self.last_updated_at = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert to dictionary for persistence."""
        return {
            "execution_id": self.execution_id,
            "handoff_id": self.handoff.handoff_id,
            "current_phase": self.current_phase.value,
            "phase_statuses": {k: v.value for k, v in self.phase_statuses.items()},
            "checkpoints_cleared": self.checkpoints_cleared,
            "started_at": self.started_at.isoformat(),
            "last_updated_at": self.last_updated_at.isoformat(),
        }
