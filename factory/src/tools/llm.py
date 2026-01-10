"""LLM client wrapper for Claude API with token limit handling and smart model selection."""

import json
import logging
from typing import Any

import anthropic

from src.config import settings

logger = logging.getLogger(__name__)

_client = None

# Model identifiers
MODEL_OPUS = "claude-opus-4-20250514"  # For complex reasoning, synthesis, important decisions
MODEL_SONNET = "claude-sonnet-4-20250514"  # For structured tasks, following templates

# Claude model context limits (input + output)
MODEL_LIMITS = {
    MODEL_OPUS: 200000,
    MODEL_SONNET: 200000,
    "claude-3-5-sonnet-20241022": 200000,
    "claude-3-haiku-20240307": 200000,
}

# Approximate characters per token (conservative estimate for English text)
CHARS_PER_TOKEN = 4


def get_client() -> anthropic.Anthropic:
    """Get or create Anthropic client."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def estimate_tokens(text: str) -> int:
    """Estimate token count from text length.
    
    Uses a conservative 4 chars/token estimate.
    For precise counting, use anthropic.count_tokens() but that requires API call.
    """
    return len(text) // CHARS_PER_TOKEN


def truncate_to_token_limit(
    text: str,
    max_tokens: int,
    suffix: str = "\n\n[Content truncated due to length...]"
) -> str:
    """Truncate text to fit within token limit."""
    estimated_tokens = estimate_tokens(text)
    
    if estimated_tokens <= max_tokens:
        return text
    
    # Calculate max characters (accounting for suffix)
    suffix_chars = len(suffix)
    max_chars = (max_tokens * CHARS_PER_TOKEN) - suffix_chars
    
    # Truncate and add suffix
    truncated = text[:max_chars]
    
    # Try to break at a sentence or paragraph
    for sep in ["\n\n", "\n", ". ", " "]:
        last_break = truncated.rfind(sep)
        if last_break > max_chars * 0.8:  # Keep at least 80% of content
            truncated = truncated[:last_break]
            break
    
    logger.warning(
        f"Truncated input from ~{estimated_tokens} to ~{estimate_tokens(truncated + suffix)} tokens"
    )
    
    return truncated + suffix


def generate(
    system_prompt: str,
    user_prompt: str,
    model: str = MODEL_SONNET,
    max_tokens: int = 8192,
) -> str:
    """Generate text using Claude with token limit handling."""
    client = get_client()
    
    # Calculate available input tokens
    model_limit = MODEL_LIMITS.get(model, 200000)
    available_input = model_limit - max_tokens - 1000  # Reserve buffer
    
    # Estimate current usage
    system_tokens = estimate_tokens(system_prompt)
    user_tokens = estimate_tokens(user_prompt)
    total_input = system_tokens + user_tokens
    
    logger.debug(
        f"Using {model} | Token estimate: system={system_tokens}, user={user_tokens}, "
        f"total={total_input}, limit={available_input}"
    )
    
    # Truncate user prompt if needed (keep system prompt intact)
    if total_input > available_input:
        available_for_user = available_input - system_tokens
        if available_for_user < 1000:
            raise ValueError(
                f"System prompt too large ({system_tokens} tokens). "
                f"Max available: {available_input}"
            )
        user_prompt = truncate_to_token_limit(user_prompt, available_for_user)
    
    try:
        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text
        
    except anthropic.BadRequestError as e:
        if "context_length" in str(e).lower() or "too long" in str(e).lower():
            logger.error(f"Context length exceeded despite estimation: {e}")
            # Try with more aggressive truncation
            user_prompt = truncate_to_token_limit(
                user_prompt, 
                (available_input - system_tokens) // 2
            )
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return message.content[0].text
        raise


def generate_json(
    system_prompt: str,
    user_prompt: str,
    model: str = MODEL_SONNET,
    max_tokens: int = 8192,
) -> dict[str, Any]:
    """Generate JSON using Claude with token limit handling."""
    json_system = (
        system_prompt
        + "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, no explanation, just JSON."
    )

    response = generate(json_system, user_prompt, model, max_tokens)

    try:
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


def generate_code(
    system_prompt: str,
    user_prompt: str,
    model: str = MODEL_SONNET,
    max_tokens: int = 16384,
) -> str:
    """Generate code using Claude with higher token limit.
    
    Uses Sonnet by default as code generation follows clear specs.
    """
    code_system = (
        system_prompt
        + "\n\nGenerate clean, production-ready code. Include comments for complex logic."
    )

    return generate(code_system, user_prompt, model, max_tokens)
