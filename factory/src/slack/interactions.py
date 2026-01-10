"""Slack interaction handlers for factory."""

import logging
import re

from slack_bolt import Ack

from src.models import Phase, PhaseStatus
from src.orchestrator import approve_checkpoint, load_state, run_factory
from src.slack.app import app
from src.slack.notifications import send_factory_complete, send_factory_error

logger = logging.getLogger(__name__)


@app.action("approve_checkpoint")
def handle_approve_checkpoint(ack: Ack, body: dict, respond):
    """Handle checkpoint approval button click."""
    ack()

    action = body["actions"][0]
    value = action["value"]  # format: "execution_id:phase"

    try:
        execution_id, phase_value = value.split(":")
        state = load_state(execution_id)

        if not state:
            respond(text="⚠️ Could not find factory run. It may have expired.")
            return

        phase = Phase(phase_value)

        # Approve and continue
        respond(
            text=f"✅ Checkpoint approved! Continuing factory...",
            replace_original=True,
        )

        # Continue execution
        result = approve_checkpoint(state, phase)

        channel_id = body["channel"]["id"]

        if result.completed_at:
            send_factory_complete(channel_id, result)
        elif result.phase_statuses.get(result.current_phase.value) == PhaseStatus.AWAITING_APPROVAL:
            from src.slack.notifications import send_checkpoint_request
            send_checkpoint_request(channel_id, result)

    except Exception as e:
        logger.exception("Failed to handle checkpoint approval")
        respond(text=f"❌ Failed to continue: {str(e)}")


@app.action("stop_factory")
def handle_stop_factory(ack: Ack, body: dict, respond):
    """Handle factory stop button click."""
    ack()

    execution_id = body["actions"][0]["value"]

    respond(
        text="🛑 Factory stopped. You can resume later from Linear.",
        replace_original=True,
    )

    logger.info(f"Factory {execution_id} stopped by user")
