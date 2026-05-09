"""PRD Analysis phase agent."""

from vineyard.agents.base import base_prompt
from vineyard.llm.gateway import build_agent
from vineyard.models import PRDAnalysisOutput
from vineyard.models.handoff import PRDInput
from vineyard.stacks.base import StackProfile


def prd_analysis_agent(profile: StackProfile):
    fragment = profile.prompt_fragment("prd_analysis")
    system = base_prompt("prd_analysis")
    if fragment:
        system += f"\n\n## Stack-specific framing ({profile.display_name})\n\n{fragment}"
    return build_agent(
        role="plan",
        output_type=PRDAnalysisOutput,
        system_prompt=system,
        name="prd_analysis",
    )


def build_prd_analysis_prompt(prd: PRDInput) -> str:
    extra = f"\n\nADDITIONAL CONTEXT: {prd.additional_context}" if prd.additional_context else ""
    return (
        f"Analyze this PRD and produce the structured output.\n\n"
        f"PRODUCT NAME: {prd.name}\n\n"
        f"PRD TEXT:\n{prd.prd_text}{extra}"
    )
