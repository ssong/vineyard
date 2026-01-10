"""LLM client wrapper for Claude API."""

import json
import logging
from typing import Any

import anthropic

from src.config import settings

logger = logging.getLogger(__name__)

_client = None


def get_client() -> anthropic.Anthropic:
    """Get or create Anthropic client."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def generate(
    system_prompt: str,
    user_prompt: str,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 4096,
) -> str:
    """Generate text using Claude."""
    client = get_client()

    logger.debug(f"Generating with prompt length: {len(user_prompt)}")

    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    return message.content[0].text


def generate_json(
    system_prompt: str,
    user_prompt: str,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """Generate JSON using Claude."""
    # Append JSON instruction to system prompt
    json_system = (
        system_prompt
        + "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, no explanation, just JSON."
    )

    response = generate(json_system, user_prompt, model, max_tokens)

    # Try to extract JSON from response
    try:
        # Handle potential markdown code blocks
        if response.strip().startswith("```"):
            lines = response.strip().split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.startswith("```json") or line.startswith("```"):
                    in_json = not in_json
                    continue
                if in_json:
                    json_lines.append(line)
            response = "\n".join(json_lines)

        return json.loads(response)

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        logger.debug(f"Response was: {response[:500]}")
        raise ValueError(f"LLM did not return valid JSON: {e}")
