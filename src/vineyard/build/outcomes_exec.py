"""BUILD executor backed by Anthropic Managed Agents + Outcomes (cloud).

Defines the build as an *outcome*: a deliverable description + the stack rubric.
A separate grader agent scores the generated codebase against the rubric in an
isolated context and the worker iterates until the verdict is terminal
(``satisfied`` / ``max_iterations_reached`` / ``failed`` / ``interrupted``).

Lifecycle (all torn down in ``finally``):

    ensure agent → ensure environment → create session
      → (fix mode) upload prior build_dir + mount into sandbox
      → define_outcome(description=user prompt, rubric=stack rubric)
      → stream events → emit to TUI, accumulate usage, capture terminal verdict
      → download output files into build_dir
    finally: delete session (+ environment) — errors warned, never raised
"""

from __future__ import annotations

import logfire

from vineyard.build.executor import BuildContext
from vineyard.build.outcomes_client import (
    SANDBOX_OUTPUT_PREFIX,
    OutcomesClient,
)
from vineyard.build.prompts import compose_system_prompt, compose_user_prompt
from vineyard.config import settings
from vineyard.llm.gateway import Role, cost_for_usage
from vineyard.models import BuildOutput, GeneratedFile

_LANG_BY_EXT: dict[str, str] = {
    ".py": "python", ".rb": "ruby", ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".css": "css", ".html": "html",
    ".json": "json", ".md": "markdown", ".yml": "yaml", ".yaml": "yaml",
    ".sql": "sql", ".sh": "shell", ".toml": "toml", ".env": "dotenv",
    ".tf": "hcl", ".tfvars": "hcl", ".tcss": "css",
}

_TERMINAL = {"satisfied", "max_iterations_reached", "failed", "interrupted"}
_GRADER_BY_VERDICT = {
    "satisfied": "satisfied",
    "max_iterations_reached": "max_iterations_reached",
    "failed": "failed",
    "interrupted": "failed",
}


class OutcomesExecutor:
    async def run(self, ctx: BuildContext, *, client: OutcomesClient | None = None) -> BuildOutput:
        build_dir = ctx.build_dir
        build_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        client = client or OutcomesClient.from_settings()
        session_id: str | None = None
        environment_id: str | None = None
        created_env = False

        with logfire.span("build.outcomes", run_id=ctx.state.run_id):
            try:
                agent_id = await client.ensure_agent(
                    model=settings.outcomes_model,
                    name=f"vineyard-{ctx.profile.name}",
                    system=compose_system_prompt(ctx),
                )
                pre_env = (
                    settings.outcomes_environment_id
                    if settings.outcomes_reuse_environment
                    else ""
                )
                environment_id = await client.ensure_environment(
                    name=f"vineyard-{ctx.state.run_id[:8]}"
                )
                created_env = environment_id != pre_env
                session_id = await client.create_session(
                    agent_id=agent_id,
                    environment_id=environment_id,
                    title=f"{ctx.state.handoff.prd_input.name} · build",
                )

                if ctx.attempt > 1 and ctx.prior_build is not None:
                    await self._upload_prior_files(client, session_id, ctx)

                await client.send_define_outcome(
                    session_id=session_id,
                    description=compose_user_prompt(ctx),
                    rubric_text=ctx.profile.rubric(),
                    max_iterations=settings.outcomes_max_iterations,
                )
                verdict, explanation, iteration, narration, usage = await self._consume(
                    client, session_id, ctx
                )
                files = await self._download(client, session_id, build_dir)
            finally:
                await self._teardown(client, session_id, environment_id, created_env, ctx)

        cost = cost_for_usage(
            _role_for_model(settings.outcomes_model),
            input_tokens=usage["input"],
            output_tokens=usage["output"],
            cache_read_tokens=usage["cache_read"],
            cache_write_tokens=usage["cache_write"],
        )
        return _to_build_output(verdict, explanation, iteration, files, cost, narration)

    # -- streaming ----------------------------------------------------------

    async def _consume(self, client, session_id, ctx):
        verdict = "needs_revision"
        explanation = ""
        iteration = 0
        narration: list[str] = []
        usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}

        async for event in client.stream_events(session_id=session_id):
            etype = getattr(event, "type", "")

            if etype == "agent.message":
                text = " ".join(
                    getattr(b, "text", "") for b in getattr(event, "content", [])
                ).strip()
                if text:
                    narration.append(text)
                    await ctx.emit("agent", _truncate(text))

            elif etype == "agent.tool_use":
                await ctx.emit("tool", _format_tool_use(event))

            elif etype == "span.model_request_end":
                mu = getattr(event, "model_usage", None)
                if mu is not None:
                    usage["input"] += getattr(mu, "input_tokens", 0) or 0
                    usage["output"] += getattr(mu, "output_tokens", 0) or 0
                    usage["cache_read"] += getattr(mu, "cache_read_input_tokens", 0) or 0
                    usage["cache_write"] += getattr(mu, "cache_creation_input_tokens", 0) or 0

            elif etype == "span.outcome_evaluation_end":
                verdict = getattr(event, "result", verdict)
                explanation = getattr(event, "explanation", "") or explanation
                iteration = getattr(event, "iteration", iteration)
                await ctx.emit(
                    "agent" if verdict == "needs_revision" else "phase",
                    f"grading: iter {iteration} · {verdict}",
                )

            elif etype == "session.error":
                msg = getattr(event, "message", None) or str(event)
                await ctx.emit("error", f"session error: {msg}")

            elif etype in ("session.status_idle", "session.status_terminated"):
                if verdict in _TERMINAL:
                    break

        return verdict, explanation, iteration, narration, usage

    # -- fix-mode upload ----------------------------------------------------

    async def _upload_prior_files(self, client, session_id, ctx) -> None:
        build_dir = ctx.build_dir
        n = 0
        for p in sorted(build_dir.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(build_dir).as_posix()
            try:
                file_id = await client.upload_file(path=p)
                await client.mount_file(
                    session_id=session_id,
                    file_id=file_id,
                    mount_path=f"{SANDBOX_OUTPUT_PREFIX}{rel}",
                )
                n += 1
            except Exception as exc:  # pragma: no cover - network
                await ctx.emit("error", f"fix-mode upload failed for {rel}: {exc}")
        await ctx.emit("agent", f"fix mode: re-uploaded {n} prior file(s) for surgical edits")

    # -- download -----------------------------------------------------------

    async def _download(self, client, session_id, build_dir) -> list[GeneratedFile]:
        files: list[GeneratedFile] = []
        for file_id, rel in await client.list_output_files(session_id=session_id):
            target = (build_dir / rel).resolve()
            if not target.is_relative_to(build_dir.resolve()):
                continue  # path traversal guard
            target.parent.mkdir(parents=True, exist_ok=True)
            data = await client.download_file(file_id=file_id)
            target.write_bytes(data)
            ext = target.suffix
            files.append(GeneratedFile(path=rel, language=_LANG_BY_EXT.get(ext, "text")))
        return files

    # -- teardown -----------------------------------------------------------

    async def _teardown(self, client, session_id, environment_id, created_env, ctx) -> None:
        if session_id is not None:
            try:
                await client.delete_session(session_id=session_id)
            except Exception as exc:  # pragma: no cover
                await ctx.emit("error", f"teardown: session delete failed: {exc}")
        # Only delete an environment we created this run; never a reused one.
        if created_env and environment_id is not None and not settings.outcomes_reuse_environment:
            try:
                await client.delete_environment(environment_id=environment_id)
            except Exception as exc:  # pragma: no cover
                await ctx.emit("error", f"teardown: env delete failed: {exc}")


# -- pure helpers (unit-testable) -------------------------------------------


def _to_build_output(verdict, explanation, iteration, files, cost, narration) -> BuildOutput:
    grader = _GRADER_BY_VERDICT.get(verdict)
    if grader is None:
        grader = "satisfied" if files else "needs_revision"
    summary = "\n\n".join(narration)[-2000:] or "(no narration captured)"
    return BuildOutput(
        files=files,
        summary=summary,
        grader_result=grader,
        grader_explanation=explanation or "(no grader explanation)",
        iterations=int(iteration) + 1,
        cost_usd=cost,
    )


def _role_for_model(model: str) -> Role:
    m = model.lower()
    if "haiku" in m:
        return "fast"
    if "sonnet" in m:
        return "code"
    return "plan"  # opus / default


def _truncate(text: str, limit: int = 200) -> str:
    text = text.strip().replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _format_tool_use(event) -> str:
    name = getattr(event, "name", "tool")
    args = getattr(event, "input", None) or {}
    for key in ("file_path", "path"):
        if key in args:
            return f"{name} {args[key]}"
    if "pattern" in args:
        return f"{name} {args['pattern']!r}"
    if "command" in args:
        return f"{name} {str(args['command'])[:80]}"
    return name
