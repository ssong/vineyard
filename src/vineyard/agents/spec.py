"""Spec phase agent."""

from vineyard.agents.base import composed_system_prompt
from vineyard.llm.gateway import build_agent
from vineyard.models import DesignOutput, SpecOutput
from vineyard.stacks.base import StackProfile


def spec_agent(profile: StackProfile):
    return build_agent(
        role="plan",
        output_type=SpecOutput,
        system_prompt=composed_system_prompt("spec", profile),
        name="spec",
    )


def build_spec_prompt(design: DesignOutput) -> str:
    feature_lines = []
    for feature in design.features:
        feature_lines.append(f"- [{feature.priority}] {feature.name}: {feature.description}")
    features_block = "\n".join(feature_lines) if feature_lines else "(no features supplied)"

    return (
        f"Turn this product design into a buildable technical specification.\n\n"
        f"DESIGN PRD:\n{design.prd_markdown}\n\n"
        f"FEATURES:\n{features_block}"
    )
