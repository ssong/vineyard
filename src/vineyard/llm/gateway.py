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

# Anthropic list pricing, USD per 1M tokens, as (input, output).
# Cache write is 1.25× input; cache read is 0.10× input.
_PRICING_PER_M: dict[str, tuple[float, float]] = {
    "claude-opus-4-7": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (0.80, 4.0),
}


def cost_for_usage(
    role: Role,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Approximate USD cost for a single agent run, based on Anthropic list pricing.

    The Pydantic AI gateway doesn't expose cost on its Usage object, so we
    compute it ourselves. Cache writes are billed at 1.25× the base input rate,
    cache reads at 0.10× — we apply both.
    """
    model = _MODEL_BY_ROLE.get(role)
    pricing = _PRICING_PER_M.get(model) if model else None
    if pricing is None:
        return 0.0
    in_per_m, out_per_m = pricing
    cost = (
        input_tokens * in_per_m
        + cache_write_tokens * in_per_m * 1.25
        + cache_read_tokens * in_per_m * 0.10
        + output_tokens * out_per_m
    ) / 1_000_000
    return cost

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
    retries: int = 4,
) -> Agent[None, T]:
    """Build a Pydantic AI agent with typed output, retries, and gateway routing."""
    return Agent(
        model_for(role),
        output_type=output_type,
        system_prompt=system_prompt,
        retries=retries,
        name=name,
    )
