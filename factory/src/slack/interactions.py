"""Slack interaction handlers for factory."""

import logging

from slack_bolt import Ack

from src.models import Phase, PhaseStatus
from src.orchestrator.runner import approve_checkpoint, resume_factory
from src.orchestrator.persistence import load_state
from src.slack.app import app
from src.slack.notifications import send_factory_complete
from src.tools import linear

logger = logging.getLogger(__name__)


def _get_approver_name(body: dict) -> str:
    """Extract approver name from Slack interaction body."""
    user = body.get("user", {})
    return user.get("real_name") or user.get("name") or "Slack user"


def _sync_approval_to_linear(state, phase: Phase, approver_name: str):
    """Add a comment to Linear when checkpoint is approved via Slack."""
    try:
        phase_info = state.linear_phase_issues.get(phase.value)
        if not phase_info:
            logger.debug(f"No Linear issue for phase {phase.value}")
            return

        issue_id = phase_info.get("id")
        if not issue_id:
            return

        opp_name = state.handoff.opportunity.name
        short_id = state.execution_id[:8]

        linear.add_comment(
            issue_id,
            f"✅ **Checkpoint approved** by {approver_name} via Slack\n\n"
            f"Continuing factory execution for **{opp_name}** (`{short_id}...`)"
        )
    except Exception as e:
        logger.warning(f"Failed to sync approval to Linear: {e}")


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
        channel_id = body["channel"]["id"]
        approver_name = _get_approver_name(body)

        # Sync approval to Linear (leave comment on phase issue)
        _sync_approval_to_linear(state, phase, approver_name)

        # Approve and continue
        respond(
            text=f"✅ Checkpoint approved by {approver_name}! Continuing factory...",
            replace_original=True,
        )

        # Continue execution with channel for notifications
        result = approve_checkpoint(state, phase, channel_id)

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
        text="🛑 Factory stopped. You can resume later with the Resume button.",
        replace_original=True,
    )

    logger.info(f"Factory {execution_id} stopped by user")


@app.action("resume_factory")
def handle_resume_factory(ack: Ack, body: dict, respond):
    """Handle factory resume button click."""
    ack()

    execution_id = body["actions"][0]["value"]
    channel_id = body["channel"]["id"]

    respond(
        text="🔄 Resuming factory...",
        replace_original=True,
    )

    try:
        result = resume_factory(execution_id, channel_id)

        if not result:
            respond(
                text="⚠️ Could not find factory run. It may have expired.",
                replace_original=False,
            )
            return

        if result.completed_at:
            send_factory_complete(channel_id, result)
            respond(
                text="✅ Factory resumed and completed!",
                replace_original=False,
            )
        elif result.phase_statuses.get(result.current_phase.value) == PhaseStatus.AWAITING_APPROVAL:
            from src.slack.notifications import send_checkpoint_request
            send_checkpoint_request(channel_id, result)
        elif result.phase_statuses.get(result.current_phase.value) == PhaseStatus.FAILED:
            # Still failing, notification already sent by run_factory
            pass
        else:
            respond(
                text=f"✅ Factory resumed! Currently at: {result.current_phase.value}",
                replace_original=False,
            )

    except Exception as e:
        logger.exception("Failed to resume factory")
        respond(text=f"❌ Failed to resume: {str(e)}")


@app.action("view_linear")
def handle_view_linear(ack: Ack, body: dict, respond):
    """Handle view Linear button click (no-op, button is a link)."""
    ack()
