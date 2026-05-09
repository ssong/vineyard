"""Helpers shared by phase agents."""

from importlib.resources import files

from vineyard.stacks.base import StackProfile

_PROMPT_PKG = "vineyard.prompts"


def base_prompt(name: str) -> str:
    """Load a base prompt by stem (e.g. 'prd_analysis')."""
    return (files(_PROMPT_PKG) / f"{name}.md").read_text()


def composed_system_prompt(phase: str, profile: StackProfile) -> str:
    """Combine the base prompt with the stack-specific fragment for this phase."""
    base = base_prompt(phase)
    fragment = profile.prompt_fragment(phase)
    if not fragment:
        return base
    return f"{base}\n\n## Stack-specific guidance ({profile.display_name})\n\n{fragment}"
