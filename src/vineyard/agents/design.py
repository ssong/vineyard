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

    return (
        f"Turn this enriched PRD into a feature-level product design.\n\n"
        f"PRODUCT: {prd_analysis.product_name}\n\n"
        f"ENRICHED PRD:\n{prd_analysis.enriched_prd_markdown}\n\n"
        f"CORE PROBLEM: {prd_analysis.core_problem}\n"
        f"TARGET USERS: {', '.join(prd_analysis.target_users)}\n"
        f"MVP SCOPE NOTES: {prd_analysis.mvp_scope_notes}"
        f"{answered_block}"
    )
