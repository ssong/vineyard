"""Eval runners — wire pydantic_evals datasets to phase agents.

Stub: real eval datasets land in `evals/datasets/*.yaml` once we have a baseline.
"""

from __future__ import annotations

from pathlib import Path

import logfire
from pydantic_evals import Dataset

from vineyard.agents.prd_analysis import build_prd_analysis_prompt, prd_analysis_agent
from vineyard.llm.logfire import configure_logfire
from vineyard.models.handoff import PRDInput
from vineyard.stacks import registry

DATASETS_DIR = Path(__file__).resolve().parent / "datasets"


async def run_prd_analysis_eval(stack: str = "nextjs") -> None:
    configure_logfire()
    profile = registry.get(stack)  # type: ignore[arg-type]
    agent = prd_analysis_agent(profile)
    dataset_path = DATASETS_DIR / "prd_analysis.yaml"
    if not dataset_path.exists():
        logfire.warn("No prd_analysis dataset; create %s to enable evals.", dataset_path)
        return
    dataset = Dataset[PRDInput, dict, dict].from_file(dataset_path)

    async def task(inp: PRDInput) -> dict:
        result = await agent.run(build_prd_analysis_prompt(inp))
        return result.output.model_dump()

    report = await dataset.evaluate(task)
    report.print(include_input=False, include_expected_output=False)
