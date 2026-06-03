"""Logfire setup — call once per process at startup."""

import logfire

from vineyard.config import settings

_configured = False


def configure_logfire(service_name: str = "vineyard") -> None:
    global _configured
    if _configured:
        return

    logfire.configure(
        token=settings.logfire_token or None,
        service_name=service_name,
        send_to_logfire="if-token-present",
    )
    logfire.instrument_pydantic_ai()
    # The managed-agents (Outcomes) executor talks to the Anthropic cloud API,
    # which the Pydantic AI Gateway can't proxy. Instrument the SDK directly so
    # Outcomes runs still emit spans + token usage + cost to the same Logfire
    # project as the rest of the pipeline.
    try:
        logfire.instrument_anthropic()
    except Exception:  # pragma: no cover - instrumentation is best-effort
        pass
    _configured = True
