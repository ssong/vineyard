"""Stack registry sanity checks — every stack has its rubric and prompts."""

import pytest

from vineyard.stacks import registry

EXPECTED = ["nextjs", "rails", "fastapi", "django"]


@pytest.mark.parametrize("name", EXPECTED)
def test_stack_registered(name):
    profile = registry.get(name)  # type: ignore[arg-type]
    assert profile.rubric().strip(), f"{name} rubric is empty"
    assert profile.system_prompt().strip(), f"{name} system prompt is empty"


def test_all_stacks_listed():
    names = sorted(p.name for p in registry.all())
    assert names == sorted(EXPECTED)


def test_default_preferences_match_stack():
    for profile in registry.all():
        prefs = profile.default_preferences()
        assert prefs.stack == profile.name
