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

        product_name = state.handoff.prd_input.name
        short_id = state.execution_id[:8]

        linear.add_comment(
            issue_id,
            f"✅ **Checkpoint approved** by {approver_name} via Slack\n\n"
            f"Continuing factory execution for **{product_name}** (`{short_id}...`)"
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


@app.view("prd_submission")
def handle_prd_submission(ack: Ack, body: dict, view: dict):
    """Handle PRD modal submission."""
    ack()

    try:
        import threading
        import uuid
        from datetime import datetime

        from src.models import BuildPreferences, FactoryHandoff, PRDInput
        from src.orchestrator.runner import create_factory_run, run_factory
        from src.orchestrator.persistence import save_state
        from src.slack.channels import create_opportunity_channels

        user_id = body["user"]["id"]

        # Extract values from modal
        values = view.get("state", {}).get("values", {})

        product_name = ""
        prd_text = ""
        for block_id, block_values in values.items():
            for action_id, action_data in block_values.items():
                if action_id == "product_name_input":
                    product_name = action_data.get("value", "").strip()
                elif action_id == "prd_text_input":
                    prd_text = action_data.get("value", "").strip()

        if not product_name or not prd_text:
            logger.warning("PRD submission missing product name or PRD text")
            return

        # Generate slug
        import re
        slug = product_name.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        slug = slug[:50]

        # Create PRD input
        prd_input = PRDInput(
            name=product_name,
            slug=slug,
            prd_text=prd_text,
            submitted_by=user_id,
        )

        # Create Linear project
        from src.tools.linear import create_project

        project = create_project(
            name=product_name,
            description=f"Factory build for {product_name}",
        )
        project_id = project.get("id", "")
        project_url = project.get("url", "")

        # Create handoff
        handoff = FactoryHandoff(
            handoff_id=str(uuid.uuid4()),
            triggered_at=datetime.utcnow(),
            triggered_by=user_id,
            linear_project_id=project_id,
            linear_project_url=project_url,
            prd_input=prd_input,
            build_preferences=BuildPreferences(),
            approval_checkpoints=["design", "build"],
        )

        # Create factory run
        state = create_factory_run(handoff)

        # Create Slack channels
        slack_channels = create_opportunity_channels(
            opportunity_slug=slug,
            opportunity_name=product_name,
        )
        state.slack_channels = slack_channels

        # Post initial message (becomes Q&A thread)
        main_channel = slack_channels.get("main")
        if main_channel:
            result = app.client.chat_postMessage(
                channel=main_channel,
                text=f"🏭 *Factory run started for {product_name}*\n\n"
                f"📋 <{project_url}|View in Linear>\n\n"
                f"_Analyzing your PRD..._",
            )
            # Store thread_ts for Q&A
            state.slack_qa_thread_ts = result.get("ts")

        save_state(state)

        # Run factory in background thread
        notification_channel = slack_channels.get("alerts", main_channel)

        def _run():
            run_factory(state, notification_channel)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    except Exception as e:
        logger.exception("Failed to handle PRD submission")


@app.action("qa_done")
def handle_qa_done(ack: Ack, body: dict, respond):
    """Handle Q&A done button click."""
    ack()

    thread_ts = body["actions"][0]["value"]
    channel_id = body["channel"]["id"]

    try:
        from src.slack.qa import signal_done
        signal_done(channel_id, thread_ts)

        respond(
            text="✅ Got it! Processing your answers and continuing with the analysis...",
            replace_original=False,
        )
    except Exception as e:
        logger.error(f"Failed to handle Q&A done: {e}")
        respond(text="Processing your answers...")
