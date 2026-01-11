"""Models for factory handoff and state."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class Phase(Enum):
    """Factory execution phases."""

    RESEARCH_ENRICHMENT = "research_enrichment"
    DESIGN = "design"
    SPEC = "spec"
    BUILD = "build"
    LAUNCH_PREP = "launch_prep"
    LAUNCH = "launch"
    GROWTH = "growth"


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
class OpportunitySummary:
    """Condensed opportunity data from research agent."""

    name: str
    slug: str
    one_liner: str
    detailed_description: str
    category: str
    target_segment: str
    business_model: str
    problem_statement: str
    current_solutions: list[str]
    pain_intensity: int
    frequency: str
    target_market_description: str
    geographic_focus: list[str]
    direct_competitors: list[str]
    competitor_weaknesses: list[str]
    differentiation_angle: str
    build_complexity: str
    estimated_build_weeks: int
    key_technical_components: list[str]
    platform_dependencies: list[str]
    suggested_price_low: int
    suggested_price_mid: int
    suggested_price_high: int


@dataclass
class ValidationSummary:
    """Key validation signals from research agent."""

    four_u_score: int
    four_u_breakdown: dict[str, int]
    is_graveyard_market: bool
    platform_risk_level: str
    key_risks: list[str]
    key_opportunities: list[str]


@dataclass
class ForecastSummary:
    """Revenue projections from research agent."""

    assumed_arpu: int
    mrr_month_12_conservative: int
    mrr_month_12_moderate: int
    mrr_month_12_optimistic: int
    mrr_month_24_moderate: int


@dataclass
class BuildPreferences:
    """Operator preferences for build phase."""

    tech_stack: dict[str, str] = field(
        default_factory=lambda: {
            "frontend": "nextjs",
            "backend": "python",
            "database": "postgresql",
        }
    )
    hosting_preference: str = "vercel"
    database_preference: str = "neon"
    auth_preference: str = "clerk"
    payments_preference: str = "stripe"


@dataclass
class LaunchPreferences:
    """Operator preferences for launch phase."""

    target_launch_date: Optional[datetime] = None
    launch_on_product_hunt: bool = True
    launch_on_twitter: bool = True
    launch_on_linkedin: bool = True
    email_provider: str = "resend"
    launch_pricing_tier: str = "mid"


@dataclass
class FactoryHandoff:
    """Handoff payload from Research Agent to SaaS Factory."""

    handoff_id: str
    triggered_at: datetime
    triggered_by: str
    research_report_id: str
    opportunity_id: str
    linear_project_id: str
    linear_project_url: str
    opportunity: OpportunitySummary
    validation: ValidationSummary
    forecast: ForecastSummary
    build_preferences: BuildPreferences = field(default_factory=BuildPreferences)
    launch_preferences: LaunchPreferences = field(default_factory=LaunchPreferences)
    approval_checkpoints: list[str] = field(
        default_factory=lambda: ["design", "build", "launch"]
    )


@dataclass
class FactoryState:
    """Persisted state for factory execution."""

    execution_id: str
    handoff: FactoryHandoff
    current_phase: Phase = Phase.RESEARCH_ENRICHMENT
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
