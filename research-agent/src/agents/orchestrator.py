"""Research pipeline orchestrator."""

import logging
import time
import uuid
from datetime import datetime

from src.agents.discovery import DiscoveryAgent
from src.agents.scoring import ScoringAgent
from src.agents.validation import ValidationAgent
from src.config import settings
from src.models import ResearchReport
from src.slack.interactions import store_report

logger = logging.getLogger(__name__)


def run_research_pipeline() -> ResearchReport:
    """
    Run the complete research pipeline.

    Returns:
        ResearchReport with top opportunities
    """
    start_time = time.time()
    report_id = str(uuid.uuid4())

    logger.info(f"Starting research pipeline (report_id: {report_id})")

    # Initialize agents
    discovery_agent = DiscoveryAgent()
    validation_agent = ValidationAgent()
    scoring_agent = ScoringAgent()

    # Run pipeline
    context = {}

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
