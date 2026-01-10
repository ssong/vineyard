"""Factory orchestrator - phase execution and state management."""

import logging
import uuid
from datetime import datetime
from typing import Optional

from src.agents.engineering import CodeAgent, DevOpsAgent, SecurityAgent, TestAgent
from src.agents.gtm import GrowthAgent, LaunchAgent, MarketingAgent, SupportAgent
from src.agents.product import DesignAgent, ResearchEnrichmentAgent, SpecAgent
from src.models import FactoryHandoff, FactoryState, Phase, PhaseStatus

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

# In-memory state storage (would be Redis/DB in production)
_factory_states: dict[str, FactoryState] = {}


def save_state(state: FactoryState):
    """Persist factory state."""
    _factory_states[state.execution_id] = state


def load_state(execution_id: str) -> Optional[FactoryState]:
    """Load factory state."""
    return _factory_states.get(execution_id)


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


def run_factory(state: FactoryState) -> FactoryState:
    """
    Execute the factory pipeline.

    Returns when complete or when a checkpoint requires approval.
    """
    logger.info(f"Starting factory run: {state.execution_id}")

    while True:
        current_phase = state.current_phase

        # Check if we need approval for this phase
        if _requires_approval(state, current_phase):
            state.update_phase_status(current_phase, PhaseStatus.AWAITING_APPROVAL)
            save_state(state)
            logger.info(f"Phase {current_phase.value} awaiting approval")
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

        except Exception as e:
            logger.exception(f"Phase {current_phase.value} failed")
            state.update_phase_status(current_phase, PhaseStatus.FAILED)
            state.errors.append({
                "phase": current_phase.value,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            })
            save_state(state)
            return state

        # Move to next phase
        next_phase = _get_next_phase(current_phase)

        if next_phase is None:
            state.completed_at = datetime.utcnow()
            save_state(state)
            logger.info(f"Factory run complete: {state.execution_id}")
            return state

        state.current_phase = next_phase
        save_state(state)


def approve_checkpoint(state: FactoryState, phase: Phase) -> FactoryState:
    """Approve a checkpoint and continue execution."""
    if state.phase_statuses.get(phase.value) != PhaseStatus.AWAITING_APPROVAL:
        raise ValueError(f"Phase {phase.value} is not awaiting approval")

    state.clear_checkpoint(phase.value)
    state.update_phase_status(phase, PhaseStatus.APPROVED)
    save_state(state)

    logger.info(f"Checkpoint {phase.value} approved, continuing...")

    # Continue execution
    return run_factory(state)


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
