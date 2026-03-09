"""Phase output models for factory agents."""

from dataclasses import dataclass, field
from typing import Optional


# =============================================================================
# PRD ANALYSIS OUTPUTS
# =============================================================================


@dataclass
class PRDAnalysisOutput:
    """Output from PRD Analysis phase."""

    product_name: str
    product_summary: str
    enriched_prd_markdown: str
    identified_gaps: list[str]
    clarification_qa: list[dict]  # [{"question": str, "answer": str}]
    target_users: list[str]
    core_problem: str
    mvp_scope_notes: str
    linear_issues: list[str] = field(default_factory=list)


# =============================================================================
# DESIGN OUTPUTS
# =============================================================================


@dataclass
class FeatureSpec:
    """Specification for a single feature."""

    name: str
    description: str
    priority: str  # P0, P1, P2
    user_stories: list[str]
    acceptance_criteria: list[str]
    technical_notes: str


@dataclass
class DesignOutput:
    """Output from Design phase."""

    prd_markdown: str
    user_flows: list[dict]
    features: list[FeatureSpec]
    ui_copy: dict[str, str]
    linear_issues: list[str] = field(default_factory=list)


# =============================================================================
# SPEC OUTPUTS
# =============================================================================


@dataclass
class APIEndpoint:
    """API endpoint specification."""

    method: str
    path: str
    description: str
    request_schema: dict
    response_schema: dict
    auth_required: bool


@dataclass
class DatabaseTable:
    """Database table specification."""

    name: str
    description: str
    columns: list[dict]
    indexes: list[str]
    relationships: list[str]


@dataclass
class EngineeringTask:
    """Engineering task for Linear."""

    title: str
    description: str
    acceptance_criteria: list[str]
    story_points: int
    labels: list[str]
    dependencies: list[str]


@dataclass
class SpecOutput:
    """Output from Spec phase."""

    technical_spec_markdown: str
    api_endpoints: list[APIEndpoint]
    database_schema: list[DatabaseTable]
    task_breakdown: list[EngineeringTask]
    linear_issues: list[str] = field(default_factory=list)


# =============================================================================
# BUILD OUTPUTS
# =============================================================================


@dataclass
class GeneratedFile:
    """A generated code file."""

    path: str
    content: str
    language: str


@dataclass
class BuildOutput:
    """Output from Build phase."""

    files: list[GeneratedFile]
    github_repo_url: str
    staging_url: str
    test_results: dict
    security_scan_results: dict
    deploy_config: dict
    linear_issues: list[str] = field(default_factory=list)


# =============================================================================
# LAUNCH PREP OUTPUTS
# =============================================================================


@dataclass
class LaunchPrepOutput:
    """Output from Launch Prep phase."""

    landing_page_copy: dict
    launch_checklist: list[dict]
    linear_issues: list[str] = field(default_factory=list)
