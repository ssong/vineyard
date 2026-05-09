"""Prompt-builder tests — pure functions, no LLM calls."""

from pathlib import Path

import pytest

from vineyard.agents.design import build_design_prompt
from vineyard.agents.qa import build_qa_prompt
from vineyard.agents.spec import build_spec_prompt
from vineyard.build.executor import BuildContext
from vineyard.build.prompts import compose_user_prompt
from vineyard.models import (
    APIEndpoint,
    BuildOutput,
    ClarificationQA,
    DesignOutput,
    EngineeringTask,
    FeatureSpec,
    GeneratedFile,
    PRDAnalysisOutput,
    RunState,
    SpecOutput,
    UserFlow,
    ValidationOutput,
    ValidationStep,
)
from vineyard.models.handoff import BuildPreferences, Handoff, PRDInput
from vineyard.stacks import registry


@pytest.fixture
def state(tmp_path):
    return RunState(
        run_id="r1",
        output_dir=tmp_path,
        handoff=Handoff(
            handoff_id="h1",
            prd_input=PRDInput(name="X", slug="x", prd_text="..."),
            build_preferences=BuildPreferences(stack="nextjs"),
        ),
    )


@pytest.fixture
def prd():
    return PRDAnalysisOutput(
        product_name="X",
        product_summary="one para",
        core_problem="solve thing",
        target_users=["devs", "PMs"],
        enriched_prd_markdown="# Long PRD",
        identified_gaps=["gap A"],
        clarification_qa=[
            ClarificationQA(question="Auth?", answer="OAuth"),
            ClarificationQA(question="DB?"),  # default unanswered
        ],
    )


@pytest.fixture
def design():
    return DesignOutput(
        prd_markdown="## Polished",
        features=[
            FeatureSpec(
                name="F1", description="d", priority="P0",
                user_stories=["As X, I want Y"],
                acceptance_criteria=["does Y"],
                technical_notes="note",
            ),
        ],
        user_flows=[UserFlow(name="signup", steps=["click", "enter", "submit"])],
        clarification_qa=[ClarificationQA(question="Theme?", answer="dark")],
    )


@pytest.fixture
def spec():
    return SpecOutput(
        technical_spec_markdown="# Spec md",
        api_endpoints=[APIEndpoint(method="GET", path="/x", description="get x")],
        task_breakdown=[EngineeringTask(title="t", description="desc", story_points=2)],
    )


# ---------------------------------------------------------------- design prompt


def test_design_prompt_includes_prd_and_answered_clarifications(prd):
    out = build_design_prompt(prd)
    assert "X" in out  # product name
    assert "# Long PRD" in out
    assert "USER ANSWERS TO PRIOR CLARIFICATIONS" in out
    assert "Auth?" in out and "OAuth" in out
    # The unanswered one should NOT appear
    assert "DB?" not in out


def test_design_prompt_synthesizes_when_enriched_empty():
    p = PRDAnalysisOutput(
        product_name="Y",
        product_summary="sum",
        core_problem="prob",
        target_users=["u"],
        enriched_prd_markdown="",  # <- the failure mode this guards
    )
    out = build_design_prompt(p)
    # _synthesize_prd kicks in
    assert "# Y" in out and "## Problem" in out and "prob" in out


# ------------------------------------------------------------------ spec prompt


def test_spec_prompt_includes_prd_and_design_clarifications(prd, design):
    out = build_spec_prompt(design, prd)
    assert "PRODUCT SUMMARY" in out and "one para" in out
    assert "ENRICHED PRD" in out and "# Long PRD" in out
    assert "DESIGN PRD" in out and "## Polished" in out
    assert "From prd_analysis" in out and "OAuth" in out
    assert "From design" in out and "Theme?" in out and "dark" in out


def test_spec_prompt_works_without_prd(design):
    out = build_spec_prompt(design)
    assert "DESIGN PRD" in out
    assert "PRODUCT SUMMARY" not in out  # PRD section not present


# -------------------------------------------------------------------- qa prompt


def test_qa_prompt_lists_files_and_grader(spec):
    build = BuildOutput(
        files=[GeneratedFile(path="src/app.tsx", language="typescript")],
        summary="built it",
        grader_result="satisfied",
        grader_explanation="looks good",
    )
    out = build_qa_prompt(spec, build)
    assert "src/app.tsx" in out
    assert "1 total" in out
    assert "satisfied" in out
    assert "looks good" in out
    assert "# Spec md" in out


# ------------------------------------------------------------ build user prompt


def test_compose_user_prompt_basic(state, prd, design, spec):
    ctx = BuildContext(
        state=state,
        profile=registry.get("nextjs"),
        spec=spec,
        prd=prd,
        design=design,
    )
    out = compose_user_prompt(ctx)
    assert "X" in out  # product name
    assert "PRODUCT SUMMARY" in out and "one para" in out
    assert "ENRICHED PRD" in out
    assert "FEATURES" in out and "[P0] F1" in out
    assert "USER FLOWS" in out and "signup" in out
    assert "API ENDPOINTS" in out and "GET /x" in out
    assert "ENGINEERING TASKS" in out
    assert "TECHNICAL SPEC" in out and "# Spec md" in out
    # No fix-mode block when prior_build is None
    assert "FIX MODE" not in out


def test_compose_user_prompt_fix_mode(state, prd, design, spec):
    prior = BuildOutput(
        files=[
            GeneratedFile(path="src/app.tsx", language="typescript"),
            GeneratedFile(path="lib/auth.ts", language="typescript"),
        ],
    )
    err = ValidationOutput(
        backend="docker",
        success=False,
        failed_step_index=1,
        steps=[
            ValidationStep(command="pnpm install", exit_code=0),
            ValidationStep(
                command="tsc --noEmit",
                exit_code=1,
                stderr_tail="src/app.tsx(14,5): error TS2322",
            ),
        ],
    )
    ctx = BuildContext(
        state=state,
        profile=registry.get("nextjs"),
        spec=spec,
        prd=prd,
        design=design,
        prior_build=prior,
        validation_errors=err,
        attempt=2,
    )
    out = compose_user_prompt(ctx)
    assert "FIX MODE — Attempt 2" in out
    assert "src/app.tsx" in out and "lib/auth.ts" in out
    assert "tsc --noEmit" in out and "TS2322" in out
    assert "Surgical edits only" in out


def test_compose_user_prompt_no_fix_mode_without_validation_errors(state, prd, design, spec):
    prior = BuildOutput(files=[GeneratedFile(path="x.py")])
    ctx = BuildContext(
        state=state, profile=registry.get("nextjs"), spec=spec,
        prd=prd, design=design,
        prior_build=prior, validation_errors=None, attempt=2,
    )
    # prior_build alone shouldn't trigger fix mode
    assert "FIX MODE" not in compose_user_prompt(ctx)


def test_compose_user_prompt_path_is_reasonable(state, prd, design, spec):
    """build_dir property + on_event helper are exercised on attribute access."""
    ctx = BuildContext(
        state=state, profile=registry.get("nextjs"), spec=spec,
        prd=prd, design=design,
    )
    assert ctx.build_dir == Path(state.output_dir) / "build"
