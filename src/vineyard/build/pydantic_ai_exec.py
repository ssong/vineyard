"""Default BUILD executor: a Pydantic AI Agent with file-system tools.

Routes through the Pydantic AI Gateway like every other phase agent. The agent
loops through tool calls (write/read/list files) until it returns a typed
``BuildOutput``. We trust the recorded tool calls — not the model's self-report —
for the final file list.
"""

from __future__ import annotations

from pathlib import Path

import logfire
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

from vineyard.build.executor import BuildContext
from vineyard.build.prompts import compose_system_prompt, compose_user_prompt
from vineyard.config import settings
from vineyard.llm.gateway import cost_for_usage, model_for
from vineyard.models import BuildOutput, GeneratedFile


class PydanticAIExecutor:
    async def run(self, ctx: BuildContext) -> BuildOutput:
        build_dir = ctx.build_dir
        build_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        build_dir_resolved = build_dir.resolve()

        # On a fix-mode retry, seed with the prior attempt's file list so the
        # final BuildOutput.files reflects the union (previously written +
        # whatever the agent overwrites this round). Without this, files the
        # agent doesn't touch on this attempt would silently disappear from
        # the recorded list even though they're still on disk.
        files_written: dict[str, GeneratedFile] = {}
        if ctx.prior_build is not None:
            for f in ctx.prior_build.files:
                files_written[f.path] = f

        def _safe_target(path: str) -> Path:
            target = (build_dir / path).resolve()
            if not target.is_relative_to(build_dir_resolved):
                raise ValueError(f"path escapes build directory: {path!r}")
            return target

        async def write_file(path: str, content: str, language: str = "text") -> str:
            """Write a source file inside the build directory.

            Args:
                path: Relative path under the build dir (e.g. ``src/app.tsx``).
                content: Full file contents.
                language: Language tag for downstream rendering (e.g. ``typescript``).
            """
            target = _safe_target(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            files_written[path] = GeneratedFile(path=path, language=language)
            await ctx.emit("tool", f"write_file {path} ({len(content)}B, {language})")
            return f"wrote {path} ({len(content)} bytes)"

        async def read_file(path: str) -> str:
            """Read a file you previously wrote in this build."""
            await ctx.emit("tool", f"read_file {path}")
            target = _safe_target(path)
            if not target.exists():
                return f"<not found: {path}>"
            return target.read_text()

        async def list_files() -> list[str]:
            """List every file written in this build so far."""
            await ctx.emit("tool", f"list_files ({len(files_written)} so far)")
            return sorted(files_written.keys())

        agent = Agent(
            model_for("code"),
            output_type=BuildOutput,
            system_prompt=compose_system_prompt(ctx),
            name="build",
            tools=[write_file, read_file, list_files],
            retries=2,
        )

        with logfire.span("build.pydantic_ai", run_id=ctx.state.run_id):
            result = await agent.run(
                compose_user_prompt(ctx),
                usage_limits=UsageLimits(request_limit=settings.build_request_limit),
            )

        output: BuildOutput = result.output
        if files_written:
            output.files = list(files_written.values())

        usage_fn = getattr(result, "usage", None)
        if callable(usage_fn):
            usage = usage_fn()
            if usage is not None:
                explicit = (
                    getattr(usage, "total_cost", None)
                    or getattr(usage, "request_cost", None)
                )
                if explicit:
                    output.cost_usd = float(explicit)
                else:
                    output.cost_usd = cost_for_usage(
                        "code",
                        input_tokens=getattr(usage, "input_tokens", 0) or 0,
                        output_tokens=getattr(usage, "output_tokens", 0) or 0,
                        cache_read_tokens=getattr(usage, "cache_read_tokens", 0) or 0,
                        cache_write_tokens=getattr(usage, "cache_write_tokens", 0) or 0,
                    )

        return output
