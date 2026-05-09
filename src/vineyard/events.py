"""Event callback type shared by the runner and BUILD executors.

The TUI subscribes to these to surface fine-grained progress (tool calls,
agent narration, phase transitions). The CLI ignores them.

Callbacks may be sync or async — call sites that may await use ``emit_event``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

EventCallback = Callable[[str, str], Awaitable[None] | None]


async def emit_event(cb: EventCallback | None, kind: str, text: str) -> None:
    if cb is None:
        return
    result = cb(kind, text)
    if result is not None:
        await result
