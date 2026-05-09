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
from vineyard.events import EventCallback, emit_event
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
    on_event: EventCallback | None = None,
) -> RunState:
    store = store or RunStore()
    profile = registry.get(state.handoff.build_preferences.stack)

    while True:
        phase = state.current_phase

        if _requires_approval(state, phase):
            state.update_phase_status(phase, PhaseStatus.AWAITING_APPROVAL)
            store.save(state)
            await _emit(on_progress, state, phase, PhaseStatus.AWAITING_APPROVAL)
            await emit_event(on_event, "phase", f"{phase.value} awaiting approval (press 'a')")
            return state

        try:
            state.update_phase_status(phase, PhaseStatus.IN_PROGRESS)
            store.save(state)
            await _emit(on_progress, state, phase, PhaseStatus.IN_PROGRESS)
            await emit_event(on_event, "phase", f"{phase.value} starting…")

            with logfire.span(f"phase.{phase.value}", run_id=state.run_id):
                output = await _execute_phase(state, phase, profile, on_event)

            state.store_output(phase, output)

            unanswered = _unanswered_clarifications(output)
            if unanswered:
                state.update_phase_status(phase, PhaseStatus.AWAITING_CLARIFICATION)
                store.save(state)
                await _emit(on_progress, state, phase, PhaseStatus.AWAITING_CLARIFICATION)
                await emit_event(
                    on_event,
                    "phase",
                    f"{phase.value} has {len(unanswered)} clarifying question(s) — open the phase to answer",
                )
                return state

            state.update_phase_status(phase, PhaseStatus.COMPLETED)
            store.save(state)
            await _emit(on_progress, state, phase, PhaseStatus.COMPLETED)
            await emit_event(
                on_event, "phase", f"{phase.value} completed · cost ${state.cost_usd:.4f}"
            )

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
            await emit_event(on_event, "error", f"{phase.value} failed: {e}")
            return state

        next_phase = _next_phase(phase)
        if next_phase is None:
            state.completed_at = datetime.now(UTC)
            store.save(state)
            await emit_event(on_event, "phase", "all phases complete")
            return state

        state.current_phase = next_phase
        store.save(state)


async def resume_run(
    run_id: str,
    *,
    store: RunStore | None = None,
    on_progress: ProgressCallback | None = None,
    on_event: EventCallback | None = None,
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

    return await run_factory(state, store=store, on_progress=on_progress, on_event=on_event)


async def restart_run(
    run_id: str,
    *,
    store: RunStore | None = None,
    on_progress: ProgressCallback | None = None,
    on_event: EventCallback | None = None,
) -> RunState | None:
    """Wipe a run's phase outputs and re-run from the first phase.

    Keeps the same run_id, handoff, and output_dir on disk. Output directory
    contents are emptied so the build phase doesn't see stale generated files.
    """
    import shutil

    store = store or RunStore()
    state = store.load(run_id)
    if state is None:
        return None

    state.phase_outputs.clear()
    state.phase_statuses = {p.value: PhaseStatus.PENDING for p in PHASE_ORDER}
    state.checkpoints_cleared.clear()
    state.errors.clear()
    state.cost_usd = 0.0
    state.current_phase = PHASE_ORDER[0]
    state.completed_at = None
    state.started_at = datetime.now(UTC)
    store.save(state)

    if state.output_dir.exists():
        shutil.rmtree(state.output_dir, ignore_errors=True)
    state.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    await emit_event(on_event, "phase", "restart: state cleared, running from prd_analysis")
    return await run_factory(state, store=store, on_progress=on_progress, on_event=on_event)


async def approve_checkpoint(
    state: RunState,
    phase: Phase,
    *,
    store: RunStore | None = None,
    on_progress: ProgressCallback | None = None,
    on_event: EventCallback | None = None,
) -> RunState:
    store = store or RunStore()
    if state.phase_statuses.get(phase.value) != PhaseStatus.AWAITING_APPROVAL:
        raise ValueError(f"Phase {phase.value} is not awaiting approval")
    state.clear_checkpoint(phase.value)
    state.update_phase_status(phase, PhaseStatus.APPROVED)
    store.save(state)
    return await run_factory(state, store=store, on_progress=on_progress, on_event=on_event)


# -----------------------------------------------------------------------------
# Phase execution
# -----------------------------------------------------------------------------


async def _execute_phase(
    state: RunState,
    phase: Phase,
    profile,
    on_event: EventCallback | None,
) -> object:
    if phase == Phase.PRD_ANALYSIS:
        agent = prd_analysis_agent(profile)
        prompt = build_prd_analysis_prompt(state.handoff.prd_input)
        await emit_event(on_event, "agent", "prd_analysis: calling claude-opus-4-7…")
        result = await agent.run(prompt)
        _track_cost(state, result)
        await emit_event(on_event, "agent", "prd_analysis: done")
        return result.output

    if phase == Phase.DESIGN:
        prd: PRDAnalysisOutput = _previous(state, Phase.PRD_ANALYSIS, PRDAnalysisOutput)
        agent = design_agent(profile)
        await emit_event(on_event, "agent", "design: calling claude-opus-4-7…")
        result = await agent.run(build_design_prompt(prd))
        _track_cost(state, result)
        await emit_event(
            on_event, "agent", f"design: done · {len(result.output.features)} features"
        )
        return result.output

    if phase == Phase.SPEC:
        design: DesignOutput = _previous(state, Phase.DESIGN, DesignOutput)
        agent = spec_agent(profile)
        await emit_event(on_event, "agent", "spec: calling claude-opus-4-7…")
        result = await agent.run(build_spec_prompt(design))
        _track_cost(state, result)
        await emit_event(
            on_event,
            "agent",
            f"spec: done · {len(result.output.api_endpoints)} endpoints, "
            f"{len(result.output.task_breakdown)} tasks",
        )
        return result.output

    if phase == Phase.BUILD:
        spec: SpecOutput = _previous(state, Phase.SPEC, SpecOutput)
        executor = get_executor(state.handoff.executor)
        await emit_event(on_event, "agent", f"build: starting {state.handoff.executor} executor…")
        build_output: BuildOutput = await executor.run(
            BuildContext(state=state, profile=profile, spec=spec, on_event=on_event)
        )
        state.add_cost(build_output.cost_usd)
        await emit_event(
            on_event, "agent", f"build: wrote {len(build_output.files)} files"
        )

        qa = qa_agent(profile)
        await emit_event(on_event, "agent", "qa: validating against rubric…")
        qa_result = await qa.run(build_qa_prompt(spec, build_output))
        _track_cost(state, qa_result)
        await emit_event(
            on_event,
            "agent",
            f"qa: done · {len(qa_result.output.issues_found)} issues",
        )
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


def _unanswered_clarifications(output) -> list:
    """Return clarification_qa items still flagged as unanswered."""
    items = getattr(output, "clarification_qa", None) or []
    return [
        qa
        for qa in items
        if not getattr(qa, "answer", None)
        or qa.answer.strip() in ("", "(unanswered)")
    ]


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


__all__ = [
    "approve_checkpoint",
    "create_run",
    "restart_run",
    "resume_run",
    "run_factory",
]
