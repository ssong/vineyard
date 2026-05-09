"""Pure-function helpers in orchestrator.runner — no LLM calls."""

import pytest

from vineyard.models import (
    BuildOutput,
    ClarificationQA,
    GeneratedFile,
    Phase,
    PhaseStatus,
    PRDAnalysisOutput,
    RunState,
)
from vineyard.models.handoff import BuildPreferences, Handoff, PRDInput
from vineyard.models.state import PHASE_ORDER
from vineyard.orchestrator.runner import (
    _load_build_output,
    _next_phase,
    _requires_approval,
    _unanswered_clarifications,
)


@pytest.fixture
def state(tmp_path):
    return RunState(
        run_id="r",
        output_dir=tmp_path,
        handoff=Handoff(
            handoff_id="h",
            prd_input=PRDInput(name="X", slug="x", prd_text=""),
            build_preferences=BuildPreferences(stack="nextjs"),
        ),
    )


# -------------------------------------------- _unanswered_clarifications


def test_unanswered_when_no_qa_field():
    out = BuildOutput()
    assert _unanswered_clarifications(out) == []


def test_unanswered_filters_out_real_answers():
    p = PRDAnalysisOutput(
        product_name="X",
        clarification_qa=[
            ClarificationQA(question="A?", answer="real answer"),
            ClarificationQA(question="B?"),  # default "(unanswered)"
            ClarificationQA(question="C?", answer=""),  # explicitly empty
            ClarificationQA(question="D?", answer="(unanswered)"),
            ClarificationQA(question="E?", answer="   "),  # whitespace
        ],
    )
    unanswered = _unanswered_clarifications(p)
    assert [q.question for q in unanswered] == ["B?", "C?", "D?", "E?"]


# -------------------------------------------- _load_build_output (shape sniff)


def test_load_build_output_handles_bare_model(state):
    bo = BuildOutput(files=[GeneratedFile(path="a.py")])
    state.phase_outputs[Phase.BUILD.value] = bo
    assert _load_build_output(state) is bo


def test_load_build_output_handles_dict_with_build_key(state):
    bo = BuildOutput(files=[GeneratedFile(path="a.py")])
    state.phase_outputs[Phase.BUILD.value] = {"build": bo, "qa": None}
    loaded = _load_build_output(state)
    assert isinstance(loaded, BuildOutput)
    assert loaded.files[0].path == "a.py"


def test_load_build_output_handles_json_roundtrip_dict(state):
    state.phase_outputs[Phase.BUILD.value] = {
        "build": {"files": [{"path": "b.py", "language": "python"}], "summary": "ok"},
        "qa": None,
    }
    loaded = _load_build_output(state)
    assert isinstance(loaded, BuildOutput)
    assert loaded.files[0].path == "b.py"
    assert loaded.summary == "ok"


def test_load_build_output_handles_bare_dict(state):
    """When the BUILD output is a bare BuildOutput dict (mid-retry-loop +
    JSON roundtrip), there's no 'build' key — fall back to validating the
    dict itself as a BuildOutput."""
    state.phase_outputs[Phase.BUILD.value] = {
        "files": [{"path": "c.py"}], "summary": "x",
    }
    loaded = _load_build_output(state)
    assert isinstance(loaded, BuildOutput)
    assert loaded.files[0].path == "c.py"


def test_load_build_output_returns_none_when_missing(state):
    assert _load_build_output(state) is None


# ---------------------------------------------- _next_phase


def test_next_phase_iterates_through_order():
    expected = [
        (Phase.PRD_ANALYSIS, Phase.DESIGN),
        (Phase.DESIGN, Phase.SPEC),
        (Phase.SPEC, Phase.BUILD),
        (Phase.BUILD, Phase.VALIDATE),
        (Phase.VALIDATE, None),
    ]
    for current, expected_next in expected:
        assert _next_phase(current) == expected_next


def test_phase_order_matches_pipeline():
    assert PHASE_ORDER == [
        Phase.PRD_ANALYSIS,
        Phase.DESIGN,
        Phase.SPEC,
        Phase.BUILD,
        Phase.VALIDATE,
    ]


# ---------------------------------------------- _requires_approval


def test_requires_approval_uses_handoff_checkpoints(state):
    state.handoff.approval_checkpoints = ["design", "build"]
    assert _requires_approval(state, Phase.DESIGN) is True
    assert _requires_approval(state, Phase.BUILD) is True
    assert _requires_approval(state, Phase.SPEC) is False


def test_requires_approval_skips_already_cleared(state):
    state.handoff.approval_checkpoints = ["design"]
    state.checkpoints_cleared.append("design")
    assert _requires_approval(state, Phase.DESIGN) is False


def test_requires_approval_handles_squashed_phase_names(state):
    """Approval checkpoints accept 'prdanalysis' as well as 'prd_analysis'
    (lenient form for user-typed CLI configs)."""
    state.handoff.approval_checkpoints = ["prdanalysis"]
    assert _requires_approval(state, Phase.PRD_ANALYSIS) is True


# ---------------------------------------------- PhaseStatus enum coverage


def test_phase_status_includes_clarification():
    assert PhaseStatus.AWAITING_CLARIFICATION.value == "awaiting_clarification"
