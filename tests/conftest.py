"""Shared fixtures: tmp data dir, in-memory store, no real LLM calls."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Each test gets its own ~/.vineyard with fresh settings everywhere it's bound."""
    monkeypatch.setenv("VINEYARD_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VINEYARD_PYDANTIC_AI_GATEWAY_API_KEY", "test-key")
    monkeypatch.setenv("LOGFIRE_IGNORE_NO_CONFIG", "1")
    import vineyard.config as config_mod

    fresh = config_mod.Settings()
    monkeypatch.setattr(config_mod, "settings", fresh)
    # Re-bind the same instance everywhere modules captured it at import time.
    for mod_path in (
        "vineyard.storage.db",
        "vineyard.orchestrator.runner",
        "vineyard.cli",
        "vineyard.llm.gateway",
        "vineyard.llm.logfire",
        "vineyard.validate.executor",
        "vineyard.validate.e2b_exec",
        "vineyard.build.executor",
        "vineyard.build.pydantic_ai_exec",
        "vineyard.build.managed_agents",
    ):
        try:
            mod = __import__(mod_path, fromlist=["settings"])
        except ImportError:
            continue
        if hasattr(mod, "settings"):
            monkeypatch.setattr(mod, "settings", fresh)
    return tmp_path


@pytest.fixture
def store():
    from vineyard.storage import RunStore
    return RunStore()
