"""CLI surface tests via Typer's CliRunner — no real LLM/network calls."""

import pytest
from typer.testing import CliRunner

from vineyard.cli import app
from vineyard.models import (
    Handoff,
    PhaseStatus,
    PRDInput,
    RunState,
)
from vineyard.models.handoff import BuildPreferences
from vineyard.storage import RunStore


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def saved_run(tmp_path):
    """Create a run in the local SQLite store and return its id + product."""
    store = RunStore()
    handoff = Handoff(
        handoff_id="h1",
        prd_input=PRDInput(name="Bandung", slug="bandung", prd_text="..."),
        build_preferences=BuildPreferences(stack="nextjs"),
    )
    state = RunState(
        run_id="11111111-2222-3333-4444-555555555555",
        handoff=handoff,
        output_dir=tmp_path / "output",
    )
    state.output_dir.mkdir(parents=True, exist_ok=True)
    state.phase_statuses["prd_analysis"] = PhaseStatus.COMPLETED
    state.cost_usd = 0.1234
    store.save(state)
    return state


# ----------------------------------------------------------- top-level commands


def test_root_help(runner):
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "vineyard" in result.stdout.lower()


def test_stacks_lists_every_registered_stack(runner):
    result = runner.invoke(app, ["stacks"])
    assert result.exit_code == 0
    for name in ("nextjs", "rails", "fastapi", "django", "backend", "cli", "tui"):
        assert name in result.stdout


# ----------------------------------------------------------------- list command


def test_list_empty(runner):
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No runs" in result.stdout


def test_list_shows_saved_run(runner, saved_run):
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "Bandung" in result.stdout
    assert "nextjs" in result.stdout


# ---------------------------------------------------------------- delete command


def test_delete_resolves_short_prefix_with_yes(runner, saved_run):
    short_id = saved_run.run_id[:8]
    result = runner.invoke(app, ["delete", short_id, "--yes"])
    assert result.exit_code == 0
    assert "Deleted" in result.stdout
    # Confirm the row is gone
    assert RunStore().load(saved_run.run_id) is None


def test_delete_unknown_run_exits_nonzero(runner):
    result = runner.invoke(app, ["delete", "nope", "--yes"])
    assert result.exit_code == 1
    assert "No run found" in result.stdout


def test_delete_ambiguous_prefix_exits_nonzero(runner, saved_run, tmp_path):
    # Add a second run with a colliding prefix
    second = RunState(
        run_id=saved_run.run_id[:8] + "-different-tail",
        handoff=saved_run.handoff,
        output_dir=tmp_path / "output2",
    )
    second.output_dir.mkdir(parents=True, exist_ok=True)
    RunStore().save(second)
    result = runner.invoke(app, ["delete", saved_run.run_id[:8], "--yes"])
    assert result.exit_code == 1
    assert "Ambiguous" in result.stdout


# ------------------------------------------------------------------ open-output


def test_open_output_prints_path(runner, saved_run):
    result = runner.invoke(app, ["open-output", saved_run.run_id])
    assert result.exit_code == 0
    # Rich may wrap long paths across lines; strip whitespace before comparing
    assert str(saved_run.output_dir) in result.stdout.replace("\n", "")


def test_open_output_unknown_run(runner):
    result = runner.invoke(app, ["open-output", "missing-id"])
    assert result.exit_code == 1


# ---------------------------------------------------------------- config command


def test_config_shows_empty_when_no_file(runner):
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "(no config file yet)" in result.stdout


def test_config_set_round_trips(runner, tmp_path):
    set_result = runner.invoke(app, ["config", "logfire-token", "pylf_test"])
    assert set_result.exit_code == 0
    assert "Set VINEYARD_LOGFIRE_TOKEN" in set_result.stdout

    show_result = runner.invoke(app, ["config"])
    assert show_result.exit_code == 0
    assert "VINEYARD_LOGFIRE_TOKEN" in show_result.stdout
    assert "pylf_test" in show_result.stdout


def test_config_set_replaces_existing_value(runner):
    runner.invoke(app, ["config", "logfire-token", "first"])
    runner.invoke(app, ["config", "logfire-token", "second"])
    show = runner.invoke(app, ["config"])
    assert "first" not in show.stdout
    assert "second" in show.stdout


def test_config_set_without_value_errors(runner):
    result = runner.invoke(app, ["config", "logfire-token"])
    assert result.exit_code == 1
    assert "Provide a value" in result.stdout


# -------------------------------------------------------------- cost (no token)


def test_cost_without_read_token_exits_nonzero(runner):
    result = runner.invoke(app, ["cost", "anything"])
    assert result.exit_code == 1
    assert "VINEYARD_LOGFIRE_READ_TOKEN" in result.stdout
