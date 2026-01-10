"""LLM client wrapper for Claude API with token limit handling and smart model selection.

Includes optimizations:
- Prompt caching for system prompts (70-90% cost reduction on cache hits)
- Accurate token counting using Anthropic's tokenizer
- Extended thinking mode for complex reasoning tasks
- Smart truncation that preserves both beginning and end of content
"""

import json
import logging
from typing import Any

import anthropic

from src.config import settings

logger = logging.getLogger(__name__)

_client = None
_tokenizer = None

# Model identifiers
MODEL_OPUS = "claude-opus-4-5-20251101"  # For complex reasoning, synthesis, important decisions
MODEL_SONNET = "claude-sonnet-4-5-20250929"  # For structured tasks, following templates

# Claude model context limits (input + output)
MODEL_LIMITS = {
    MODEL_OPUS: 200000,
    MODEL_SONNET: 200000,
}

# Fallback: Approximate characters per token (used if tokenizer unavailable)
CHARS_PER_TOKEN = 4

# Minimum tokens required for prompt caching (Anthropic requirement)
MIN_CACHE_TOKENS = 1024


def get_client() -> anthropic.Anthropic:
    """Get or create Anthropic client."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def get_tokenizer():
    """Get or create the Anthropic tokenizer for accurate token counting."""
    global _tokenizer
    if _tokenizer is None:
        try:
            _tokenizer = anthropic.Anthropic().messages.count_tokens
            logger.debug("Using Anthropic API for token counting")
        except Exception as e:
            logger.warning(f"Could not initialize tokenizer: {e}. Using estimation.")
            _tokenizer = None
    return _tokenizer


def count_tokens(text: str, model: str = MODEL_SONNET) -> int:
    """Count tokens accurately using Anthropic's tokenizer.

    Falls back to character-based estimation if tokenizer unavailable.
    """
    if not text:
        return 0

    # Try accurate counting first
    try:
        client = get_client()
        result = client.messages.count_tokens(
            model=model,
            messages=[{"role": "user", "content": text}]
        )
        return result.input_tokens
    except Exception as e:
        logger.debug(f"Token counting API failed, using estimation: {e}")
        return len(text) // CHARS_PER_TOKEN


def estimate_tokens(text: str) -> int:
    """Estimate token count from text length (fast, less accurate).

    Uses a conservative 4 chars/token estimate.
    Use count_tokens() for accurate counting when precision matters.
    """
    return len(text) // CHARS_PER_TOKEN


def truncate_smart(
    text: str,
    max_tokens: int,
    model: str = MODEL_SONNET,
    middle_marker: str = "\n\n[... middle content truncated for brevity ...]\n\n"
) -> str:
    """Smart truncation that preserves beginning and end of content.

    Strategy: Keep first 40% and last 40%, cut the middle 20%.
    This preserves context (usually at start) and specific requirements (usually at end).
    """
    current_tokens = count_tokens(text, model)

    if current_tokens <= max_tokens:
        return text

    # Calculate how much we need to keep
    marker_tokens = count_tokens(middle_marker, model)
    available_tokens = max_tokens - marker_tokens

    if available_tokens < 200:
        # Not enough room for smart truncation, fall back to simple truncation
        logger.warning("Insufficient tokens for smart truncation, using simple truncation")
        return _truncate_simple(text, max_tokens)

    # Keep 45% from start and 45% from end (leaves 10% buffer for boundary adjustments)
    start_tokens = int(available_tokens * 0.45)
    end_tokens = int(available_tokens * 0.45)

    # Convert to character positions (approximate)
    total_chars = len(text)
    start_chars = int(total_chars * 0.45)
    end_chars = int(total_chars * 0.45)

    # Extract start portion, break at paragraph/sentence boundary
    start_text = text[:start_chars]
    for sep in ["\n\n", "\n", ". ", " "]:
        break_pos = start_text.rfind(sep)
        if break_pos > start_chars * 0.8:
            start_text = start_text[:break_pos + len(sep)]
            break

    # Extract end portion, break at paragraph/sentence boundary
    end_text = text[-end_chars:]
    for sep in ["\n\n", "\n", ". ", " "]:
        break_pos = end_text.find(sep)
        if break_pos != -1 and break_pos < end_chars * 0.2:
            end_text = end_text[break_pos + len(sep):]
            break

    truncated = start_text + middle_marker + end_text

    logger.warning(
        f"Smart truncated input from ~{current_tokens} to ~{count_tokens(truncated, model)} tokens "
        f"(kept start + end, cut middle)"
    )

    return truncated


def _truncate_simple(
    text: str,
    max_tokens: int,
    suffix: str = "\n\n[Content truncated due to length...]"
) -> str:
    """Simple truncation from the end (fallback method)."""
    # Calculate max characters (using estimation for speed)
    suffix_chars = len(suffix)
    max_chars = (max_tokens * CHARS_PER_TOKEN) - suffix_chars

    truncated = text[:max_chars]

    # Try to break at a sentence or paragraph
    for sep in ["\n\n", "\n", ". ", " "]:
        last_break = truncated.rfind(sep)
        if last_break > max_chars * 0.8:
            truncated = truncated[:last_break]
            break

    return truncated + suffix


# Keep old function name for backward compatibility
def truncate_to_token_limit(
    text: str,
    max_tokens: int,
    suffix: str = "\n\n[Content truncated due to length...]"
) -> str:
    """Truncate text to fit within token limit.

    Note: This uses simple end-truncation for backward compatibility.
    For better results, use truncate_smart() which preserves both ends.
    """
    estimated_tokens = estimate_tokens(text)

    if estimated_tokens <= max_tokens:
        return text

    return _truncate_simple(text, max_tokens, suffix)


def _build_system_with_cache(system_prompt: str, model: str = MODEL_SONNET) -> list[dict]:
    """Build system prompt with cache_control for prompt caching.

    Anthropic's prompt caching reduces costs by 90% for cached content.
    Requires minimum 1024 tokens in the cached block.
    """
    prompt_tokens = estimate_tokens(system_prompt)

    if prompt_tokens >= MIN_CACHE_TOKENS:
        # System prompt is large enough to benefit from caching
        return [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"}
            }
        ]
    else:
        # Too small for caching, use simple string (will be converted by API)
        logger.debug(f"System prompt too small for caching ({prompt_tokens} tokens)")
        return [{"type": "text", "text": system_prompt}]


def generate(
    system_prompt: str,
    user_prompt: str,
    model: str = MODEL_SONNET,
    max_tokens: int = 4096,
    use_extended_thinking: bool = False,
    thinking_budget: int = 10000,
) -> str:
    """Generate text using Claude with token limit handling and prompt caching.

    Args:
        system_prompt: System instructions for the model
        user_prompt: User input/query
        model: Model to use (MODEL_OPUS or MODEL_SONNET)
        max_tokens: Maximum output tokens
        use_extended_thinking: Enable extended thinking for complex reasoning
        thinking_budget: Token budget for thinking (only used if use_extended_thinking=True)

    Returns:
        Generated text response
    """
    client = get_client()

    # Calculate available input tokens
    model_limit = MODEL_LIMITS.get(model, 200000)
    available_input = model_limit - max_tokens - 1000  # Reserve buffer

    # Estimate current usage (use fast estimation for pre-check)
    system_tokens = estimate_tokens(system_prompt)
    user_tokens = estimate_tokens(user_prompt)
    total_input = system_tokens + user_tokens

    logger.debug(
        f"Using {model} | Token estimate: system={system_tokens}, user={user_tokens}, "
        f"total={total_input}, limit={available_input}, extended_thinking={use_extended_thinking}"
    )

    # Truncate user prompt if needed (keep system prompt intact)
    if total_input > available_input:
        available_for_user = available_input - system_tokens
        if available_for_user < 1000:
            raise ValueError(
                f"System prompt too large ({system_tokens} tokens). "
                f"Max available: {available_input}"
            )
        # Use smart truncation for better context preservation
        user_prompt = truncate_smart(user_prompt, available_for_user, model)

    # Build system prompt with cache control
    system_with_cache = _build_system_with_cache(system_prompt, model)

    # Build request parameters
    request_params = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_with_cache,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    # Add extended thinking if requested (for complex reasoning tasks)
    if use_extended_thinking:
        # Anthropic requires max_tokens > budget_tokens
        # Set max_tokens to thinking_budget + original max_tokens for output
        request_params["max_tokens"] = thinking_budget + max_tokens
        request_params["thinking"] = {
            "type": "enabled",
            "budget_tokens": thinking_budget
        }
        logger.debug(f"Extended thinking enabled with budget: {thinking_budget} tokens, max_tokens: {request_params['max_tokens']}")

    try:
        # Use streaming for extended thinking (required for long operations)
        if use_extended_thinking:
            return _generate_with_streaming(client, request_params)

        message = client.messages.create(**request_params)

        # Log cache performance if available
        if hasattr(message, 'usage') and message.usage:
            usage = message.usage
            cache_read = getattr(usage, 'cache_read_input_tokens', 0)
            cache_create = getattr(usage, 'cache_creation_input_tokens', 0)
            if cache_read or cache_create:
                logger.info(
                    f"Prompt cache: read={cache_read}, created={cache_create} tokens"
                )

        return message.content[0].text

    except anthropic.BadRequestError as e:
        if "context_length" in str(e).lower() or "too long" in str(e).lower():
            logger.error(f"Context length exceeded despite estimation: {e}")
            # Try with more aggressive truncation
            user_prompt = truncate_smart(
                user_prompt,
                (available_input - system_tokens) // 2,
                model
            )
            # Rebuild request without extended thinking (reduce token usage)
            request_params["messages"] = [{"role": "user", "content": user_prompt}]
            if use_extended_thinking:
                request_params.pop("thinking", None)
                logger.warning("Disabled extended thinking due to context length issues")

            message = client.messages.create(**request_params)
            return message.content[0].text
        raise


def _generate_with_streaming(client: anthropic.Anthropic, request_params: dict) -> str:
    """Generate response using streaming (required for extended thinking).

    Anthropic requires streaming for operations that may take longer than 10 minutes.
    Extended thinking operations often exceed this threshold.
    """
    text_content = []

    with client.messages.stream(**request_params) as stream:
        for event in stream:
            # Handle content block deltas
            if hasattr(event, 'type'):
                if event.type == 'content_block_delta':
                    delta = event.delta
                    if hasattr(delta, 'text'):
                        text_content.append(delta.text)

        # Get the final message for logging
        final_message = stream.get_final_message()

        # Log cache performance if available
        if hasattr(final_message, 'usage') and final_message.usage:
            usage = final_message.usage
            cache_read = getattr(usage, 'cache_read_input_tokens', 0)
            cache_create = getattr(usage, 'cache_creation_input_tokens', 0)
            if cache_read or cache_create:
                logger.info(
                    f"Prompt cache: read={cache_read}, created={cache_create} tokens"
                )

    # If we collected text from deltas, return it
    if text_content:
        return ''.join(text_content)

    # Fallback: get text from final message content blocks
    if final_message and final_message.content:
        for block in final_message.content:
            if block.type == "text":
                return block.text
        return final_message.content[0].text if final_message.content else ""

    return ""


def generate_json(
    system_prompt: str,
    user_prompt: str,
    model: str = MODEL_SONNET,
    max_tokens: int = 4096,
    use_extended_thinking: bool = False,
    thinking_budget: int = 10000,
) -> dict[str, Any]:
    """Generate JSON using Claude with token limit handling and prompt caching.

    Args:
        system_prompt: System instructions for the model
        user_prompt: User input/query
        model: Model to use (MODEL_OPUS or MODEL_SONNET)
        max_tokens: Maximum output tokens
        use_extended_thinking: Enable extended thinking for complex reasoning
        thinking_budget: Token budget for thinking

    Returns:
        Parsed JSON as dictionary
    """
    json_system = (
        system_prompt
        + "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, no explanation, just JSON."
    )

    response = generate(
        json_system,
        user_prompt,
        model,
        max_tokens,
        use_extended_thinking=use_extended_thinking,
        thinking_budget=thinking_budget
    )

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
