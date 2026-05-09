"""Pydantic AI Gateway provider — single entry point for LLM calls.

All Anthropic traffic flows through `gateway-us.pydantic.dev`, which automatically
sends OTLP traces to Logfire (configured separately in `logfire.py`).
"""

from typing import Literal, TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.gateway import gateway_provider

from vineyard.config import settings

Role = Literal["plan", "code", "judge", "fast"]

# Maps a high-level role to a concrete Claude model. Tweak in one place.
_MODEL_BY_ROLE: dict[Role, str] = {
    "plan": "claude-opus-4-7",
    "code": "claude-sonnet-4-6",
    "judge": "claude-opus-4-7",
    "fast": "claude-haiku-4-5-20251001",
}

T = TypeVar("T", bound=BaseModel)


def model_for(role: Role) -> AnthropicModel:
    """Build an AnthropicModel that routes through the gateway."""
    if not settings.pydantic_ai_gateway_api_key:
        raise RuntimeError(
            "VINEYARD_PYDANTIC_AI_GATEWAY_API_KEY is not set. "
            "Run `vineyard config pydantic-ai-gateway-api-key pylf_…` or export the env var."
        )
    provider = gateway_provider(
        "anthropic",
        api_key=settings.pydantic_ai_gateway_api_key,
    )
    return AnthropicModel(_MODEL_BY_ROLE[role], provider=provider)


def build_agent(
    *,
    role: Role,
    output_type: type[T],
    system_prompt: str,
    name: str,
    retries: int = 2,
) -> Agent[None, T]:
    """Build a Pydantic AI agent with typed output, retries, and gateway routing."""
    return Agent(
        model_for(role),
        output_type=output_type,
        system_prompt=system_prompt,
        retries=retries,
        name=name,
    )
