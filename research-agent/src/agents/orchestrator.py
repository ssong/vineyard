"""Research pipeline orchestrator."""

import logging
import time
import uuid
from datetime import datetime
from typing import Optional

from src.agents.discovery import DiscoveryAgent
from src.agents.scoring import ScoringAgent
from src.agents.validation import ValidationAgent
from src.config import settings
from src.config.diversity import DiversityConfig
from src.models import ResearchReport
from src.slack.interactions import store_report

logger = logging.getLogger(__name__)


def build_diversity_config() -> DiversityConfig:
    """Build diversity configuration from settings."""
    config = DiversityConfig()

    # Parse focus frameworks from settings
    if settings.focus_frameworks:
        config.focus_frameworks = [
            f.strip() for f in settings.focus_frameworks.split(",")
            if f.strip()
        ]

    # Parse focus industries from settings
    if settings.focus_industries:
        config.focus_industries = [
            i.strip() for i in settings.focus_industries.split(",")
            if i.strip()
        ]

    # Apply other settings
    config.industries_per_run = settings.industries_per_run
    config.total_queries = settings.queries_per_run

    return config


def run_research_pipeline(
    focus_frameworks: Optional[list[str]] = None,
    focus_industries: Optional[list[str]] = None,
) -> ResearchReport:
    """
    Run the complete research pipeline.

    Args:
        focus_frameworks: Optional list of framework IDs to focus on
            (unbundling, productized_service, integration, boring_business,
             developer_tools, automation)
        focus_industries: Optional list of industries to focus on

    Returns:
        ResearchReport with top opportunities
    """
    start_time = time.time()
    report_id = str(uuid.uuid4())

    logger.info(f"Starting research pipeline (report_id: {report_id})")

    # Build diversity configuration
    diversity_config = build_diversity_config()

    # Apply runtime overrides
    if focus_frameworks:
        diversity_config.focus_frameworks = focus_frameworks
        logger.info(f"Focusing on frameworks: {focus_frameworks}")
    if focus_industries:
        diversity_config.focus_industries = focus_industries
        logger.info(f"Focusing on industries: {focus_industries}")

    # Initialize agents with diversity config
    discovery_agent = DiscoveryAgent(config=diversity_config)
    validation_agent = ValidationAgent()
    scoring_agent = ScoringAgent()

    # Run pipeline with diversity context
    context = {
        "diversity_config": diversity_config,
    }

    # Phase 1: Discovery
    logger.info("Phase 1: Discovery")
    context = discovery_agent.run(context)

    # Phase 2: Validation
    logger.info("Phase 2: Validation")
    context = validation_agent.run(context)

    # Phase 3: Scoring
    logger.info("Phase 3: Scoring")
    context = scoring_agent.run(context)

    # Build final report
    opportunity_reports = context.get("opportunity_reports", [])
    top_opportunities = opportunity_reports[: settings.max_opportunities]

    duration_seconds = int(time.time() - start_time)

    # Extract run metadata from discovery phase
    run_metadata = context.get("run_metadata", {})
    queries_used = run_metadata.get("queries_used", [])
    industries_sampled = run_metadata.get("industries_sampled", [])
    frameworks_used = run_metadata.get("frameworks_used", [])

    report = ResearchReport(
        report_id=report_id,
        generated_at=datetime.utcnow(),
        research_duration_seconds=duration_seconds,
        executive_summary=_generate_executive_summary(top_opportunities),
        opportunities=top_opportunities,
        top_recommendation=top_opportunities[0] if top_opportunities else None,
        top_recommendation_rationale=(
            top_opportunities[0].recommendation_rationale if top_opportunities else ""
        ),
        data_sources_used=["Tavily Web Search", "Claude AI Analysis"],
        limitations=[
            "Market size estimates are approximations",
            "Revenue projections based on industry benchmarks",
            "Competitor data may be incomplete",
        ],
    )

    # Log diversity info for debugging
    logger.info(f"Run metadata - Queries: {len(queries_used)}, "
                f"Industries: {industries_sampled}, Frameworks: {frameworks_used}")

    # Store for later retrieval
    store_report(report_id, report)

    logger.info(
        f"Research pipeline complete in {duration_seconds}s. "
        f"Found {len(top_opportunities)} opportunities."
    )

    return report


def _generate_executive_summary(opportunity_reports: list) -> str:
    """Generate executive summary for the report."""
    if not opportunity_reports:
        return "No viable opportunities identified in this research cycle."

    top = opportunity_reports[0]
    opp = top.opportunity

    return (
        f"This research cycle identified {len(opportunity_reports)} promising opportunities. "
        f"The top recommendation is **{opp.name}** ({opp.one_liner}) with an overall score of "
        f"{opp.overall_score}/100. This opportunity targets {opp.target_segment.value} customers "
        f"with a {opp.business_model.value} model. Estimated time to build: {opp.estimated_build_weeks} weeks."
    )
