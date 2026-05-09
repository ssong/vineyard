"""Orchestrator phase loop with phase agents and the build executor stubbed out."""

import pytest

from vineyard.models import (
    BuildOutput,
    DesignOutput,
    FeatureSpec,
    Handoff,
    PhaseStatus,
    PRDAnalysisOutput,
    PRDInput,
    QAOutput,
    SpecOutput,
)
from vineyard.orchestrator import create_run, run_factory
from vineyard.orchestrator import runner as runner_mod
from vineyard.stacks import registry


@pytest.mark.asyncio
async def test_phase_loop_runs_to_build(monkeypatch):
    nextjs = registry.get("nextjs")
    handoff = Handoff(
        handoff_id="h1",
        prd_input=PRDInput(name="Smoketest", slug="smoke", prd_text="A simple TODO app."),
        build_preferences=nextjs.default_preferences(),
        approval_checkpoints=[],
    )
    state = create_run(handoff)

    prd_out = PRDAnalysisOutput(
        product_name="Smoketest",
        product_summary="todo app",
        enriched_prd_markdown="# PRD",
        core_problem="users need todos",
    )
    design_out = DesignOutput(
        prd_markdown="# Design",
        features=[FeatureSpec(name="add todo", description="x", priority="P0")],
    )
    spec_out = SpecOutput(technical_spec_markdown="# Spec")
    qa_out = QAOutput(summary="all good")

    monkeypatch.setattr(runner_mod, "prd_analysis_agent", lambda p: _stub_agent(prd_out))
    monkeypatch.setattr(runner_mod, "design_agent", lambda p: _stub_agent(design_out))
    monkeypatch.setattr(runner_mod, "spec_agent", lambda p: _stub_agent(spec_out))
    monkeypatch.setattr(runner_mod, "qa_agent", lambda p: _stub_agent(qa_out))

    async def fake_executor_run(ctx):
        return BuildOutput(summary="stubbed build")

    monkeypatch.setattr(
        runner_mod,
        "get_executor",
        lambda name=None: type("E", (), {"run": staticmethod(fake_executor_run)})(),
    )

    final = await run_factory(state)
    assert final.phase_statuses["build"] == PhaseStatus.COMPLETED


def _stub_agent(output_obj):
    class _Stub:
        async def run(self, _prompt: str):
            class _R:
                output = output_obj

                def usage(self):
                    return None

            return _R()

    return _Stub()
