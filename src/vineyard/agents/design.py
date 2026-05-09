"""Design phase agent."""

from vineyard.agents.base import composed_system_prompt
from vineyard.llm.gateway import build_agent
from vineyard.models import DesignOutput, PRDAnalysisOutput
from vineyard.stacks.base import StackProfile


def design_agent(profile: StackProfile):
    return build_agent(
        role="plan",
        output_type=DesignOutput,
        system_prompt=composed_system_prompt("design", profile),
        name="design",
    )


def build_design_prompt(prd_analysis: PRDAnalysisOutput) -> str:
    answered = [
        qa
        for qa in prd_analysis.clarification_qa
        if qa.answer and qa.answer.strip() not in ("", "(unanswered)")
    ]
    answered_block = ""
    if answered:
        lines = ["\n\nUSER ANSWERS TO PRIOR CLARIFICATIONS:"]
        for qa in answered:
            lines.append(f"- Q: {qa.question}\n  A: {qa.answer}")
        answered_block = "\n".join(lines)

    enriched = prd_analysis.enriched_prd_markdown or _synthesize_prd(prd_analysis)

    return (
        f"Turn this enriched PRD into a feature-level product design.\n\n"
        f"PRODUCT: {prd_analysis.product_name}\n\n"
        f"ENRICHED PRD:\n{enriched}\n\n"
        f"CORE PROBLEM: {prd_analysis.core_problem}\n"
        f"TARGET USERS: {', '.join(prd_analysis.target_users)}\n"
        f"MVP SCOPE NOTES: {prd_analysis.mvp_scope_notes}"
        f"{answered_block}"
    )


def _synthesize_prd(o: PRDAnalysisOutput) -> str:
    """Best-effort fallback when the agent left enriched_prd_markdown empty."""
    parts = [f"# {o.product_name}"]
    if o.product_summary:
        parts += ["", o.product_summary]
    if o.core_problem:
        parts += ["", "## Problem", o.core_problem]
    if o.target_users:
        parts += ["", "## Target Users", *(f"- {u}" for u in o.target_users)]
    if o.mvp_scope_notes:
        parts += ["", "## MVP Scope", o.mvp_scope_notes]
    if o.identified_gaps:
        parts += ["", "## Identified Gaps", *(f"- {g}" for g in o.identified_gaps)]
    return "\n".join(parts) or "(empty PRD analysis)"
