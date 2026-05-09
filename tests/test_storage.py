"""SQLite store round-trips."""

from pathlib import Path

from vineyard.models import (
    BuildPreferences,
    Handoff,
    Phase,
    PhaseStatus,
    PRDInput,
    RunState,
)


def test_save_load_round_trip(store, tmp_path: Path):
    handoff = Handoff(
        handoff_id="h1",
        prd_input=PRDInput(name="Bandung", slug="bandung", prd_text="..."),
        build_preferences=BuildPreferences(stack="fastapi"),
    )
    state = RunState(run_id="r-test", handoff=handoff, output_dir=tmp_path)
    state.update_phase_status(Phase.PRD_ANALYSIS, PhaseStatus.IN_PROGRESS)
    store.save(state)

    revived = store.load("r-test")
    assert revived is not None
    assert revived.handoff.prd_input.name == "Bandung"
    assert revived.handoff.build_preferences.stack == "fastapi"
    assert revived.phase_statuses["prd_analysis"] == PhaseStatus.IN_PROGRESS


def test_list_filters_by_status(store, tmp_path: Path):
    for i, status in enumerate([PhaseStatus.COMPLETED, PhaseStatus.FAILED, PhaseStatus.FAILED]):
        handoff = Handoff(
            handoff_id=f"h{i}",
            prd_input=PRDInput(name=f"p{i}", slug=f"p-{i}", prd_text="..."),
            build_preferences=BuildPreferences(stack="nextjs"),
        )
        state = RunState(run_id=f"r{i}", handoff=handoff, output_dir=tmp_path)
        state.update_phase_status(Phase.PRD_ANALYSIS, status)
        store.save(state)

    failed = store.list(status_filter=PhaseStatus.FAILED.value)
    assert len(failed) == 2
