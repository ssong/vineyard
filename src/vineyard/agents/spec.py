"""Spec phase agent."""

from vineyard.agents.base import composed_system_prompt
from vineyard.llm.gateway import build_agent
from vineyard.models import DesignOutput, PRDAnalysisOutput, SpecOutput
from vineyard.stacks.base import StackProfile


def spec_agent(profile: StackProfile):
    return build_agent(
        role="plan",
        output_type=SpecOutput,
        system_prompt=composed_system_prompt("spec", profile),
        name="spec",
    )


def build_spec_prompt(design: DesignOutput, prd: PRDAnalysisOutput | None = None) -> str:
    feature_lines = []
    for feature in design.features:
        feature_lines.append(f"- [{feature.priority}] {feature.name}: {feature.description}")
    features_block = "\n".join(feature_lines) if feature_lines else "(no features supplied)"

    sections: list[str] = ["Turn this product design into a buildable technical specification."]

    # Include the original PRD context — design.prd_markdown alone can be thin
    # if the design agent didn't write much, and PRD answered clarifications
    # belong here too.
    if prd is not None:
        if prd.product_summary:
            sections.append(f"PRODUCT SUMMARY:\n{prd.product_summary}")
        if prd.core_problem:
            sections.append(f"CORE PROBLEM:\n{prd.core_problem}")
        if prd.target_users:
            sections.append(f"TARGET USERS: {', '.join(prd.target_users)}")
        if prd.enriched_prd_markdown:
            sections.append(f"ENRICHED PRD:\n{prd.enriched_prd_markdown}")

    sections.append(f"DESIGN PRD:\n{design.prd_markdown}")
    sections.append(f"FEATURES:\n{features_block}")

    # Answered clarifications from any upstream phase
    answered_blocks: list[str] = []
    if prd is not None:
        prd_answered = [
            qa
            for qa in prd.clarification_qa
            if qa.answer and qa.answer.strip() not in ("", "(unanswered)")
        ]
        if prd_answered:
            lines = ["From prd_analysis:"]
            for qa in prd_answered:
                lines.append(f"- Q: {qa.question}\n  A: {qa.answer}")
            answered_blocks.append("\n".join(lines))
    design_answered = [
        qa
        for qa in design.clarification_qa
        if qa.answer and qa.answer.strip() not in ("", "(unanswered)")
    ]
    if design_answered:
        lines = ["From design:"]
        for qa in design_answered:
            lines.append(f"- Q: {qa.question}\n  A: {qa.answer}")
        answered_blocks.append("\n".join(lines))
    if answered_blocks:
        sections.append(
            "USER ANSWERS TO PRIOR CLARIFICATIONS:\n" + "\n\n".join(answered_blocks)
        )

    return "\n\n".join(sections)
