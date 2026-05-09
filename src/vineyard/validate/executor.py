"""Protocol + factory for VALIDATE-phase executors."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from vineyard.config import settings
from vineyard.events import EventCallback, emit_event
from vineyard.models import RunState, ValidationOutput

if TYPE_CHECKING:
    from vineyard.stacks.base import StackProfile


@dataclass(frozen=True)
class ValidatorContext:
    """Everything a validator needs to run the stack's validate_commands."""

    state: RunState
    profile: StackProfile
    on_event: EventCallback | None = None

    @property
    def build_dir(self) -> Path:
        return self.state.output_dir / "build"

    async def emit(self, kind: str, text: str) -> None:
        await emit_event(self.on_event, kind, text)


class Validator(Protocol):
    """Async runner for the validate phase."""

    async def run(self, ctx: ValidatorContext) -> ValidationOutput: ...


def get_validator() -> Validator:
    """Pick a validator based on settings + environment availability.

    `auto` (default): E2B if VINEYARD_E2B_API_KEY is set, else Docker if the
    docker CLI is available, else a no-op SkipValidator that records a
    'skipped' result so the phase doesn't fail outright.
    """
    choice = settings.validate_executor

    if choice == "none":
        return _SkipValidator(reason="validate_executor=none")

    if choice == "e2b":
        return _make_e2b()

    if choice == "docker":
        return _make_docker()

    # auto
    if settings.e2b_api_key:
        return _make_e2b()
    if shutil.which("docker"):
        return _make_docker()
    return _SkipValidator(
        reason="no E2B key and no docker CLI on PATH — set VINEYARD_E2B_API_KEY "
        "or install Docker to enable validation",
    )


def _make_docker() -> Validator:
    if not shutil.which("docker"):
        return _SkipValidator(reason="docker CLI not found on PATH")
    from vineyard.validate.docker_exec import DockerValidator

    return DockerValidator()


def _make_e2b() -> Validator:
    if not settings.e2b_api_key:
        return _SkipValidator(reason="VINEYARD_E2B_API_KEY not set")
    try:
        from vineyard.validate.e2b_exec import E2BValidator
    except ImportError as e:
        return _SkipValidator(reason=f"e2b SDK not installed: {e}")
    return E2BValidator()


class _SkipValidator:
    """Placeholder when no real backend is usable; records a 'skipped' result."""

    def __init__(self, reason: str) -> None:
        self.reason = reason

    async def run(self, ctx: ValidatorContext) -> ValidationOutput:
        await ctx.emit("phase", f"validate skipped — {self.reason}")
        return ValidationOutput(
            backend="skipped",
            success=True,  # don't fail the run for absence of a sandbox
            summary=f"Skipped: {self.reason}",
        )
