"""Phase output models for factory agents."""

from dataclasses import dataclass, field
from typing import Optional


# =============================================================================
# RESEARCH ENRICHMENT OUTPUTS
# =============================================================================


@dataclass
class UserPersona:
    """Detailed user persona with Jobs-to-be-Done."""

    name: str
    role: str
    demographics: str
    goals: list[str]
    frustrations: list[str]
    jobs_to_be_done: list[str]
    willingness_to_pay: str
    acquisition_channels: list[str]


@dataclass
class CompetitorFeatureMatrix:
    """Detailed competitor comparison."""

    competitor_name: str
    website: str
    pricing_tiers: list[dict]
    feature_comparison: dict[str, bool]
    key_strengths: list[str]
    key_gaps: list[str]
    review_summary: str


@dataclass
class SEOStrategy:
    """Keyword and content strategy."""

    primary_keywords: list[dict]
    long_tail_keywords: list[str]
    content_opportunities: list[str]
    competitor_ranking_gaps: list[str]
    estimated_organic_potential: str


@dataclass
class ResearchEnrichmentOutput:
    """Output from Research Enrichment phase."""

    personas: list[UserPersona]
    primary_persona: str
    competitor_matrix: list[CompetitorFeatureMatrix]
    competitive_landscape_miro_url: str
    positioning_statement: str
    seo_strategy: SEOStrategy
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
    user_flow_miro_url: str
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
    architecture_miro_url: str
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
class EmailSequence:
    """Email sequence content."""

    name: str
    subject: str
    body_html: str
    send_delay_hours: int


@dataclass
class SocialContent:
    """Social media content."""

    twitter_thread: list[str]
    linkedin_post: str
    twitter_launch_tweet: str


@dataclass
class ProductHuntListing:
    """Product Hunt listing content."""

    tagline: str
    description: str
    first_comment: str
    topics: list[str]


@dataclass
class LaunchPrepOutput:
    """Output from Launch Prep phase."""

    landing_page_copy: dict
    email_sequences: list[EmailSequence]
    social_content: SocialContent
    product_hunt_listing: ProductHuntListing
    launch_checklist: list[dict]
    linear_issues: list[str] = field(default_factory=list)


# =============================================================================
# LAUNCH OUTPUTS
# =============================================================================


@dataclass
class LaunchOutput:
    """Output from Launch phase."""

    production_url: str
    scheduled_posts: list[str]
    email_broadcast_ids: list[str]
    launch_metrics_dashboard_url: str
    linear_issues: list[str] = field(default_factory=list)


# =============================================================================
# GROWTH OUTPUTS
# =============================================================================


@dataclass
class GrowthExperiment:
    """Growth experiment hypothesis."""

    name: str
    hypothesis: str
    metric: str
    success_criteria: str
    implementation_notes: str


@dataclass
class GrowthOutput:
    """Output from Growth phase."""

    experiments: list[GrowthExperiment]
    analytics_events: list[dict]
    weekly_report_template: str
    growth_playbook: str
    faq_content: str
    help_articles: list[dict]
    linear_issues: list[str] = field(default_factory=list)
