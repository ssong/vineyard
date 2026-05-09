"""Prompt composition shared by both BUILD executors."""

from __future__ import annotations

from vineyard.agents.base import base_prompt
from vineyard.build.executor import BuildContext


def compose_system_prompt(ctx: BuildContext) -> str:
    parts: list[str] = [base_prompt("build")]
    parts.append(
        f"\n## Stack: {ctx.profile.display_name}\n\n{ctx.profile.system_prompt()}"
    )
    fragment = ctx.profile.prompt_fragment("build")
    if fragment:
        parts.append(f"\n## Stack-specific build guidance\n\n{fragment}")
    parts.append(f"\n## Rubric you will be graded against\n\n{ctx.profile.rubric()}")
    return "\n".join(parts)


def compose_user_prompt(ctx: BuildContext) -> str:
    spec = ctx.spec
    prefs = ctx.state.handoff.build_preferences
    prd = ctx.state.handoff.prd_input

    endpoints = "\n".join(
        f"- {e.method} {e.path} — {e.description}" for e in spec.api_endpoints
    ) or "(none)"
    tables = "\n".join(
        f"- {t.name}: {t.description}" for t in spec.database_schema
    ) or "(none)"
    tasks = "\n".join(
        f"- [{t.story_points}pt] {t.title}" for t in spec.task_breakdown
    ) or "(none)"

    return (
        f"Build the codebase for **{prd.name}** on the {ctx.profile.display_name} stack.\n\n"
        f"BUILD PREFERENCES: auth={prefs.auth} · payments={prefs.payments} · db={prefs.db}\n\n"
        f"API ENDPOINTS:\n{endpoints}\n\n"
        f"DATABASE TABLES:\n{tables}\n\n"
        f"ENGINEERING TASKS:\n{tasks}\n\n"
        f"TECHNICAL SPEC:\n{spec.technical_spec_markdown}"
    )
