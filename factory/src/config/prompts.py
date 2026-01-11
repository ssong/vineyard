"""Agent prompts for all factory domains - loaded from markdown files."""

from pathlib import Path

# Base directory for prompts
PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    """Load a prompt from a markdown file."""
    filepath = PROMPTS_DIR / filename
    if filepath.exists():
        return filepath.read_text()
    # Fallback to basic prompt if file doesn't exist
    return f"[Prompt file not found: {filename}]"


# =============================================================================
# PRODUCT DOMAIN PROMPTS
# =============================================================================

RESEARCH_ENRICHMENT_PROMPT = _load_prompt("research_agent.md")
DESIGN_AGENT_PROMPT = _load_prompt("design_agent.md")
SPEC_AGENT_PROMPT = _load_prompt("spec_agent.md")

# =============================================================================
# ENGINEERING DOMAIN PROMPTS
# =============================================================================

CODE_AGENT_PROMPT = _load_prompt("code_agent.md")
TEST_AGENT_PROMPT = _load_prompt("test_agent.md")
SECURITY_AGENT_PROMPT = _load_prompt("security_agent.md")
DEVOPS_AGENT_PROMPT = _load_prompt("devops_agent.md")
QA_AGENT_PROMPT = _load_prompt("qa_agent.md")

# =============================================================================
# GTM DOMAIN PROMPTS
# =============================================================================

MARKETING_AGENT_PROMPT = _load_prompt("marketing_agent.md")
LAUNCH_AGENT_PROMPT = _load_prompt("launch_agent.md")
GROWTH_AGENT_PROMPT = _load_prompt("growth_agent.md")
SUPPORT_AGENT_PROMPT = _load_prompt("support_agent.md")
