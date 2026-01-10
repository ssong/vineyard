"""Factory orchestrator - phase execution, state management, and recovery."""

import logging
import uuid
from datetime import datetime
from typing import Optional

from src.agents.engineering import CodeAgent, DevOpsAgent, SecurityAgent, TestAgent
from src.agents.gtm import GrowthAgent, LaunchAgent, MarketingAgent, SupportAgent
from src.agents.product import DesignAgent, ResearchEnrichmentAgent, SpecAgent
from src.models import FactoryHandoff, FactoryState, Phase, PhaseStatus
from src.orchestrator.persistence import (
    delete_state,
    list_states,
    load_state,
    save_state,
)

logger = logging.getLogger(__name__)

# Phase configuration
PHASE_CONFIG = {
    Phase.RESEARCH_ENRICHMENT: {
        "agent": ResearchEnrichmentAgent,
        "checkpoint": False,
    },
    Phase.DESIGN: {
        "agent": DesignAgent,
        "checkpoint": True,
    },
    Phase.SPEC: {
        "agent": SpecAgent,
        "checkpoint": False,
    },
    Phase.BUILD: {
        "agent": None,  # Composite of Code, Test, Security, DevOps
        "checkpoint": True,
    },
    Phase.LAUNCH_PREP: {
        "agent": None,  # Composite of Marketing, Launch
        "checkpoint": False,
    },
    Phase.LAUNCH: {
        "agent": LaunchAgent,
        "checkpoint": True,
    },
    Phase.GROWTH: {
        "agent": None,  # Composite of Growth, Support
        "checkpoint": False,
    },
}

# Phase order
PHASE_ORDER = [
    Phase.RESEARCH_ENRICHMENT,
    Phase.DESIGN,
    Phase.SPEC,
    Phase.BUILD,
    Phase.LAUNCH_PREP,
    Phase.LAUNCH,
    Phase.GROWTH,
]


def create_factory_run(handoff: FactoryHandoff) -> FactoryState:
    """Create a new factory execution."""
    state = FactoryState(
        execution_id=str(uuid.uuid4()),
        handoff=handoff,
        current_phase=Phase.RESEARCH_ENRICHMENT,
    )

    # Initialize phase statuses
    for phase in PHASE_ORDER:
        state.phase_statuses[phase.value] = PhaseStatus.PENDING

    save_state(state)
    logger.info(f"Created factory run: {state.execution_id}")

    return state


def run_factory(
    state: FactoryState,
    channel_id: Optional[str] = None,
) -> FactoryState:
    """
    Execute the factory pipeline.

    Args:
        state: Current factory state
        channel_id: Slack channel for notifications (optional)

    Returns when complete, at a checkpoint, or on failure.
    """
    logger.info(f"Starting factory run: {state.execution_id}")

    while True:
        current_phase = state.current_phase

        # Check if we need approval for this phase
        if _requires_approval(state, current_phase):
            state.update_phase_status(current_phase, PhaseStatus.AWAITING_APPROVAL)
            save_state(state)
            logger.info(f"Phase {current_phase.value} awaiting approval")
            
            # Send Slack notification
            if channel_id:
                _notify_checkpoint(channel_id, state)
            
            return state

        # Execute current phase
        try:
            state.update_phase_status(current_phase, PhaseStatus.IN_PROGRESS)
            save_state(state)

            output = _execute_phase(state, current_phase)

            state.store_output(current_phase, output)
            state.update_phase_status(current_phase, PhaseStatus.COMPLETED)
            save_state(state)

            logger.info(f"Phase {current_phase.value} completed")
            
            # Send progress notification
            if channel_id:
                _notify_phase_complete(channel_id, state, current_phase)

        except Exception as e:
            logger.exception(f"Phase {current_phase.value} failed")
            state.update_phase_status(current_phase, PhaseStatus.FAILED)
            state.errors.append({
                "phase": current_phase.value,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            })
            save_state(state)
            
            # Create Linear error issue
            _create_linear_error(state, current_phase, str(e))
            
            # Send failure notification with resume option
            if channel_id:
                _notify_failure(channel_id, state, str(e))
            
            return state

        # Move to next phase
        next_phase = _get_next_phase(current_phase)

        if next_phase is None:
            state.completed_at = datetime.utcnow()
            save_state(state)
            logger.info(f"Factory run complete: {state.execution_id}")
            
            # Send completion notification
            if channel_id:
                _notify_complete(channel_id, state)
            
            return state

        state.current_phase = next_phase
        save_state(state)


def resume_factory(
    execution_id: str,
    channel_id: Optional[str] = None,
) -> Optional[FactoryState]:
    """
    Resume a failed or stopped factory run.

    Args:
        execution_id: The execution ID to resume
        channel_id: Slack channel for notifications

    Returns:
        Updated state, or None if execution not found
    """
    state = load_state(execution_id)
    
    if not state:
        logger.error(f"No state found for execution: {execution_id}")
        return None
    
    current_status = state.phase_statuses.get(state.current_phase.value)
    
    if current_status == PhaseStatus.FAILED:
        # Reset failed phase to pending and retry
        logger.info(f"Resuming failed execution {execution_id} from {state.current_phase.value}")
        state.update_phase_status(state.current_phase, PhaseStatus.PENDING)
        save_state(state)
        return run_factory(state, channel_id)
    
    elif current_status == PhaseStatus.AWAITING_APPROVAL:
        logger.info(f"Execution {execution_id} is awaiting approval, not resuming")
        return state
    
    elif current_status == PhaseStatus.COMPLETED:
        # Move to next phase if current is complete
        next_phase = _get_next_phase(state.current_phase)
        if next_phase:
            state.current_phase = next_phase
            save_state(state)
            return run_factory(state, channel_id)
        else:
            logger.info(f"Execution {execution_id} is already complete")
            return state
    
    else:
        # Continue from current state
        return run_factory(state, channel_id)


def approve_checkpoint(
    state: FactoryState,
    phase: Phase,
    channel_id: Optional[str] = None,
) -> FactoryState:
    """Approve a checkpoint and continue execution."""
    if state.phase_statuses.get(phase.value) != PhaseStatus.AWAITING_APPROVAL:
        raise ValueError(f"Phase {phase.value} is not awaiting approval")

    state.clear_checkpoint(phase.value)
    state.update_phase_status(phase, PhaseStatus.APPROVED)
    save_state(state)

    logger.info(f"Checkpoint {phase.value} approved, continuing...")

    # Continue execution
    return run_factory(state, channel_id)


def get_failed_runs() -> list[dict]:
    """Get all failed factory runs that can be resumed."""
    return list_states(status_filter="failed")


def get_pending_runs() -> list[dict]:
    """Get all runs awaiting approval."""
    return list_states(status_filter="awaiting_approval")


def cleanup_old_runs(days: int = 30) -> int:
    """Delete factory runs older than specified days."""
    from datetime import timedelta
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    deleted = 0
    
    for run in list_states():
        started = datetime.fromisoformat(run["started_at"])
        if started < cutoff:
            delete_state(run["execution_id"])
            deleted += 1
    
    logger.info(f"Cleaned up {deleted} old factory runs")
    return deleted


def _requires_approval(state: FactoryState, phase: Phase) -> bool:
    """Check if phase requires human approval."""
    # Check if already approved
    if phase.value in state.checkpoints_cleared:
        return False

    # Check if phase is in approval list
    approval_checkpoints = state.handoff.approval_checkpoints
    phase_name = phase.value.replace("_", "")  # Match format like "design", "build"

    for checkpoint in approval_checkpoints:
        if checkpoint.lower() in phase_name:
            return True

    return False


def _execute_phase(state: FactoryState, phase: Phase) -> dict:
    """Execute a single phase."""
    logger.info(f"Executing phase: {phase.value}")

    if phase == Phase.BUILD:
        # Composite phase: Code → Test → Security → DevOps
        outputs = {}

        code_agent = CodeAgent()
        outputs["code"] = code_agent.run(state)
        state.store_output("build", outputs)

        test_agent = TestAgent()
        outputs["test"] = test_agent.run(state)

        security_agent = SecurityAgent()
        outputs["security"] = security_agent.run(state)

        devops_agent = DevOpsAgent()
        outputs["devops"] = devops_agent.run(state)

        return outputs

    elif phase == Phase.LAUNCH_PREP:
        # Composite: Marketing + Launch prep
        outputs = {}

        marketing_agent = MarketingAgent()
        outputs["marketing"] = marketing_agent.run(state)
        state.store_output("launch_prep", outputs)

        return outputs

    elif phase == Phase.GROWTH:
        # Composite: Growth + Support
        outputs = {}

        growth_agent = GrowthAgent()
        outputs["growth"] = growth_agent.run(state)

        support_agent = SupportAgent()
        outputs["support"] = support_agent.run(state)

        return outputs

    else:
        # Single agent phase
        config = PHASE_CONFIG.get(phase)
        if not config or not config["agent"]:
            return {}

        agent = config["agent"]()
        return agent.run(state)


def _get_next_phase(current: Phase) -> Optional[Phase]:
    """Get the next phase in the pipeline."""
    try:
        current_idx = PHASE_ORDER.index(current)
        if current_idx + 1 < len(PHASE_ORDER):
            return PHASE_ORDER[current_idx + 1]
    except ValueError:
        pass
    return None


# Notification helpers
def _notify_checkpoint(channel_id: str, state: FactoryState):
    """Send checkpoint approval request."""
    try:
        from src.slack.notifications import send_checkpoint_request
        send_checkpoint_request(channel_id, state)
    except Exception as e:
        logger.error(f"Failed to send checkpoint notification: {e}")


def _notify_phase_complete(channel_id: str, state: FactoryState, phase: Phase):
    """Send phase completion notification."""
    try:
        from src.slack.notifications import send_phase_update
        send_phase_update(channel_id, state, phase)
    except Exception as e:
        logger.error(f"Failed to send phase notification: {e}")


def _notify_failure(channel_id: str, state: FactoryState, error: str):
    """Send failure notification with resume option."""
    try:
        from src.slack.app import app
        
        app.client.chat_postMessage(
            channel=channel_id,
            text=f"❌ Factory failed at {state.current_phase.value}",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "❌ Factory Execution Failed",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Phase:*\n{state.current_phase.value.replace('_', ' ').title()}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Product:*\n{state.handoff.opportunity.name}",
                        },
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Error:*\n```{error[:500]}```",
                    },
                },
                {"type": "divider"},
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "🔄 Resume Factory"},
                            "style": "primary",
                            "value": state.execution_id,
                            "action_id": "resume_factory",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "📋 View in Linear"},
                            "url": state.handoff.linear_project_url,
                            "action_id": "view_linear",
                        },
                    ],
                },
            ],
        )
    except Exception as e:
        logger.error(f"Failed to send failure notification: {e}")


def _notify_complete(channel_id: str, state: FactoryState):
    """Send completion notification."""
    try:
        from src.slack.notifications import send_factory_complete
        send_factory_complete(channel_id, state)
    except Exception as e:
        logger.error(f"Failed to send completion notification: {e}")


def _create_linear_error(state: FactoryState, phase: Phase, error: str):
    """Create a Linear issue for the error."""
    try:
        from src.tools import linear
        
        linear.create_error_issue(
            project_id=state.handoff.linear_project_id,
            phase=phase.value,
            error_message=error,
            execution_id=state.execution_id,
        )
    except Exception as e:
        logger.error(f"Failed to create Linear error issue: {e}")
