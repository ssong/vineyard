"""Thin, mockable async wrapper over the Anthropic Managed Agents (Outcomes) API.

This is the ONLY module that imports ``anthropic`` and instruments it with
Logfire. The executor (`outcomes_exec.py`) and its tests talk to this wrapper,
so they're insulated from the SDK surface and trivially mockable.

The Managed Agents endpoints can't be proxied through the Pydantic AI Gateway
(it only proxies model-inference), so we instrument the SDK directly with
``logfire.instrument_anthropic()`` — that keeps spans + token usage + cost in
the same Logfire project as the rest of the pipeline.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from vineyard.config import settings

# Sandbox path the stack rubrics tell the agent to write outputs to.
SANDBOX_OUTPUT_PREFIX = "/mnt/session/outputs/"

_BETA_HEADER = "managed-agents-2026-04-01"
_instrumented = False


class OutcomesClient:
    """Async wrapper around ``anthropic`` ``beta.{agents,environments,sessions,files}``."""

    def __init__(self, client: Any) -> None:
        self._c = client

    @classmethod
    def from_settings(cls) -> OutcomesClient:
        """Build a client from settings, instrumenting Logfire once.

        Raises a clear error when the API key is missing, mirroring
        ``llm.gateway.model_for``.
        """
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "VINEYARD_ANTHROPIC_API_KEY is not set. "
                "Run `vineyard config anthropic-api-key sk-ant-…` or export the env var. "
                "The managed_agents (Outcomes) executor needs it."
            )
        import anthropic  # lazy — keeps module import cheap

        global _instrumented
        if not _instrumented:
            try:
                import logfire

                logfire.instrument_anthropic()
            except Exception:  # pragma: no cover - best effort
                pass
            _instrumented = True

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        return cls(client)

    # -- agent / environment / session lifecycle ----------------------------

    async def ensure_agent(self, *, model: str, name: str, system: str) -> str:
        """Reuse a pre-created agent if configured, else create one."""
        if settings.outcomes_agent_id:
            return settings.outcomes_agent_id
        agent = await self._c.beta.agents.create(
            model=model,
            name=name,
            system=system,
            tools=[{"type": "agent_toolset_20260401"}],
        )
        return agent.id

    async def ensure_environment(self, *, name: str) -> str:
        """Reuse the configured environment if set, else create a cloud one."""
        if settings.outcomes_reuse_environment and settings.outcomes_environment_id:
            return settings.outcomes_environment_id
        env = await self._c.beta.environments.create(name=name)
        return env.id

    async def create_session(
        self, *, agent_id: str, environment_id: str, title: str
    ) -> str:
        session = await self._c.beta.sessions.create(
            agent={"agent_id": agent_id},
            environment_id=environment_id,
            title=title,
        )
        return session.id

    async def send_define_outcome(
        self,
        *,
        session_id: str,
        description: str,
        rubric_text: str,
        max_iterations: int,
    ) -> None:
        await self._c.beta.sessions.events.send(
            session_id,
            events=[
                {
                    "type": "user.define_outcome",
                    "description": description,
                    "rubric": {"type": "text", "content": rubric_text[:262_144]},
                    "max_iterations": max_iterations,
                }
            ],
        )

    async def stream_events(self, *, session_id: str) -> AsyncIterator[Any]:
        stream = await self._c.beta.sessions.events.stream(session_id)
        async for event in stream:
            yield event

    # -- file I/O -----------------------------------------------------------

    async def list_output_files(self, *, session_id: str) -> list[tuple[str, str]]:
        """Return ``(file_id, relative_path)`` for every file under the outputs dir."""
        out: list[tuple[str, str]] = []
        page = await self._c.beta.sessions.resources.list(session_id)
        async for resource in page:
            if getattr(resource, "type", None) != "file":
                continue
            mount = getattr(resource, "mount_path", "") or ""
            rel = mount.removeprefix(SANDBOX_OUTPUT_PREFIX).lstrip("/")
            if rel:
                out.append((resource.file_id, rel))
        return out

    async def download_file(self, *, file_id: str) -> bytes:
        resp = await self._c.beta.files.download(file_id)
        return await resp.read()

    async def upload_file(self, *, path: Path) -> str:
        """Upload a local file, returning its ``file_id``."""
        with path.open("rb") as fh:
            meta = await self._c.beta.files.upload(file=fh)
        return meta.id

    async def mount_file(
        self, *, session_id: str, file_id: str, mount_path: str
    ) -> None:
        await self._c.beta.sessions.resources.add(
            session_id, file_id=file_id, type="file", mount_path=mount_path
        )

    # -- teardown -----------------------------------------------------------

    async def delete_session(self, *, session_id: str) -> None:
        await self._c.beta.sessions.delete(session_id)

    async def delete_environment(self, *, environment_id: str) -> None:
        await self._c.beta.environments.delete(environment_id)
