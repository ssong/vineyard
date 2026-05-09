"""Docker-backed validator. Spawns a one-shot container per validate command.

Each command runs in the same container session via ``docker exec`` so installed
deps persist across steps. The build directory is bind-mounted at /workspace.
"""

from __future__ import annotations

import asyncio
import time
import uuid

import logfire

from vineyard.models import ValidationOutput, ValidationStep
from vineyard.validate.executor import ValidatorContext

_TAIL_BYTES = 4_000


class DockerValidator:
    async def run(self, ctx: ValidatorContext) -> ValidationOutput:
        commands = tuple(ctx.profile.validate_commands)
        if not commands:
            return ValidationOutput(
                backend="docker",
                success=True,
                summary="No validate_commands defined for this stack.",
            )
        if not ctx.build_dir.exists():
            return ValidationOutput(
                backend="docker",
                success=False,
                summary=f"Build directory does not exist: {ctx.build_dir}",
            )

        container = f"vineyard-validate-{uuid.uuid4().hex[:8]}"
        image = ctx.profile.container_image

        with logfire.span("validate.docker", run_id=ctx.state.run_id, image=image):
            await ctx.emit("phase", f"validate (docker): pulling {image} if needed")
            await self._exec(["docker", "pull", image])

            await ctx.emit("phase", f"validate (docker): starting container {container}")
            up = await self._exec(
                [
                    "docker", "run", "-d",
                    "--name", container,
                    "-v", f"{ctx.build_dir.resolve()}:/workspace",
                    "-w", "/workspace",
                    image,
                    "sleep", "3600",
                ]
            )
            if up.returncode != 0:
                return ValidationOutput(
                    backend="docker",
                    success=False,
                    summary="Could not start container",
                    steps=[
                        ValidationStep(
                            command="docker run …",
                            exit_code=up.returncode,
                            stdout_tail=up.stdout,
                            stderr_tail=up.stderr,
                        )
                    ],
                )

            steps: list[ValidationStep] = []
            failed_idx: int | None = None
            try:
                for i, cmd in enumerate(commands):
                    await ctx.emit("tool", f"validate ▶ {cmd}")
                    started = time.monotonic()
                    res = await self._exec(
                        ["docker", "exec", container, "sh", "-lc", cmd]
                    )
                    elapsed = time.monotonic() - started
                    step = ValidationStep(
                        command=cmd,
                        exit_code=res.returncode,
                        duration_seconds=round(elapsed, 2),
                        stdout_tail=res.stdout[-_TAIL_BYTES:],
                        stderr_tail=res.stderr[-_TAIL_BYTES:],
                    )
                    steps.append(step)
                    await ctx.emit(
                        "tool" if res.returncode == 0 else "error",
                        f"validate {'✓' if res.returncode == 0 else '✗'} "
                        f"({elapsed:.1f}s) {cmd}",
                    )
                    if res.returncode != 0:
                        failed_idx = i
                        break
            finally:
                await self._exec(["docker", "rm", "-f", container])

        success = failed_idx is None
        summary = (
            f"All {len(steps)} step(s) passed."
            if success
            else f"Failed at step {failed_idx + 1} of {len(commands)}: "
            f"{commands[failed_idx]!r}"
        )
        return ValidationOutput(
            backend="docker",
            success=success,
            steps=steps,
            failed_step_index=failed_idx,
            summary=summary,
        )

    @staticmethod
    async def _exec(argv: list[str]) -> _ProcResult:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        return _ProcResult(
            returncode=proc.returncode or 0,
            stdout=out.decode("utf-8", errors="replace"),
            stderr=err.decode("utf-8", errors="replace"),
        )


class _ProcResult:
    __slots__ = ("returncode", "stdout", "stderr")

    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
