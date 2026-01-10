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
    PhaseStatus,
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
        # Create handoff from Linear project
        handoff = _create_handoff_from_project(project_id, user_id)

        # Create factory run
        state = create_factory_run(handoff)

        # Create opportunity Slack channels
        from src.slack.channels import create_opportunity_channels
        from src.orchestrator.persistence import save_state

        slack_channels = create_opportunity_channels(
            opportunity_slug=handoff.opportunity.slug,
            opportunity_name=handoff.opportunity.name,
        )
        state.slack_channels = slack_channels

        # Save state with channel info
        save_state(state)

        # Post initial message to main channel if created
        if "main" in slack_channels:
            from src.slack.app import app as slack_app
            slack_app.client.chat_postMessage(
                channel=slack_channels["main"],
                text=f"🏭 *Factory run started for {handoff.opportunity.name}*\n\n"
                f"📋 <{handoff.linear_project_url}|View in Linear>\n\n"
                "_Automated updates will be posted to #{}-alerts_".format(handoff.opportunity.slug),
            )

        # Use alerts channel for notifications (fall back to command channel)
        notification_channel = slack_channels.get("alerts", channel_id)

        # Run factory
        _run_factory_async(state, notification_channel)

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
        # Run until checkpoint or completion (pass channel_id for checkpoint notifications)
        result = run_factory(state, channel_id)

        # Post final status
        if result.completed_at:
            slack_app.client.chat_postMessage(
                channel=channel_id,
                text="✅ *Factory run complete!*\n\n"
                f"All phases finished successfully.\n"
                f"Linear project: {result.handoff.linear_project_url}",
            )
        elif result.phase_statuses.get(result.current_phase.value) == PhaseStatus.AWAITING_APPROVAL:
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


def _generate_slug(name: str) -> str:
    """Generate a URL-safe slug from a name."""
    import re
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug[:50]


def _create_handoff_from_project(project_id: str, user_id: str) -> FactoryHandoff:
    """Create a handoff from a Linear project."""
    from src.tools.linear import get_project

    # Fetch project details from Linear
    project = get_project(project_id)
    project_name = project.get("name", "Unnamed Project") if project else "Unnamed Project"
    project_url = project.get("url", f"https://linear.app/project/{project_id}") if project else f"https://linear.app/project/{project_id}"
    project_slug = _generate_slug(project_name)
    project_description = (project.get("description") or "") if project else ""

    return FactoryHandoff(
        handoff_id=str(uuid.uuid4()),
        triggered_at=datetime.utcnow(),
        triggered_by=user_id,
        research_report_id=f"project-{project_id}",
        opportunity_id=project_id,
        linear_project_id=project_id,
        linear_project_url=project_url,
        opportunity=OpportunitySummary(
            name=project_name,
            slug=project_slug,
            one_liner=project_description or f"Building {project_name}",
            detailed_description=project_description or f"Factory build for {project_name}",
            category="automation",
            target_segment="smb",
            business_model="subscription_monthly",
            problem_statement=f"Building {project_name}",
            current_solutions=["Manual process"],
            pain_intensity=7,
            frequency="daily",
            target_market_description="Target users",
            geographic_focus=["global"],
            direct_competitors=[],
            competitor_weaknesses=[],
            differentiation_angle="Unique approach",
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
