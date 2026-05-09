"""QA phase agent — validates a generated codebase against rubric and spec."""

from vineyard.agents.base import base_prompt
from vineyard.llm.gateway import build_agent
from vineyard.models import BuildOutput, QAOutput, SpecOutput
from vineyard.stacks.base import StackProfile


def qa_agent(profile: StackProfile):
    system = (
        base_prompt("qa")
        + "\n\n## Rubric you are validating against\n\n"
        + profile.rubric()
    )
    return build_agent(
        role="judge",
        output_type=QAOutput,
        system_prompt=system,
        name="qa",
    )


def build_qa_prompt(spec: SpecOutput, build: BuildOutput) -> str:
    file_listing = "\n".join(f"- {f.path} ({f.language})" for f in build.files) or "(no files)"
    return (
        f"Validate the generated codebase against the rubric and spec.\n\n"
        f"GENERATED FILES ({len(build.files)} total):\n{file_listing}\n\n"
        f"BUILDER SUMMARY:\n{build.summary}\n\n"
        f"GRADER RESULT: {build.grader_result}\n"
        f"GRADER EXPLANATION: {build.grader_explanation}\n\n"
        f"SPEC SUMMARY:\n{spec.technical_spec_markdown[:4000]}"
    )
