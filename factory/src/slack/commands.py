"""Slack slash command handlers for factory."""

import logging
import uuid
from datetime import datetime

from slack_bolt import Ack, Respond

from src.models import (
    BuildPreferences,
    FactoryHandoff,
    ForecastSummary,
    LaunchPreferences,
    OpportunitySummary,
    ValidationSummary,
)
from src.orchestrator import create_factory_run, run_factory
from src.slack.app import app
from src.slack.notifications import send_phase_update, send_checkpoint_request

logger = logging.getLogger(__name__)


@app.command("/vineyard")
def handle_vineyard_command(ack: Ack, respond: Respond, command: dict):
    """Handle /vineyard slash command."""
    ack()

    subcommand = command.get("text", "").strip().lower()

    if subcommand.startswith("build"):
        handle_build_command(respond, command)
    elif subcommand == "help":
        respond(
            text="*Vineyard Factory Commands*\n"
            "• `/vineyard build [project-id]` - Start factory for a project\n"
            "• `/vineyard help` - Show this help message"
        )
    else:
        respond(
            text="Unknown command. Use `/vineyard help` to see available commands."
        )


def handle_build_command(respond: Respond, command: dict):
    """Start factory build for a project."""
    text = command.get("text", "").strip()
    parts = text.split()

    project_id = parts[1] if len(parts) > 1 else None
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    if not project_id:
        respond(
            text="Please provide a project ID: `/vineyard build [project-id]`\n\n"
            "_You can find the project ID in Linear or from the research agent output._"
        )
        return

    respond(
        text=f"🏭 *Factory starting for project {project_id}*\n"
        "_This will take a few minutes. I'll post updates as each phase completes._"
    )

    try:
        # Create handoff (in production, this would load from research agent output)
        handoff = _create_demo_handoff(project_id, user_id)

        # Create factory run
        state = create_factory_run(handoff)

        # Run factory
        _run_factory_async(state, channel_id)

    except Exception as e:
        logger.exception("Factory failed to start")
        from src.slack.app import app as slack_app

        slack_app.client.chat_postMessage(
            channel=channel_id,
            text=f"❌ Factory failed to start: {str(e)}",
        )


def _run_factory_async(state, channel_id: str):
    """Run factory and post updates."""
    from src.slack.app import app as slack_app

    try:
        # Run until checkpoint or completion
        result = run_factory(state)

        # Post final status
        if result.completed_at:
            slack_app.client.chat_postMessage(
                channel=channel_id,
                text="✅ *Factory run complete!*\n\n"
                f"All phases finished successfully.\n"
                f"Linear project: {result.handoff.linear_project_url}",
            )
        elif result.phase_statuses.get(result.current_phase.value) == "awaiting_approval":
            send_checkpoint_request(channel_id, result)
        else:
            # Failed
            slack_app.client.chat_postMessage(
                channel=channel_id,
                text=f"⚠️ Factory paused at *{result.current_phase.value}*\n"
                f"Check Linear for details.",
            )

    except Exception as e:
        logger.exception("Factory run failed")
        slack_app.client.chat_postMessage(
            channel=channel_id,
            text=f"❌ Factory run failed: {str(e)}",
        )


def _create_demo_handoff(project_id: str, user_id: str) -> FactoryHandoff:
    """Create a demo handoff for testing."""
    return FactoryHandoff(
        handoff_id=str(uuid.uuid4()),
        triggered_at=datetime.utcnow(),
        triggered_by=user_id,
        research_report_id="demo-report",
        opportunity_id="demo-opp",
        linear_project_id=project_id,
        linear_project_url=f"https://linear.app/team/project/{project_id}",
        opportunity=OpportunitySummary(
            name="Demo Product",
            slug="demo-product",
            one_liner="A demo product for testing the factory",
            detailed_description="This is a demo product used to test the factory pipeline.",
            category="automation",
            target_segment="smb",
            business_model="subscription_monthly",
            problem_statement="Demo problem statement",
            current_solutions=["Manual process"],
            pain_intensity=7,
            frequency="daily",
            target_market_description="Small business owners",
            geographic_focus=["global"],
            direct_competitors=["Competitor A", "Competitor B"],
            competitor_weaknesses=["Too expensive", "Complex"],
            differentiation_angle="Simple and affordable",
            build_complexity="medium",
            estimated_build_weeks=4,
            key_technical_components=["API", "Dashboard"],
            platform_dependencies=[],
            suggested_price_low=1900,
            suggested_price_mid=4900,
            suggested_price_high=9900,
        ),
        validation=ValidationSummary(
            four_u_score=78,
            four_u_breakdown={"unworkable": 20, "unavoidable": 18, "urgent": 20, "underserved": 20},
            is_graveyard_market=False,
            platform_risk_level="low",
            key_risks=["Competition"],
            key_opportunities=["Growing market"],
        ),
        forecast=ForecastSummary(
            assumed_arpu=4900,
            mrr_month_12_conservative=240000,
            mrr_month_12_moderate=480000,
            mrr_month_12_optimistic=850000,
            mrr_month_24_moderate=1200000,
        ),
        build_preferences=BuildPreferences(),
        launch_preferences=LaunchPreferences(),
        approval_checkpoints=["design", "build", "launch"],
    )
