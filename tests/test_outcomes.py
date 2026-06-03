"""OutcomesExecutor against a fake OutcomesClient — no network."""

from types import SimpleNamespace

import pytest

from vineyard.build.executor import BuildContext
from vineyard.build.outcomes_exec import (
    OutcomesExecutor,
    _format_tool_use,
    _role_for_model,
    _to_build_output,
)
from vineyard.models import (
    BuildOutput,
    DesignOutput,
    FeatureSpec,
    GeneratedFile,
    PRDAnalysisOutput,
    RunState,
    SpecOutput,
)
from vineyard.models.handoff import BuildPreferences, Handoff, PRDInput
from vineyard.stacks import registry

# ----------------------------------------------------------------- fixtures


@pytest.fixture
def ctx(tmp_path):
    state = RunState(
        run_id="run-1234abcd",
        output_dir=tmp_path,
        handoff=Handoff(
            handoff_id="h",
            prd_input=PRDInput(name="Demo", slug="demo", prd_text="..."),
            build_preferences=BuildPreferences(stack="fastapi"),
            executor="managed_agents",
        ),
    )
    return BuildContext(
        state=state,
        profile=registry.get("fastapi"),
        spec=SpecOutput(technical_spec_markdown="# spec"),
        prd=PRDAnalysisOutput(product_name="Demo", enriched_prd_markdown="# prd"),
        design=DesignOutput(features=[FeatureSpec(name="F", description="d", priority="P0")]),
    )


def _evt(type_, **kw):
    return SimpleNamespace(type=type_, **kw)


def _text(t):
    return SimpleNamespace(text=t)


def _usage(i, o, cr=0, cw=0):
    return SimpleNamespace(
        input_tokens=i,
        output_tokens=o,
        cache_read_input_tokens=cr,
        cache_creation_input_tokens=cw,
    )


class FakeClient:
    """Records lifecycle calls and replays a scripted event stream."""

    def __init__(self, events, output_files=None, file_bytes=b"print('hi')\n"):
        self._events = events
        self._output_files = output_files or []
        self._file_bytes = file_bytes
        self.calls = []
        self.uploaded = []
        self.mounted = []
        self.deleted_session = False
        self.deleted_env = False

    async def ensure_agent(self, **kw):
        self.calls.append("ensure_agent")
        return "agt_1"

    async def ensure_environment(self, **kw):
        self.calls.append("ensure_environment")
        return "env_1"

    async def create_session(self, **kw):
        self.calls.append("create_session")
        return "ses_1"

    async def send_define_outcome(self, **kw):
        self.calls.append("send_define_outcome")
        self.define_kw = kw

    async def stream_events(self, *, session_id):
        for e in self._events:
            yield e

    async def list_output_files(self, *, session_id):
        return self._output_files

    async def download_file(self, *, file_id):
        return self._file_bytes

    async def upload_file(self, *, path):
        self.uploaded.append(path.name)
        return f"file_{path.name}"

    async def mount_file(self, *, session_id, file_id, mount_path):
        self.mounted.append(mount_path)

    async def delete_session(self, *, session_id):
        self.deleted_session = True

    async def delete_environment(self, *, environment_id):
        self.deleted_env = True


# ----------------------------------------------------------------- pure helpers


def test_role_for_model():
    assert _role_for_model("claude-opus-4-7") == "plan"
    assert _role_for_model("claude-sonnet-4-6") == "code"
    assert _role_for_model("claude-haiku-4-5") == "fast"
    assert _role_for_model("something-else") == "plan"


def test_to_build_output_terminal_mapping():
    assert _to_build_output("satisfied", "ok", 1, [], 0, []).grader_result == "satisfied"
    assert _to_build_output("interrupted", "", 0, [], 0, []).grader_result == "failed"
    assert _to_build_output("failed", "", 0, [], 0, []).grader_result == "failed"
    mx = _to_build_output("max_iterations_reached", "", 2, [], 0, [])
    assert mx.grader_result == "max_iterations_reached"
    assert mx.iterations == 3  # iteration is 0-indexed → +1


def test_to_build_output_unknown_verdict_falls_back_on_files():
    with_files = _to_build_output("needs_revision", "", 0, [GeneratedFile(path="a.py")], 0, [])
    assert with_files.grader_result == "satisfied"
    no_files = _to_build_output("needs_revision", "", 0, [], 0, [])
    assert no_files.grader_result == "needs_revision"


def test_format_tool_use():
    assert (
        _format_tool_use(_evt("agent.tool_use", name="Write", input={"file_path": "a.py"}))
        == "Write a.py"
    )
    assert (
        _format_tool_use(_evt("agent.tool_use", name="Bash", input={"command": "ls -la"}))
        == "Bash ls -la"
    )
    assert (
        _format_tool_use(_evt("agent.tool_use", name="Glob", input={"pattern": "*.py"}))
        == "Glob '*.py'"
    )


# ----------------------------------------------------------------- executor


async def test_happy_path_satisfied_downloads_files(ctx):
    events = [
        _evt("agent.message", content=[_text("writing main.py")]),
        _evt("agent.tool_use", name="Write", input={"file_path": "app/main.py"}),
        _evt("span.model_request_end", model_usage=_usage(10_000, 5_000)),
        _evt(
            "span.outcome_evaluation_end",
            result="satisfied",
            explanation="all criteria met",
            iteration=0,
        ),
        _evt("session.status_idle"),
    ]
    client = FakeClient(
        events,
        output_files=[("file_main", "app/main.py")],
        file_bytes=b"print('hello')\n",
    )
    out = await OutcomesExecutor().run(ctx, client=client)

    assert out.grader_result == "satisfied"
    assert out.grader_explanation == "all criteria met"
    assert [f.path for f in out.files] == ["app/main.py"]
    assert out.cost_usd > 0  # priced from the 10k/5k usage
    # file actually written to disk
    assert (ctx.build_dir / "app/main.py").read_bytes() == b"print('hello')\n"
    # lifecycle + teardown ran
    assert client.calls[:4] == [
        "ensure_agent",
        "ensure_environment",
        "create_session",
        "send_define_outcome",
    ]
    assert client.deleted_session is True


async def test_max_iterations_reached(ctx):
    events = [
        _evt(
            "span.outcome_evaluation_end",
            result="needs_revision",
            explanation="missing tests",
            iteration=0,
        ),
        _evt(
            "span.outcome_evaluation_end",
            result="max_iterations_reached",
            explanation="still missing tests",
            iteration=2,
        ),
        _evt("session.status_idle"),
    ]
    out = await OutcomesExecutor().run(ctx, client=FakeClient(events))
    assert out.grader_result == "max_iterations_reached"
    assert out.iterations == 3


async def test_failed_verdict(ctx):
    events = [
        _evt(
            "span.outcome_evaluation_end",
            result="failed",
            explanation="rubric does not apply",
            iteration=0,
        ),
        _evt("session.status_terminated"),
    ]
    out = await OutcomesExecutor().run(ctx, client=FakeClient(events))
    assert out.grader_result == "failed"


async def test_teardown_runs_on_stream_exception(ctx):
    class Boom(FakeClient):
        async def stream_events(self, *, session_id):
            raise RuntimeError("stream dropped")
            yield  # pragma: no cover

    client = Boom([])
    with pytest.raises(RuntimeError, match="stream dropped"):
        await OutcomesExecutor().run(ctx, client=client)
    # teardown still happened despite the exception
    assert client.deleted_session is True


async def test_fix_mode_reuploads_prior_files(ctx, tmp_path):
    # Simulate a prior build already on disk
    (ctx.build_dir).mkdir(parents=True, exist_ok=True)
    (ctx.build_dir / "app").mkdir(parents=True, exist_ok=True)
    (ctx.build_dir / "app" / "main.py").write_text("old\n")

    fix_ctx = BuildContext(
        state=ctx.state,
        profile=ctx.profile,
        spec=ctx.spec,
        prd=ctx.prd,
        design=ctx.design,
        prior_build=BuildOutput(files=[GeneratedFile(path="app/main.py")]),
        validation_errors=None,
        attempt=2,
    )
    events = [
        _evt("span.outcome_evaluation_end", result="satisfied", explanation="fixed", iteration=0),
        _evt("session.status_idle"),
    ]
    client = FakeClient(events, output_files=[("f", "app/main.py")])
    await OutcomesExecutor().run(fix_ctx, client=client)

    assert "main.py" in client.uploaded
    assert client.mounted == ["/mnt/session/outputs/app/main.py"]


async def test_missing_key_raises(ctx, monkeypatch):
    import vineyard.build.outcomes_client as oc

    monkeypatch.setattr(oc.settings, "anthropic_api_key", "")
    with pytest.raises(RuntimeError, match="VINEYARD_ANTHROPIC_API_KEY"):
        # No client injected → from_settings() runs and should raise
        await OutcomesExecutor().run(ctx)
