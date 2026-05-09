"""Prompt composition shared by both BUILD executors.

The user prompt assembles every upstream artifact so the build agent has the
same product context the design and spec agents had — original PRD, enriched
PRD, full feature breakdowns, user flows, and any clarifications the user
answered along the way. Without these, a thin spec leaves the build agent
guessing.
"""

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
    prd_input = ctx.state.handoff.prd_input

    sections: list[str] = [
        f"Build the codebase for **{prd_input.name}** on the {ctx.profile.display_name} stack.",
        f"BUILD PREFERENCES: auth={prefs.auth} · payments={prefs.payments} · db={prefs.db}",
    ]

    # ---- Product context (PRD) ----
    if ctx.prd is not None:
        if ctx.prd.product_summary:
            sections.append(f"PRODUCT SUMMARY:\n{ctx.prd.product_summary}")
        if ctx.prd.core_problem:
            sections.append(f"CORE PROBLEM:\n{ctx.prd.core_problem}")
        if ctx.prd.target_users:
            users = ", ".join(ctx.prd.target_users)
            sections.append(f"TARGET USERS: {users}")
        if ctx.prd.enriched_prd_markdown:
            sections.append(f"ENRICHED PRD:\n{ctx.prd.enriched_prd_markdown}")

    # ---- Design context (features + flows) ----
    if ctx.design is not None and ctx.design.features:
        feature_blocks: list[str] = []
        for f in ctx.design.features:
            block = [f"### [{f.priority}] {f.name}", f.description]
            if f.user_stories:
                block.append("**User stories:**")
                block.extend(f"- {s}" for s in f.user_stories)
            if f.acceptance_criteria:
                block.append("**Acceptance criteria:**")
                block.extend(f"- {c}" for c in f.acceptance_criteria)
            if f.technical_notes:
                block.append(f"_Notes:_ {f.technical_notes}")
            feature_blocks.append("\n".join(block))
        sections.append("FEATURES:\n" + "\n\n".join(feature_blocks))

    if ctx.design is not None and ctx.design.user_flows:
        flow_blocks: list[str] = []
        for flow in ctx.design.user_flows:
            steps = "\n".join(f"  {i + 1}. {step}" for i, step in enumerate(flow.steps))
            flow_blocks.append(f"- **{flow.name}:**\n{steps}")
        sections.append("USER FLOWS:\n" + "\n".join(flow_blocks))

    # ---- Answered clarifications from every upstream phase ----
    answered = _gather_answered(ctx)
    if answered:
        ans_lines: list[str] = []
        for phase_name, qas in answered:
            ans_lines.append(f"From {phase_name}:")
            for qa in qas:
                ans_lines.append(f"- Q: {qa.question}\n  A: {qa.answer}")
        sections.append("USER ANSWERS TO PRIOR CLARIFICATIONS:\n" + "\n".join(ans_lines))

    # ---- Spec details ----
    endpoints = (
        "\n".join(f"- {e.method} {e.path} — {e.description}" for e in spec.api_endpoints)
        or "(none)"
    )
    tables = (
        "\n".join(f"- {t.name}: {t.description}" for t in spec.database_schema) or "(none)"
    )
    tasks = (
        "\n".join(f"- [{t.story_points}pt] {t.title}" for t in spec.task_breakdown)
        or "(none)"
    )
    sections.append(f"API ENDPOINTS:\n{endpoints}")
    sections.append(f"DATABASE TABLES:\n{tables}")
    sections.append(f"ENGINEERING TASKS:\n{tasks}")
    if spec.technical_spec_markdown:
        sections.append(f"TECHNICAL SPEC:\n{spec.technical_spec_markdown}")

    # ---- Fix mode (only set on retries after validation failed) ----
    fix_block = _fix_mode_section(ctx)
    if fix_block:
        sections.append(fix_block)

    return "\n\n".join(sections)


def _fix_mode_section(ctx: BuildContext) -> str | None:
    """Compose a FIX MODE block describing the prior build + validation failure.

    Placed at the end of the prompt so it dominates recent-context attention
    and so the unchanging upstream sections above stay cacheable across retries.
    """
    if ctx.validation_errors is None or ctx.prior_build is None:
        return None

    prior_files = "\n".join(
        f"- {f.path} ({f.language})" for f in ctx.prior_build.files
    ) or "(no files recorded)"

    err = ctx.validation_errors
    failed_step = None
    if err.failed_step_index is not None and 0 <= err.failed_step_index < len(err.steps):
        failed_step = err.steps[err.failed_step_index]

    lines = [
        f"## FIX MODE — Attempt {ctx.attempt}",
        "",
        "Your previous build attempt produced these files (they're already on "
        "disk — `read_file` to inspect, `write_file` to overwrite):",
        prior_files,
    ]

    if failed_step is not None:
        lines += [
            "",
            f"Validation failed at step {err.failed_step_index + 1} of "
            f"{len(err.steps)}: `{failed_step.command}`",
            f"Exit code: {failed_step.exit_code}  ·  "
            f"Duration: {failed_step.duration_seconds:.2f}s",
        ]
        if failed_step.stderr_tail.strip():
            lines += ["", "stderr (tail):", "```", failed_step.stderr_tail.strip(), "```"]
        if failed_step.stdout_tail.strip():
            lines += ["", "stdout (tail):", "```", failed_step.stdout_tail.strip(), "```"]
    else:
        lines += ["", f"Validation failure summary: {err.summary or '(no detail)'}"]

    lines += [
        "",
        "**Surgical edits only.** Use `read_file` to inspect the specific files "
        "the errors point to, then `write_file` to overwrite just those files "
        "with corrected content. Do not rewrite files that aren't broken. "
        "Don't introduce new files unless the error literally requires one.",
    ]
    return "\n".join(lines)


def _gather_answered(ctx: BuildContext) -> list[tuple[str, list]]:
    """Collect every clarification_qa with a real answer from upstream phases."""
    out: list[tuple[str, list]] = []
    for phase_name, src in [
        ("prd_analysis", ctx.prd),
        ("design", ctx.design),
        ("spec", ctx.spec),
    ]:
        if src is None:
            continue
        items = getattr(src, "clarification_qa", None) or []
        answered = [
            qa
            for qa in items
            if qa.answer and qa.answer.strip() not in ("", "(unanswered)")
        ]
        if answered:
            out.append((phase_name, answered))
    return out
