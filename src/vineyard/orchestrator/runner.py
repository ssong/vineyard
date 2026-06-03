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
from vineyard.llm.gateway import Role, cost_for_usage
from vineyard.models import (
    BuildOutput,
    DesignOutput,
    Handoff,
    Phase,
    PhaseStatus,
    PRDAnalysisOutput,
    QAOutput,
    RunState,
    SpecOutput,
    ValidationOutput,
)
from vineyard.models.state import PHASE_ORDER
from vineyard.stacks import registry
from vineyard.storage.db import RunStore
from vineyard.validate import ValidatorContext, get_validator

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
        _track_cost(state, result, role="plan")
        await emit_event(on_event, "agent", "prd_analysis: done")
        return result.output

    if phase == Phase.DESIGN:
        prd: PRDAnalysisOutput = _previous(state, Phase.PRD_ANALYSIS, PRDAnalysisOutput)
        agent = design_agent(profile)
        await emit_event(on_event, "agent", "design: calling claude-opus-4-7…")
        result = await agent.run(build_design_prompt(prd))
        _track_cost(state, result, role="plan")
        await emit_event(
            on_event, "agent", f"design: done · {len(result.output.features)} features"
        )
        return result.output

    if phase == Phase.SPEC:
        design: DesignOutput = _previous(state, Phase.DESIGN, DesignOutput)
        prd_for_spec: PRDAnalysisOutput = _previous(state, Phase.PRD_ANALYSIS, PRDAnalysisOutput)
        agent = spec_agent(profile)
        await emit_event(on_event, "agent", "spec: calling claude-opus-4-7…")
        result = await agent.run(build_spec_prompt(design, prd_for_spec))
        _track_cost(state, result, role="plan")
        await emit_event(
            on_event,
            "agent",
            f"spec: done · {len(result.output.api_endpoints)} endpoints, "
            f"{len(result.output.task_breakdown)} tasks",
        )
        return result.output

    if phase == Phase.BUILD:
        # First-pass build: no QA yet. QA + the validate-driven retry loop
        # both live in the VALIDATE phase below, so the build phase output
        # is just the BuildOutput. _render_build_summary already tolerates
        # both the {build, qa} dict shape (final) and a bare BuildOutput.
        spec: SpecOutput = _previous(state, Phase.SPEC, SpecOutput)
        prd_out: PRDAnalysisOutput = _previous(state, Phase.PRD_ANALYSIS, PRDAnalysisOutput)
        design_out: DesignOutput = _previous(state, Phase.DESIGN, DesignOutput)
        build_output = await _run_build(
            state, profile, spec, prd_out, design_out, on_event,
            attempt=1,
            prior_build=None,
            validation_errors=None,
        )
        return build_output

    if phase == Phase.VALIDATE:
        return await _run_validate_loop(
            state=state,
            profile=profile,
            on_event=on_event,
        )

    raise ValueError(f"Unknown phase: {phase}")


async def _run_build(
    state: RunState,
    profile,
    spec: SpecOutput,
    prd_out: PRDAnalysisOutput,
    design_out: DesignOutput,
    on_event: EventCallback | None,
    *,
    attempt: int,
    prior_build: BuildOutput | None,
    validation_errors: ValidationOutput | None,
) -> BuildOutput:
    executor = get_executor(state.handoff.executor)
    label = (
        f"build: starting {state.handoff.executor} executor…"
        if attempt == 1
        else f"build (fix attempt {attempt}): re-running {state.handoff.executor} executor…"
    )
    await emit_event(on_event, "agent", label)
    build_output: BuildOutput = await executor.run(
        BuildContext(
            state=state,
            profile=profile,
            spec=spec,
            prd=prd_out,
            design=design_out,
            on_event=on_event,
            prior_build=prior_build,
            validation_errors=validation_errors,
            attempt=attempt,
        )
    )
    state.add_cost(build_output.cost_usd)
    await emit_event(
        on_event, "agent", f"build: wrote {len(build_output.files)} files"
    )
    return build_output


async def _run_validate_loop(
    *,
    state: RunState,
    profile,
    on_event: EventCallback | None,
) -> dict:
    """Validate the generated codebase, looping back into BUILD on failure.

    Up to ``settings.validate_max_retries + 1`` total validate attempts. Between
    failures, BUILD re-runs in fix mode with the prior file list and the
    failing step's stderr/stdout in its prompt. On the first successful
    validation, QA runs once against the final build output and the result is
    bundled into the phase output.

    Raises RuntimeError when retries are exhausted (recoverable via resume).
    """
    spec: SpecOutput = _previous(state, Phase.SPEC, SpecOutput)
    prd_out: PRDAnalysisOutput = _previous(state, Phase.PRD_ANALYSIS, PRDAnalysisOutput)
    design_out: DesignOutput = _previous(state, Phase.DESIGN, DesignOutput)

    last_build = _load_build_output(state)
    if last_build is None:
        raise RuntimeError("BUILD phase has no output — cannot validate")
    max_retries = max(0, int(settings.validate_max_retries))
    cost_cap = settings.run_cost_cap_usd

    for attempt in range(1, max_retries + 2):  # 1..N+1 inclusive
        validator = get_validator()
        await emit_event(
            on_event,
            "agent",
            f"validate (attempt {attempt}/{max_retries + 1}): starting via "
            f"{type(validator).__name__}",
        )
        result: ValidationOutput = await validator.run(
            ValidatorContext(state=state, profile=profile, on_event=on_event)
        )
        passed = sum(1 for s in result.steps if s.exit_code == 0)
        total = len(result.steps)
        await emit_event(
            on_event,
            "agent",
            f"validate: {result.summary} ({passed}/{total} steps passed)",
        )

        if result.success:
            # Final successful build. Run QA once to score against the rubric —
            # UNLESS the Outcomes (managed_agents) executor already graded the
            # build against that same rubric, in which case a separate QA agent
            # pass is redundant spend. We reuse the Outcomes grader verdict.
            if state.handoff.executor == "managed_agents":
                qa_output = QAOutput(
                    summary=(
                        f"Outcomes grader: {last_build.grader_result} — "
                        f"{last_build.grader_explanation}"
                    )
                )
                await emit_event(
                    on_event,
                    "agent",
                    f"qa: using Outcomes grader verdict ({last_build.grader_result})",
                )
            else:
                qa = qa_agent(profile)
                await emit_event(on_event, "agent", "qa: validating against rubric…")
                qa_result = await qa.run(build_qa_prompt(spec, last_build))
                _track_cost(state, qa_result, role="judge")
                qa_output = qa_result.output
                await emit_event(
                    on_event,
                    "agent",
                    f"qa: done · {len(qa_output.issues_found)} issues",
                )
            # Update BUILD phase output with the final build + qa, so the
            # build card reflects the QA result the user inspects in the UI.
            state.store_output(
                Phase.BUILD,
                {"build": last_build, "qa": qa_output},
            )
            return result

        # Failure path — out of retries?
        if attempt > max_retries:
            raise RuntimeError(
                f"Validation failed after {attempt} build attempt(s): {result.summary}"
            )

        # Cost cap check — bail before paying for another build.
        if cost_cap is not None and state.cost_usd >= cost_cap:
            raise RuntimeError(
                f"Run cost cap (${cost_cap:.2f}) reached at ${state.cost_usd:.4f}; "
                f"refusing further build retries. Last validate failure: {result.summary}"
            )

        await emit_event(
            on_event,
            "phase",
            f"validation failed; retrying build (fix attempt {attempt + 1}/"
            f"{max_retries + 1}) with errors as context",
        )

        last_build = await _run_build(
            state, profile, spec, prd_out, design_out, on_event,
            attempt=attempt + 1,
            prior_build=last_build,
            validation_errors=result,
        )
        # Persist the latest build so the phase card and UI reflect it even
        # mid-loop. Phase status stays COMPLETED (we don't re-flip it).
        state.store_output(Phase.BUILD, last_build)

    # Unreachable; the loop either returns success or raises.
    raise RuntimeError("validate loop exited without returning")  # pragma: no cover


def _load_build_output(state: RunState) -> BuildOutput | None:
    """Return the most recent BuildOutput regardless of phase-output shape.

    The BUILD phase output is a bare BuildOutput mid-retry-loop and a
    ``{"build": BuildOutput, "qa": QAOutput}`` dict after validation
    succeeds. After a JSON roundtrip both shapes come back as dicts, so we
    sniff and unwrap.
    """
    raw = state.phase_outputs.get(Phase.BUILD.value)
    if raw is None:
        return None
    if isinstance(raw, BuildOutput):
        return raw
    if isinstance(raw, dict):
        candidate = raw.get("build", raw)
        if isinstance(candidate, BuildOutput):
            return candidate
        if isinstance(candidate, dict):
            return BuildOutput.model_validate(candidate)
    return None


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


def _track_cost(state: RunState, result, role: Role) -> None:
    """Compute the run cost from a Pydantic AI agent result and add it to state.

    Pydantic AI's RunUsage exposes token counts but no cost — we calculate from
    Anthropic list pricing. Falls back to any explicit cost attr if a future
    version starts surfacing one.
    """
    usage_fn = getattr(result, "usage", None)
    if not callable(usage_fn):
        return
    usage = usage_fn()
    if usage is None:
        return

    # Prefer an explicit cost field if the SDK ever starts surfacing one.
    explicit = getattr(usage, "total_cost", None) or getattr(usage, "request_cost", None)
    if explicit:
        state.add_cost(float(explicit))
        return

    cost = cost_for_usage(
        role,
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
        cache_read_tokens=getattr(usage, "cache_read_tokens", 0) or 0,
        cache_write_tokens=getattr(usage, "cache_write_tokens", 0) or 0,
    )
    if cost:
        state.add_cost(cost)


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
