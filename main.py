"""Vineyard Bot - Unified entry point for Research Agent and Factory.

This module creates a single Slack App instance shared by both systems,
reducing resource usage and ensuring consistent bot behavior.

APPROACH: Register a unified /vineyard command handler that routes to the
appropriate project based on subcommand. Interaction handlers (@app.action)
are imported from each project since they use unique action IDs.
"""

import argparse
import logging
import os
import sys
import threading

from dotenv import load_dotenv
from slack_bolt import App, Ack, Respond
from slack_bolt.adapter.socket_mode import SocketModeHandler

# Load environment variables first
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Compute paths once at module level
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESEARCH_AGENT_PATH = os.path.join(BASE_DIR, "research-agent")
FACTORY_PATH = os.path.join(BASE_DIR, "factory")


def clear_src_modules():
    """Clear all src.* modules from sys.modules."""
    modules_to_remove = [key for key in list(sys.modules.keys()) 
                         if key.startswith('src.') or key == 'src']
    for mod in modules_to_remove:
        del sys.modules[mod]
    return len(modules_to_remove)


def set_project_path(project_path):
    """Set a project path at the front of sys.path."""
    if project_path in sys.path:
        sys.path.remove(project_path)
    sys.path.insert(0, project_path)


def get_factory_settings():
    """Load settings from factory config."""
    set_project_path(FACTORY_PATH)
    from src.config import settings
    return settings


def create_shared_app(settings):
    """Create the shared Slack App instance."""
    return App(token=settings.slack_bot_token)


def inject_app_module(project_path, shared_app):
    """Inject a pre-made src.slack.app module with our shared app.

    This ensures that when command modules do `from src.slack.app import app`,
    they get our shared app instance, and decorators register to it directly.
    """
    import types

    # Create the module hierarchy
    src_module = types.ModuleType('src')
    src_module.__path__ = [os.path.join(project_path, 'src')]

    slack_module = types.ModuleType('src.slack')
    slack_module.__path__ = [os.path.join(project_path, 'src', 'slack')]

    app_module = types.ModuleType('src.slack.app')
    app_module.app = shared_app
    app_module.__file__ = os.path.join(project_path, 'src', 'slack', 'app.py')

    # Wire up the module hierarchy
    src_module.slack = slack_module

    # The __init__.py does `from .app import app`, so src.slack.app should be:
    # 1. A module (src.slack.app) with an `app` attribute
    # 2. Also exported as src.slack.app (the App instance) from __init__.py
    # We set both: the submodule reference and the direct app instance
    setattr(slack_module, 'app', shared_app)  # src.slack.app = App instance (from __init__.py export)

    # Inject into sys.modules
    sys.modules['src'] = src_module
    sys.modules['src.slack'] = slack_module
    sys.modules['src.slack.app'] = app_module  # src.slack.app module


def register_research_agent_handlers(shared_app, settings):
    """Register Research Agent interaction handlers (not commands)."""
    set_project_path(RESEARCH_AGENT_PATH)
    clear_src_modules()

    # Pre-inject the app module with our shared app
    inject_app_module(RESEARCH_AGENT_PATH, shared_app)

    # Track listener count before import
    before_count = len(shared_app._listeners) if hasattr(shared_app, '_listeners') else 0

    # Import ONLY interactions (not commands - we use unified command handler)
    # Interactions use unique action IDs so they won't conflict
    from src.slack import interactions  # noqa: F401

    after_count = len(shared_app._listeners) if hasattr(shared_app, '_listeners') else 0
    new_listeners = after_count - before_count
    logger.info(f"✓ Research Agent interaction handlers registered ({new_listeners} listeners)")


def register_factory_handlers(shared_app, settings):
    """Register Factory interaction handlers (not commands)."""
    set_project_path(FACTORY_PATH)
    clear_src_modules()

    # Pre-inject the app module with our shared app
    inject_app_module(FACTORY_PATH, shared_app)

    # Track listener count before import
    before_count = len(shared_app._listeners) if hasattr(shared_app, '_listeners') else 0

    # Import ONLY interactions (not commands - we use unified command handler)
    # Interactions use unique action IDs so they won't conflict
    from src.slack import interactions  # noqa: F401

    after_count = len(shared_app._listeners) if hasattr(shared_app, '_listeners') else 0
    new_listeners = after_count - before_count
    logger.info(f"✓ Factory interaction handlers registered ({new_listeners} listeners)")


def start_api_server(settings):
    """Start the Factory API server for Linear webhooks."""
    set_project_path(FACTORY_PATH)
    clear_src_modules()

    from src.api.server import start_server

    logger.info(f"Starting API server on {settings.api_host}:{settings.api_port}")
    start_server(host=settings.api_host, port=settings.api_port)


def register_unified_command_handler(shared_app):
    """Register a unified /vineyard command handler that routes to both projects."""

    @shared_app.command("/vineyard")
    def handle_vineyard_command(ack: Ack, respond: Respond, command: dict):
        """Unified handler for /vineyard command - routes to appropriate project."""
        ack()

        subcommand = command.get("text", "").strip().lower()

        if subcommand == "new":
            # Route to research-agent
            _handle_research_new(respond, command, shared_app)
        elif subcommand.startswith("build"):
            # Route to factory
            _handle_factory_build(respond, command, shared_app)
        elif subcommand.startswith("resume"):
            # Resume a failed factory run
            _handle_factory_resume(respond, command, shared_app)
        elif subcommand == "list" or subcommand == "projects":
            # List Linear projects
            _handle_list_projects(respond, shared_app)
        elif subcommand == "status" or subcommand == "runs":
            # List factory runs
            _handle_list_runs(respond, shared_app)
        elif subcommand == "history":
            # Show all research opportunities with status
            _handle_history(respond, shared_app)
        elif subcommand == "help":
            respond(
                text="*Vineyard Commands*\n"
                "• `/vineyard new` - Start a new research cycle\n"
                "• `/vineyard history` - Show all opportunities with status\n"
                "• `/vineyard list` - List available Linear projects\n"
                "• `/vineyard build [project-id]` - Start factory for a project\n"
                "• `/vineyard status` - List factory runs and their status\n"
                "• `/vineyard resume [execution-id]` - Resume a failed factory run\n"
                "• `/vineyard help` - Show this help message"
            )
        else:
            respond(
                text="Unknown command. Use `/vineyard help` to see available commands."
            )

    logger.info("✓ Unified /vineyard command handler registered")


def _handle_list_runs(respond: Respond, shared_app: App):
    """Handle /vineyard status - shows factory runs."""
    set_project_path(FACTORY_PATH)
    clear_src_modules()
    inject_app_module(FACTORY_PATH, shared_app)

    try:
        from src.orchestrator.persistence import list_states

        states = list_states()

        if not states:
            respond(
                text="No factory runs found.\n\n"
                "_Use `/vineyard build [project-id]` to start a new factory run._"
            )
            return

        lines = ["*Factory Runs*\n"]

        for state in states[:10]:  # Limit to 10 most recent
            exec_id = state.get("execution_id", "")
            phase = state.get("current_phase", "unknown")
            status = state.get("status", "unknown")
            name = state.get("opportunity_name", "Unknown")

            # Status emoji
            status_emoji = {
                "pending": "⏳",
                "in_progress": "🔄",
                "completed": "✅",
                "failed": "❌",
                "awaiting_approval": "⏸️",
            }.get(status, "📋")

            lines.append(f"{status_emoji} *{name}*")
            lines.append(f"   Phase: `{phase}` | Status: `{status}`")
            lines.append(f"   ID: `{exec_id}`")
            lines.append("")

        if len(states) > 10:
            lines.append(f"_...and {len(states) - 10} more runs_")

        lines.append("_Use `/vineyard resume [execution-id]` to resume a failed run_")

        respond(text="\n".join(lines))

    except Exception as e:
        logger.exception("Failed to list runs")
        respond(text=f"❌ Failed to list runs: {str(e)}")


def _handle_history(respond: Respond, shared_app: App):
    """Handle /vineyard history - shows all research opportunities with status."""
    from datetime import datetime

    set_project_path(RESEARCH_AGENT_PATH)
    clear_src_modules()
    inject_app_module(RESEARCH_AGENT_PATH, shared_app)

    try:
        from src.persistence import list_opportunities

        opportunities = list_opportunities(limit=50)

        if not opportunities:
            respond(
                text="📭 No opportunities found yet.\n\nRun `/vineyard new` to discover opportunities."
            )
            return

        # Build table header
        lines = [
            "*📊 Opportunity History*\n",
            "```",
            f"{'Status':<10} {'Score':<6} {'Name':<30} {'ID':<10} {'Date':<12}",
            f"{'-'*10} {'-'*6} {'-'*30} {'-'*10} {'-'*12}",
        ]

        for opp in opportunities:
            # Map status to display
            status = opp.get("status", "pending")
            if status == "selected":
                status_display = "✅ Accept"
            elif status == "rejected":
                status_display = "❌ Reject"
            else:
                status_display = "⏳ Pending"

            score = opp.get("score", 0)
            name = opp.get("name", "Unknown")[:30]
            opp_id = opp.get("id", "")[:8]  # First 8 chars of UUID

            # Format created_at
            created = opp.get("created_at", "")
            if created:
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    date_str = created_dt.strftime("%Y-%m-%d")
                except Exception:
                    date_str = ""
            else:
                date_str = ""

            lines.append(f"{status_display:<10} {score:<6} {name:<30} {opp_id:<10} {date_str:<12}")

        lines.append("```")

        # Add summary
        total = len(opportunities)
        accepted = sum(1 for o in opportunities if o.get("status") == "selected")
        rejected = sum(1 for o in opportunities if o.get("status") == "rejected")
        pending = total - accepted - rejected

        lines.append(f"\n_Total: {total} | ✅ {accepted} accepted | ❌ {rejected} rejected | ⏳ {pending} pending_")

        respond(text="\n".join(lines))

    except Exception as e:
        logger.exception("Failed to list opportunity history")
        respond(text=f"❌ Failed to list history: {str(e)}")


def _handle_factory_resume(respond: Respond, command: dict, shared_app: App):
    """Handle /vineyard resume - resumes a failed factory run."""
    set_project_path(FACTORY_PATH)
    clear_src_modules()
    inject_app_module(FACTORY_PATH, shared_app)

    text = command.get("text", "").strip()
    parts = text.split()

    execution_id = parts[1] if len(parts) > 1 else None
    channel_id = command["channel_id"]

    if not execution_id:
        # Show list of failed runs that can be resumed
        try:
            from src.orchestrator.persistence import list_states

            failed_states = [s for s in list_states() if s.get("status") == "failed"]

            if not failed_states:
                respond(
                    text="No failed runs to resume.\n\n"
                    "_Use `/vineyard status` to see all factory runs._"
                )
                return

            lines = ["Please provide an execution ID: `/vineyard resume [execution-id]`\n"]
            lines.append("*Failed runs that can be resumed:*\n")

            for state in failed_states[:5]:
                exec_id = state.get("execution_id", "")
                name = state.get("opportunity_name", "Unknown")
                phase = state.get("current_phase", "unknown")
                lines.append(f"• *{name}* - failed at `{phase}`")
                lines.append(f"  ID: `{exec_id}`")

            respond(text="\n".join(lines))
            return

        except Exception as e:
            respond(
                text="Please provide an execution ID: `/vineyard resume [execution-id]`\n\n"
                "_Use `/vineyard status` to see all factory runs._"
            )
            return

    respond(
        text=f"🔄 *Resuming factory run*\n"
        f"Execution ID: `{execution_id[:8]}...`\n"
        "_Attempting to resume from last failed phase..._"
    )

    try:
        from src.orchestrator.runner import resume_factory
        from src.orchestrator.persistence import load_state

        # Validate execution exists
        state = load_state(execution_id)
        if not state:
            shared_app.client.chat_postMessage(
                channel=channel_id,
                text=f"❌ Execution not found: `{execution_id}`\n\n"
                "_Use `/vineyard status` to see available runs._"
            )
            return

        # Resume the factory
        updated_state = resume_factory(execution_id)

        if updated_state:
            phase_name = updated_state.current_phase.value.replace("_", " ").title()
            status = updated_state.phase_statuses.get(updated_state.current_phase.value)

            if updated_state.completed_at:
                shared_app.client.chat_postMessage(
                    channel=channel_id,
                    text=f"✅ *Factory run complete!*\n\n"
                    f"Project: {updated_state.handoff.opportunity.name}\n"
                    f"Linear: <{updated_state.handoff.linear_project_url}|View in Linear>"
                )
            elif status and status.value == "failed":
                shared_app.client.chat_postMessage(
                    channel=channel_id,
                    text=f"❌ *Factory failed again at {phase_name}*\n\n"
                    f"Check Linear for error details.\n"
                    f"Use `/vineyard resume {execution_id}` to try again."
                )
            else:
                shared_app.client.chat_postMessage(
                    channel=channel_id,
                    text=f"🔄 *Factory resumed*\n\n"
                    f"Current phase: *{phase_name}*\n"
                    f"Status: `{status.value if status else 'unknown'}`"
                )
        else:
            shared_app.client.chat_postMessage(
                channel=channel_id,
                text="❌ Failed to resume factory. Check logs for details."
            )

    except Exception as e:
        logger.exception("Failed to resume factory")
        shared_app.client.chat_postMessage(
            channel=channel_id,
            text=f"❌ Failed to resume: {str(e)}"
        )


def _handle_list_projects(respond: Respond, shared_app: App):
    """Handle /vineyard list - shows available Linear projects."""
    set_project_path(FACTORY_PATH)
    clear_src_modules()
    inject_app_module(FACTORY_PATH, shared_app)

    try:
        from src.tools.linear import list_projects

        projects = list_projects(limit=15)

        if not projects:
            respond(
                text="No projects found in Linear.\n\n"
                "_Create a project in Linear first, or run `/vineyard new` to discover opportunities._"
            )
            return

        # Build project list
        lines = ["*Available Linear Projects*\n"]

        for proj in projects:
            name = proj.get("name", "Untitled")
            proj_id = proj.get("id", "")
            state = proj.get("state", "").lower()
            url = proj.get("url", "")

            # Get team info
            teams = proj.get("teams", {}).get("nodes", [])
            team_key = teams[0].get("key", "") if teams else ""

            # State emoji
            state_emoji = {
                "planned": "📋",
                "started": "🚀",
                "paused": "⏸️",
                "completed": "✅",
                "canceled": "❌",
            }.get(state, "📁")

            # Format line with copyable ID
            if team_key:
                lines.append(f"{state_emoji} *{name}* ({team_key})")
            else:
                lines.append(f"{state_emoji} *{name}*")
            lines.append(f"   ID: `{proj_id}`")
            if url:
                lines.append(f"   <{url}|View in Linear>")
            lines.append("")

        lines.append("_Use `/vineyard build [project-id]` to start the factory_")

        respond(text="\n".join(lines))

    except Exception as e:
        logger.exception("Failed to list projects")
        respond(text=f"❌ Failed to list projects: {str(e)}")


def _handle_research_new(respond: Respond, command: dict, shared_app: App):
    """Handle /vineyard new - delegates to research-agent logic."""
    set_project_path(RESEARCH_AGENT_PATH)
    clear_src_modules()
    inject_app_module(RESEARCH_AGENT_PATH, shared_app)

    channel_id = command["channel_id"]
    user_id = command["user_id"]

    respond(
        text="🔍 *Research starting...*\n"
        "This typically takes 2-3 minutes.\n\n"
        "_Discovering opportunities, validating markets, and scoring potential..._"
    )

    try:
        from src.agents.orchestrator import run_research_pipeline
        from src.reports.generator import generate_markdown_report
        from src.reports.pdf import generate_pdf
        from src.slack.interactions import store_report

        report = run_research_pipeline()

        # Store report for later retrieval
        store_report(report.report_id, report)

        # Generate PDF
        markdown_content = generate_markdown_report(report)
        pdf_path = generate_pdf(markdown_content, report.report_id)

        # Upload PDF and post results
        _post_research_results(channel_id, user_id, report, pdf_path, shared_app)

    except Exception as e:
        logger.exception("Research pipeline failed")
        shared_app.client.chat_postMessage(
            channel=channel_id,
            text=f"❌ Research failed: {str(e)}\n\nPlease try again or check the logs.",
        )


def _post_research_results(channel_id: str, user_id: str, report, pdf_path: str, shared_app: App):
    """Post research results to Slack with interactive elements."""
    from datetime import datetime

    # Upload PDF
    shared_app.client.files_upload_v2(
        channel=channel_id,
        file=pdf_path,
        title=f"Research Report - {datetime.now().strftime('%Y-%m-%d')}",
        initial_comment="📊 *Research Complete*\n\nFull report attached below.",
    )

    # Build opportunity blocks
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🎯 Top Opportunities", "emoji": True},
        },
        {"type": "divider"},
    ]

    for i, opp_report in enumerate(report.opportunities[:5], 1):
        opp = opp_report.opportunity
        forecast = opp_report.forecast

        # Format MRR range
        mrr_low = forecast.mrr_month_12_conservative / 100
        mrr_high = forecast.mrr_month_12_optimistic / 100

        blocks.extend(
            [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*{i}. {opp.name}* (Score: {opp.overall_score}/100)\n"
                            f"{opp.one_liner}\n"
                            f"💰 ${mrr_low:,.0f} - ${mrr_high:,.0f} MRR @ 12mo"
                        ),
                    },
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Select This", "emoji": True},
                        "value": opp.id,
                        "action_id": f"select_opportunity_{i}",
                    },
                },
                {"type": "divider"},
            ]
        )

    # Add Reject All button
    blocks.append(
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ Reject All", "emoji": True},
                    "value": report.report_id,
                    "action_id": "reject_all_opportunities",
                    "style": "danger",
                }
            ],
        }
    )

    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"_Research completed in {report.research_duration_seconds}s._",
                }
            ],
        }
    )

    # Post message with metadata
    shared_app.client.chat_postMessage(
        channel=channel_id,
        blocks=blocks,
        text="Research results - select an opportunity to proceed",
        metadata={
            "event_type": "research_results",
            "event_payload": {"report_id": report.report_id},
        },
    )


def _generate_slug(name: str) -> str:
    """Generate a URL-safe slug from a name."""
    import re
    # Convert to lowercase, replace spaces with hyphens, remove non-alphanumeric
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug[:50]  # Limit length for Slack channel names


def _handle_factory_build(respond: Respond, command: dict, shared_app: App):
    """Handle /vineyard build - delegates to factory logic."""
    import uuid
    from datetime import datetime

    set_project_path(FACTORY_PATH)
    clear_src_modules()
    inject_app_module(FACTORY_PATH, shared_app)

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

    try:
        from src.models import (
            BuildPreferences,
            FactoryHandoff,
            ForecastSummary,
            LaunchPreferences,
            OpportunitySummary,
            ValidationSummary,
        )
        from src.orchestrator import create_factory_run, run_factory
        from src.slack.channels import create_opportunity_channels
        from src.orchestrator.persistence import save_state
        from src.slack.notifications import send_checkpoint_request
        from src.tools.linear import get_project

        # Fetch project details from Linear
        project = get_project(project_id)
        if not project:
            respond(
                text=f"❌ Project not found: `{project_id}`\n\n"
                "_Use `/vineyard list` to see available projects._"
            )
            return

        project_name = project.get("name", "Unnamed Project")
        project_url = project.get("url", f"https://linear.app/project/{project_id}")
        project_slug = _generate_slug(project_name)

        respond(
            text=f"🏭 *Factory starting for {project_name}*\n"
            "_This will take a few minutes. I'll post updates as each phase completes._"
        )

        # Create handoff with actual project details
        handoff = FactoryHandoff(
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
                one_liner=project.get("description", f"Building {project_name}") or f"Building {project_name}",
                detailed_description=project.get("description", "") or f"Factory build for {project_name}",
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

        # Create factory run
        state = create_factory_run(handoff)

        # Create opportunity Slack channels
        slack_channels = create_opportunity_channels(
            opportunity_slug=handoff.opportunity.slug,
            opportunity_name=handoff.opportunity.name,
        )
        state.slack_channels = slack_channels
        save_state(state)

        # Post initial message to main channel if created
        if "main" in slack_channels:
            shared_app.client.chat_postMessage(
                channel=slack_channels["main"],
                text=f"🏭 *Factory run started for {handoff.opportunity.name}*\n\n"
                f"📋 <{handoff.linear_project_url}|View in Linear>\n\n"
                f"_Automated updates will be posted to #{handoff.opportunity.slug}-alerts_",
            )

        # Use alerts channel for notifications (fall back to command channel)
        notification_channel = slack_channels.get("alerts", channel_id)

        # Run factory with notification channel for checkpoint messages
        result = run_factory(state, notification_channel)

        # Post final status
        if result.completed_at:
            shared_app.client.chat_postMessage(
                channel=notification_channel,
                text="✅ *Factory run complete!*\n\n"
                f"All phases finished successfully.\n"
                f"Linear project: {result.handoff.linear_project_url}",
            )
        elif result.phase_statuses.get(result.current_phase.value) == "awaiting_approval":
            send_checkpoint_request(notification_channel, result)
        else:
            shared_app.client.chat_postMessage(
                channel=notification_channel,
                text=f"⚠️ Factory paused at *{result.current_phase.value}*\n"
                f"Check Linear for details.",
            )

    except Exception as e:
        logger.exception("Factory failed to start")
        shared_app.client.chat_postMessage(
            channel=channel_id,
            text=f"❌ Factory failed to start: {str(e)}",
        )


def main():
    """Start the unified Vineyard Bot."""
    parser = argparse.ArgumentParser(description="Vineyard Bot")
    parser.add_argument(
        "--mode",
        choices=["all", "slack", "api"],
        default="all",
        help="Which services to run (default: all)",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Vineyard Bot - Unified Research Agent + Factory")
    logger.info("=" * 60)

    try:
        # Get settings (uses factory's config)
        settings = get_factory_settings()

        if args.mode == "api":
            logger.info("Running in API-only mode")
            start_api_server(settings)
            return

        # Create shared Slack app
        app = create_shared_app(settings)

        # Register unified command handler FIRST (handles /vineyard routing)
        register_unified_command_handler(app)

        # Register interaction handlers from both systems
        # (these use unique action IDs so they won't conflict)
        register_research_agent_handlers(app, settings)
        register_factory_handlers(app, settings)

        # Log total listeners
        total_listeners = len(app._listeners) if hasattr(app, '_listeners') else 0
        logger.info(f"Total listeners registered: {total_listeners}")

        if args.mode == "all":
            logger.info("Starting API server in background...")
            api_thread = threading.Thread(
                target=start_api_server,
                args=(settings,),
                daemon=True
            )
            api_thread.start()

        logger.info("Starting Slack bot in Socket Mode...")
        logger.info("Available commands:")
        logger.info("  /vineyard new        - Start research cycle")
        logger.info("  /vineyard build [id] - Start factory for project")
        logger.info("  /vineyard help       - Show help")
        logger.info("Press Ctrl+C to stop")

        # Start Socket Mode (blocking)
        handler = SocketModeHandler(app, settings.slack_app_token)
        handler.start()

    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
