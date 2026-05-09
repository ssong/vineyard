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
    _configured = True
