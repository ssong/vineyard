"""Slack notifications for factory progress."""

import logging
from typing import Optional

from src.models import FactoryState, Phase, PhaseStatus
from src.slack.app import app
from src.utils import truncate_text, SlackLimits

logger = logging.getLogger(__name__)


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
    """Send checkpoint approval request."""
    phase = state.current_phase

    try:
        app.client.chat_postMessage(
            channel=channel_id,
            text=f"⏸️ *Checkpoint: {phase.value.replace('_', ' ').title()}*\n\n"
            f"Factory is waiting for approval to continue.\n"
            f"Review the outputs in Linear, then click below to proceed.",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"⏸️ *Checkpoint: {phase.value.replace('_', ' ').title()}*\n\n"
                        f"Factory is waiting for approval to continue.\n"
                        f"📋 <{state.handoff.linear_project_url}|View in Linear>",
                    },
                },
                {"type": "divider"},
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ Approve & Continue"},
                            "style": "primary",
                            "value": f"{state.execution_id}:{phase.value}",
                            "action_id": "approve_checkpoint",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "❌ Stop Factory"},
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
