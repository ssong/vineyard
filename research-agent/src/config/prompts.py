"""System prompts for research agents - loaded from markdown files."""

from pathlib import Path

# Base directory for prompts
PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    """Load a prompt from a markdown file."""
    filepath = PROMPTS_DIR / filename
    if filepath.exists():
        return filepath.read_text()
    # Fallback to inline prompt if file doesn't exist
    return f"[Prompt file not found: {filename}]"


# Load prompts from markdown files
DISCOVERY_AGENT_PROMPT = _load_prompt("discovery_agent.md")
VALIDATION_AGENT_PROMPT = _load_prompt("validation_agent.md")
SCORING_AGENT_PROMPT = _load_prompt("scoring_agent.md")
