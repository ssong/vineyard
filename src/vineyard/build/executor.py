"""Executor protocol + factory for the BUILD phase."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from vineyard.config import ExecutorName, settings
from vineyard.events import EventCallback, emit_event
from vineyard.models import (
    BuildOutput,
    DesignOutput,
    PRDAnalysisOutput,
    RunState,
    SpecOutput,
    ValidationOutput,
)

if TYPE_CHECKING:
    from vineyard.stacks.base import StackProfile


@dataclass(frozen=True)
class BuildContext:
    """Everything a BUILD executor needs to generate a codebase.

    The upstream phase outputs (``prd``, ``design``) are passed alongside the
    spec so the build agent has the same product context the design and spec
    agents had — features, user stories, user flows, and any clarifications
    the user answered along the way.

    On a retry triggered by a failed VALIDATE phase, ``prior_build`` and
    ``validation_errors`` carry forward so the agent can read the existing
    files and surgically fix the offending lines instead of rewriting from
    scratch. ``attempt == 1`` is the first build; 2+ are fix attempts.
    """

    state: RunState
    profile: StackProfile
    spec: SpecOutput
    prd: PRDAnalysisOutput | None = None
    design: DesignOutput | None = None
    on_event: EventCallback | None = None
    prior_build: BuildOutput | None = None
    validation_errors: ValidationOutput | None = None
    attempt: int = 1

    @property
    def build_dir(self) -> Path:
        """Where generated files should land. Created lazily by the executor."""
        return self.state.output_dir / "build"

    async def emit(self, kind: str, text: str) -> None:
        await emit_event(self.on_event, kind, text)


class Executor(Protocol):
    """Async BUILD executor. Implementations live in sibling modules."""

    async def run(self, ctx: BuildContext) -> BuildOutput: ...


def get_executor(name: ExecutorName | None = None) -> Executor:
    """Resolve an executor by name. Falls back to the configured default."""
    chosen: ExecutorName = name or settings.build_executor

    if chosen == "pydantic_ai":
        from vineyard.build.pydantic_ai_exec import PydanticAIExecutor
        return PydanticAIExecutor()

    if chosen == "managed_agents":
        from vineyard.build.managed_agents import ManagedAgentsExecutor
        return ManagedAgentsExecutor()

    raise ValueError(f"Unknown executor: {chosen!r}")
