"""Phase loop. Pause-able at approval checkpoints; resume-able after failure.

No Slack, no Linear, no GitHub — purely local.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import logfire

from vineyard.agents.design import build_design_prompt, design_agent
from vineyard.agents.prd_analysis import build_prd_analysis_prompt, prd_analysis_agent
from vineyard.agents.qa import build_qa_prompt, qa_agent
from vineyard.agents.spec import build_spec_prompt, spec_agent
from vineyard.build.executor import BuildContext, get_executor
from vineyard.config import settings
from vineyard.models import (
    BuildOutput,
    DesignOutput,
    Handoff,
    Phase,
    PhaseStatus,
    PRDAnalysisOutput,
    RunState,
    SpecOutput,
)
from vineyard.models.state import PHASE_ORDER
from vineyard.stacks import registry
from vineyard.storage.db import RunStore

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[RunState, Phase, PhaseStatus], Awaitable[None] | None]


def create_run(handoff: Handoff, store: RunStore | None = None) -> RunState:
    store = store or RunStore()
    settings.ensure_dirs()
    run_id = str(uuid.uuid4())
    state = RunState(
        run_id=run_id,
        handoff=handoff,
        output_dir=settings.output_dir(run_id),
        phase_statuses={p.value: PhaseStatus.PENDING for p in PHASE_ORDER},
    )
    state.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    store.save(state)
    logger.info("Created run %s for %s", run_id, handoff.prd_input.name)
    return state


async def run_factory(
    state: RunState,
    *,
    store: RunStore | None = None,
    on_progress: ProgressCallback | None = None,
) -> RunState:
    store = store or RunStore()
    profile = registry.get(state.handoff.build_preferences.stack)

    while True:
        phase = state.current_phase

        if _requires_approval(state, phase):
            state.update_phase_status(phase, PhaseStatus.AWAITING_APPROVAL)
            store.save(state)
            await _emit(on_progress, state, phase, PhaseStatus.AWAITING_APPROVAL)
            return state

        try:
            state.update_phase_status(phase, PhaseStatus.IN_PROGRESS)
            store.save(state)
            await _emit(on_progress, state, phase, PhaseStatus.IN_PROGRESS)

            with logfire.span(f"phase.{phase.value}", run_id=state.run_id):
                output = await _execute_phase(state, phase, profile)

            state.store_output(phase, output)
            state.update_phase_status(phase, PhaseStatus.COMPLETED)
            store.save(state)
            await _emit(on_progress, state, phase, PhaseStatus.COMPLETED)

        except Exception as e:
            logger.exception("Phase %s failed", phase.value)
            state.update_phase_status(phase, PhaseStatus.FAILED)
            state.errors.append({
                "phase": phase.value,
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat(),
            })
            store.save(state)
            await _emit(on_progress, state, phase, PhaseStatus.FAILED)
            return state

        next_phase = _next_phase(phase)
        if next_phase is None:
            state.completed_at = datetime.now(UTC)
            store.save(state)
            return state

        state.current_phase = next_phase
        store.save(state)


async def resume_run(
    run_id: str,
    *,
    store: RunStore | None = None,
    on_progress: ProgressCallback | None = None,
) -> RunState | None:
    store = store or RunStore()
    state = store.load(run_id)
    if state is None:
        return None

    current_status = state.phase_statuses.get(state.current_phase.value)
    if current_status == PhaseStatus.FAILED:
        state.update_phase_status(state.current_phase, PhaseStatus.PENDING)
        store.save(state)
    elif current_status == PhaseStatus.COMPLETED:
        nxt = _next_phase(state.current_phase)
        if nxt is None:
            return state
        state.current_phase = nxt
        store.save(state)

    return await run_factory(state, store=store, on_progress=on_progress)


async def approve_checkpoint(
    state: RunState,
    phase: Phase,
    *,
    store: RunStore | None = None,
    on_progress: ProgressCallback | None = None,
) -> RunState:
    store = store or RunStore()
    if state.phase_statuses.get(phase.value) != PhaseStatus.AWAITING_APPROVAL:
        raise ValueError(f"Phase {phase.value} is not awaiting approval")
    state.clear_checkpoint(phase.value)
    state.update_phase_status(phase, PhaseStatus.APPROVED)
    store.save(state)
    return await run_factory(state, store=store, on_progress=on_progress)


# -----------------------------------------------------------------------------
# Phase execution
# -----------------------------------------------------------------------------


async def _execute_phase(state: RunState, phase: Phase, profile) -> object:
    if phase == Phase.PRD_ANALYSIS:
        agent = prd_analysis_agent(profile)
        prompt = build_prd_analysis_prompt(state.handoff.prd_input)
        result = await agent.run(prompt)
        _track_cost(state, result)
        return result.output

    if phase == Phase.DESIGN:
        prd: PRDAnalysisOutput = _previous(state, Phase.PRD_ANALYSIS, PRDAnalysisOutput)
        agent = design_agent(profile)
        result = await agent.run(build_design_prompt(prd))
        _track_cost(state, result)
        return result.output

    if phase == Phase.SPEC:
        design: DesignOutput = _previous(state, Phase.DESIGN, DesignOutput)
        agent = spec_agent(profile)
        result = await agent.run(build_spec_prompt(design))
        _track_cost(state, result)
        return result.output

    if phase == Phase.BUILD:
        spec: SpecOutput = _previous(state, Phase.SPEC, SpecOutput)
        executor = get_executor(state.handoff.executor)
        build_output: BuildOutput = await executor.run(
            BuildContext(state=state, profile=profile, spec=spec)
        )
        state.add_cost(build_output.cost_usd)
        qa = qa_agent(profile)
        qa_result = await qa.run(build_qa_prompt(spec, build_output))
        _track_cost(state, qa_result)
        return {"build": build_output, "qa": qa_result.output}

    raise ValueError(f"Unknown phase: {phase}")


def _previous(state: RunState, phase: Phase, model_cls):
    raw = state.phase_outputs.get(phase.value)
    if raw is None:
        raise RuntimeError(f"No output for {phase.value} — cannot proceed")
    if isinstance(raw, model_cls):
        return raw
    if isinstance(raw, dict):
        return model_cls.model_validate(raw)
    raise TypeError(f"Unexpected output type for {phase.value}: {type(raw)}")


def _track_cost(state: RunState, result) -> None:
    usage = getattr(result, "usage", lambda: None)()
    if usage is None:
        return
    cost = getattr(usage, "total_cost", None) or getattr(usage, "request_cost", None)
    if cost:
        state.add_cost(float(cost))


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _requires_approval(state: RunState, phase: Phase) -> bool:
    if phase.value in state.checkpoints_cleared:
        return False
    needs = state.handoff.approval_checkpoints
    return any(c.lower() == phase.value.replace("_", "") or c.lower() == phase.value for c in needs)


def _next_phase(current: Phase) -> Phase | None:
    idx = PHASE_ORDER.index(current)
    if idx + 1 >= len(PHASE_ORDER):
        return None
    return PHASE_ORDER[idx + 1]


async def _emit(cb: ProgressCallback | None, state: RunState, phase: Phase, status: PhaseStatus) -> None:
    if cb is None:
        return
    result = cb(state, phase, status)
    if result is not None:
        await result


__all__ = ["approve_checkpoint", "create_run", "resume_run", "run_factory"]
