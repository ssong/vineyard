"""Sanity checks on Pydantic models."""

from vineyard.models import (
    APIEndpoint,
    BuildPreferences,
    DesignOutput,
    FeatureSpec,
    Handoff,
    Phase,
    PhaseStatus,
    PRDAnalysisOutput,
    PRDInput,
    RunState,
    SpecOutput,
)


def test_phase_enum_order():
    assert Phase.PRD_ANALYSIS.value == "prd_analysis"
    assert Phase.BUILD.value == "build"


def test_handoff_round_trips():
    handoff = Handoff(
        handoff_id="h1",
        prd_input=PRDInput(name="Test", slug="test", prd_text="hello"),
        build_preferences=BuildPreferences(stack="nextjs"),
    )
    serialized = handoff.model_dump_json()
    revived = Handoff.model_validate_json(serialized)
    assert revived.prd_input.name == "Test"
    assert revived.build_preferences.stack == "nextjs"


def test_run_state_tracks_status_and_cost(tmp_path):
    handoff = Handoff(
        handoff_id="h1",
        prd_input=PRDInput(name="X", slug="x", prd_text="..."),
        build_preferences=BuildPreferences(stack="rails"),
    )
    state = RunState(run_id="r1", handoff=handoff, output_dir=tmp_path)
    state.update_phase_status(Phase.PRD_ANALYSIS, PhaseStatus.COMPLETED)
    state.add_cost(0.42)
    state.add_cost(0.08)
    assert state.phase_statuses["prd_analysis"] == PhaseStatus.COMPLETED
    assert round(state.cost_usd, 2) == 0.5


def test_design_output_validates_priority():
    DesignOutput(
        prd_markdown="...",
        features=[
            FeatureSpec(name="x", description="y", priority="P0"),
        ],
    )


def test_spec_output_endpoints_constrained():
    SpecOutput(
        technical_spec_markdown="...",
        api_endpoints=[
            APIEndpoint(method="GET", path="/health", description="health"),
        ],
    )
