"""Slack notifications for factory progress."""

import logging
from datetime import datetime
from typing import Optional

from src.models import FactoryState, Phase, PhaseStatus
from src.slack.app import app
from src.utils import truncate_text, SlackLimits

logger = logging.getLogger(__name__)


def _get_completed_phases(state: FactoryState) -> list[Phase]:
    """Get list of phases that have been completed."""
    completed = []
    for phase in Phase:
        status = state.phase_statuses.get(phase.value)
        if status in (PhaseStatus.COMPLETED, PhaseStatus.APPROVED):
            completed.append(phase)
    return completed


def _upload_phase_pdf(channel_id: str, state: FactoryState, phase: Phase) -> Optional[str]:
    """Generate and upload PDF for a phase, returning the file permalink."""
    try:
        from src.reports.pdf import generate_phase_report_pdf

        pdf_path = generate_phase_report_pdf(state, phase)
        if not pdf_path:
            return None

        opp_name = state.handoff.opportunity.name
        phase_title = phase.value.replace("_", " ").title()

        result = app.client.files_upload_v2(
            channel=channel_id,
            file=pdf_path,
            title=f"{opp_name} - {phase_title} Report",
            initial_comment=f"*{phase_title} Phase Complete*\n\nFull output attached below.",
        )

        # Return permalink if available
        file_info = result.get("file", {})
        return file_info.get("permalink")

    except Exception as e:
        logger.warning(f"Failed to generate/upload phase PDF: {e}")
        return None


def send_phase_update(channel_id: str, state: FactoryState, phase: Phase):
    """Send phase completion notification."""
    phase_emoji = {
        Phase.RESEARCH_ENRICHMENT: "🔍",
        Phase.DESIGN: "🎨",
        Phase.SPEC: "📋",
        Phase.BUILD: "🔨",
        Phase.LAUNCH_PREP: "🚀",
        Phase.LAUNCH: "📣",
        Phase.GROWTH: "📈",
    }

    emoji = phase_emoji.get(phase, "✅")

    try:
        app.client.chat_postMessage(
            channel=channel_id,
            text=f"{emoji} *{phase.value.replace('_', ' ').title()}* phase complete!",
        )
    except Exception as e:
        logger.error(f"Failed to send phase update: {e}")


def send_checkpoint_request(channel_id: str, state: FactoryState):
    """Send checkpoint approval request with PDF of completed phase output."""
    phase = state.current_phase
    opp_name = state.handoff.opportunity.name
    phase_title = phase.value.replace("_", " ").title()

    try:
        # First, upload the PDF of the completed phase output
        _upload_phase_pdf(channel_id, state, phase)

        # Then send the approval request message
        app.client.chat_postMessage(
            channel=channel_id,
            text=f"⏸️ *Checkpoint: {phase_title} for {opp_name}*\n\n"
            f"Factory is waiting for approval to continue.\n"
            f"Review the outputs above and in Linear, then click below to proceed.",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"⏸️ Checkpoint: {phase_title}",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{opp_name}*\n\n"
                        f"Factory is waiting for approval to continue.\n"
                        f"Review the PDF report above and details in Linear.",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Current Phase:*\n{phase_title}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Project:*\n<{state.handoff.linear_project_url}|View in Linear>",
                        },
                    ],
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "_You can also approve from Linear by commenting 'approve' or 'lgtm' on the phase issue._",
                        },
                    ],
                },
                {"type": "divider"},
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ Approve & Continue", "emoji": True},
                            "style": "primary",
                            "value": f"{state.execution_id}:{phase.value}",
                            "action_id": "approve_checkpoint",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "❌ Stop Factory", "emoji": True},
                            "style": "danger",
                            "value": state.execution_id,
                            "action_id": "stop_factory",
                        },
                    ],
                },
            ],
        )
    except Exception as e:
        logger.error(f"Failed to send checkpoint request: {e}")


def send_factory_complete(channel_id: str, state: FactoryState):
    """Send factory completion notification."""
    opp = state.handoff.opportunity

    try:
        app.client.chat_postMessage(
            channel=channel_id,
            text=f"🎉 *Factory Complete: {opp.name}*",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🎉 Factory Complete: {opp.name}",
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Phases Completed:*\n7/7"},
                        {"type": "mrkdwn", "text": f"*Duration:*\n{_format_duration(state)}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"📋 <{state.handoff.linear_project_url}|View Project in Linear>",
                    },
                },
            ],
        )
    except Exception as e:
        logger.error(f"Failed to send completion notification: {e}")


def send_factory_error(channel_id: str, state: FactoryState, error: str):
    """Send factory error notification."""
    try:
        # Truncate error message to avoid Slack API limits
        truncated_error = truncate_text(error, SlackLimits.ERROR_MESSAGE)
        app.client.chat_postMessage(
            channel=channel_id,
            text=f"❌ *Factory Error*\n\n"
            f"Phase: {state.current_phase.value}\n"
            f"Error: {truncated_error}\n\n"
            f"Check Linear for details and retry.",
        )
    except Exception as e:
        logger.error(f"Failed to send error notification: {e}")


def _format_duration(state: FactoryState) -> str:
    """Format factory duration."""
    if not state.completed_at:
        return "In progress"

    duration = state.completed_at - state.started_at
    minutes = int(duration.total_seconds() / 60)

    if minutes < 60:
        return f"{minutes} minutes"
    else:
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}m"
