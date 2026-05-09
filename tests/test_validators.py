"""get_validator factory selection across config/env combinations."""

from vineyard.validate.executor import get_validator


def _patch_settings(monkeypatch, **kwargs):
    from vineyard.validate import executor as exec_mod
    for k, v in kwargs.items():
        monkeypatch.setattr(exec_mod.settings, k, v)


def test_explicit_none_returns_skip(monkeypatch):
    _patch_settings(monkeypatch, validate_executor="none")
    v = get_validator()
    assert type(v).__name__ == "_SkipValidator"


def test_auto_with_e2b_key_picks_e2b(monkeypatch):
    _patch_settings(monkeypatch, validate_executor="auto", e2b_api_key="e2b_xxx")
    v = get_validator()
    # Either an E2BValidator or a SkipValidator (if e2b SDK isn't installed in test env).
    name = type(v).__name__
    assert name in ("E2BValidator", "_SkipValidator")
    if name == "_SkipValidator":
        assert "e2b" in v.reason.lower()


def test_auto_without_e2b_falls_back_to_docker_when_available(monkeypatch):
    _patch_settings(monkeypatch, validate_executor="auto", e2b_api_key="")
    monkeypatch.setattr("vineyard.validate.executor.shutil.which", lambda _: "/usr/bin/docker")
    v = get_validator()
    assert type(v).__name__ == "DockerValidator"


def test_auto_without_e2b_or_docker_returns_skip(monkeypatch):
    _patch_settings(monkeypatch, validate_executor="auto", e2b_api_key="")
    monkeypatch.setattr("vineyard.validate.executor.shutil.which", lambda _: None)
    v = get_validator()
    assert type(v).__name__ == "_SkipValidator"
    assert "no E2B key" in v.reason


def test_explicit_docker_without_cli_returns_skip(monkeypatch):
    _patch_settings(monkeypatch, validate_executor="docker")
    monkeypatch.setattr("vineyard.validate.executor.shutil.which", lambda _: None)
    v = get_validator()
    assert type(v).__name__ == "_SkipValidator"
    assert "docker" in v.reason.lower()


def test_explicit_e2b_without_key_returns_skip(monkeypatch):
    _patch_settings(monkeypatch, validate_executor="e2b", e2b_api_key="")
    v = get_validator()
    assert type(v).__name__ == "_SkipValidator"
    assert "VINEYARD_E2B_API_KEY" in v.reason


async def test_skip_validator_returns_success(monkeypatch, tmp_path):
    """SkipValidator should return success=True so phases don't fail when no
    sandbox is available — that's the whole point of the fallback."""
    from vineyard.models import RunState
    from vineyard.models.handoff import BuildPreferences, Handoff, PRDInput
    from vineyard.stacks import registry
    from vineyard.validate.executor import ValidatorContext

    _patch_settings(monkeypatch, validate_executor="none")
    state = RunState(
        run_id="r", output_dir=tmp_path,
        handoff=Handoff(
            handoff_id="h",
            prd_input=PRDInput(name="X", slug="x", prd_text=""),
            build_preferences=BuildPreferences(stack="nextjs"),
        ),
    )
    ctx = ValidatorContext(state=state, profile=registry.get("nextjs"))
    result = await get_validator().run(ctx)
    assert result.success is True
    assert result.backend == "skipped"
