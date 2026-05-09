"""Executor protocol + factory for the BUILD phase."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from vineyard.config import ExecutorName, settings
from vineyard.events import EventCallback, emit_event
from vineyard.models import BuildOutput, RunState, SpecOutput

if TYPE_CHECKING:
    from vineyard.stacks.base import StackProfile


@dataclass(frozen=True)
class BuildContext:
    """Everything a BUILD executor needs to generate a codebase."""

    state: RunState
    profile: StackProfile
    spec: SpecOutput
    on_event: EventCallback | None = None

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
