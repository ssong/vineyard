"""E2B-backed validator. Spins up a Firecracker microVM, uploads the build
directory, runs the stack's validate_commands, and tears down.

Requires ``e2b-code-interpreter`` (optional dependency) and a
``VINEYARD_E2B_API_KEY``. The factory in :mod:`vineyard.validate.executor`
falls back gracefully when either is missing.
"""

from __future__ import annotations

import time

import logfire

from vineyard.config import settings
from vineyard.models import ValidationOutput, ValidationStep
from vineyard.validate.executor import ValidatorContext

_TAIL_BYTES = 4_000


class E2BValidator:
    async def run(self, ctx: ValidatorContext) -> ValidationOutput:
        commands = tuple(ctx.profile.validate_commands)
        if not commands:
            return ValidationOutput(
                backend="e2b",
                success=True,
                summary="No validate_commands defined for this stack.",
            )
        if not ctx.build_dir.exists():
            return ValidationOutput(
                backend="e2b",
                success=False,
                summary=f"Build directory does not exist: {ctx.build_dir}",
            )

        # Lazy import — keeps the package optional.
        from e2b_code_interpreter import Sandbox  # type: ignore[import-not-found]

        with logfire.span("validate.e2b", run_id=ctx.state.run_id):
            await ctx.emit("phase", "validate (e2b): launching sandbox")
            sandbox = Sandbox.create(api_key=settings.e2b_api_key, timeout=900)
            try:
                await ctx.emit("phase", "validate (e2b): uploading build directory")
                self._upload(sandbox, ctx)

                steps: list[ValidationStep] = []
                failed_idx: int | None = None
                for i, cmd in enumerate(commands):
                    await ctx.emit("tool", f"validate ▶ {cmd}")
                    started = time.monotonic()
                    result = sandbox.commands.run(
                        f"cd /workspace && {cmd}",
                        timeout=600,
                    )
                    elapsed = time.monotonic() - started
                    exit_code = getattr(result, "exit_code", 0)
                    stdout = getattr(result, "stdout", "") or ""
                    stderr = getattr(result, "stderr", "") or ""
                    steps.append(
                        ValidationStep(
                            command=cmd,
                            exit_code=exit_code,
                            duration_seconds=round(elapsed, 2),
                            stdout_tail=stdout[-_TAIL_BYTES:],
                            stderr_tail=stderr[-_TAIL_BYTES:],
                        )
                    )
                    await ctx.emit(
                        "tool" if exit_code == 0 else "error",
                        f"validate {'✓' if exit_code == 0 else '✗'} "
                        f"({elapsed:.1f}s) {cmd}",
                    )
                    if exit_code != 0:
                        failed_idx = i
                        break
            finally:
                try:
                    sandbox.kill()
                except Exception:
                    pass

        success = failed_idx is None
        summary = (
            f"All {len(steps)} step(s) passed."
            if success
            else f"Failed at step {failed_idx + 1} of {len(commands)}: "
            f"{commands[failed_idx]!r}"
        )
        return ValidationOutput(
            backend="e2b",
            success=success,
            steps=steps,
            failed_step_index=failed_idx,
            summary=summary,
        )

    @staticmethod
    def _upload(sandbox, ctx: ValidatorContext) -> None:
        build_dir = ctx.build_dir
        for src in build_dir.rglob("*"):
            if not src.is_file():
                continue
            rel = src.relative_to(build_dir).as_posix()
            dest = f"/workspace/{rel}"
            try:
                # Try text first; fall back to bytes for binaries.
                sandbox.files.write(dest, src.read_text())
            except UnicodeDecodeError:
                sandbox.files.write(dest, src.read_bytes())
