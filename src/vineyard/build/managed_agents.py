"""Beta BUILD executor: Anthropic Claude Agent SDK.

The SDK runs the agent with built-in file tools (Read/Write/Edit) inside the
configured ``cwd``. We hand it the spec, let it work, then walk the build dir
for the generated file list. ``ResultMessage.total_cost_usd`` gives us
authoritative cost tracking.

Outcomes (beta): the long-horizon grader Anthropic exposes for managed agents.
The hookpoint is marked below — wire ``task_budget`` / ``output_format`` once
the Outcomes API surface is final.
"""

from __future__ import annotations

from pathlib import Path

import logfire
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from vineyard.build.executor import BuildContext
from vineyard.build.prompts import compose_system_prompt, compose_user_prompt
from vineyard.config import settings
from vineyard.models import BuildOutput, GeneratedFile

_LANG_BY_EXT: dict[str, str] = {
    ".py": "python", ".rb": "ruby", ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".css": "css", ".html": "html",
    ".json": "json", ".md": "markdown", ".yml": "yaml", ".yaml": "yaml",
    ".sql": "sql", ".sh": "shell", ".toml": "toml", ".env": "dotenv",
}


class ManagedAgentsExecutor:
    async def run(self, ctx: BuildContext) -> BuildOutput:
        build_dir = ctx.build_dir
        build_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        env: dict[str, str] = {}
        if settings.anthropic_api_key:
            env["ANTHROPIC_API_KEY"] = settings.anthropic_api_key

        options = ClaudeAgentOptions(
            cwd=str(build_dir),
            system_prompt=compose_system_prompt(ctx),
            allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
            permission_mode="bypassPermissions",
            env=env,
            # TODO(beta/Outcomes): wire `task_budget=` and `output_format=` once
            # the Managed Agents Outcomes API surface stabilizes — that's the
            # whole point of opting into this executor.
        )

        cost = 0.0
        narration: list[str] = []

        with logfire.span("build.managed_agents", run_id=ctx.state.run_id):
            async for msg in query(prompt=compose_user_prompt(ctx), options=options):
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            narration.append(block.text)
                elif isinstance(msg, ResultMessage):
                    if msg.total_cost_usd:
                        cost = float(msg.total_cost_usd)

        files = _collect_files(build_dir)
        summary = "\n\n".join(narration)[-2000:] or "(no narration captured)"

        return BuildOutput(
            files=files,
            summary=summary,
            grader_result="satisfied" if files else "needs_revision",
            grader_explanation="Outcomes grading not yet wired — beta hookpoint pending.",
            iterations=1,
            cost_usd=cost,
        )


def _collect_files(build_dir: Path) -> list[GeneratedFile]:
    out: list[GeneratedFile] = []
    for p in sorted(build_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(build_dir).as_posix()
        out.append(GeneratedFile(path=rel, language=_LANG_BY_EXT.get(p.suffix, "text")))
    return out
