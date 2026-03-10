"""Agent SDK runner for agentic tasks that benefit from iterative tool use.

Uses the Claude Agent SDK to give Claude autonomy over tool-calling loops,
which produces better results for tasks like:
- Code generation (can self-review and iterate)
- QA validation (can adaptively find and fix issues)

Falls back to direct LLM calls if the SDK/CLI is unavailable.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Track whether the SDK is available
_sdk_available: Optional[bool] = None


def _get_api_key() -> str:
    """Lazily get the Anthropic API key from settings."""
    from src.config import settings
    return settings.anthropic_api_key


def is_sdk_available() -> bool:
    """Check if the Claude Agent SDK and CLI are available.

    Verifies both the Python package AND the claude CLI binary,
    since the SDK launches claude as a subprocess.
    """
    global _sdk_available
    if _sdk_available is not None:
        return _sdk_available

    try:
        import claude_agent_sdk  # noqa: F401
    except ImportError:
        _sdk_available = False
        logger.info("Claude Agent SDK not installed, using direct API calls")
        return _sdk_available

    # Verify the claude CLI is actually available
    import shutil
    if shutil.which("claude") is None:
        _sdk_available = False
        logger.info("Claude CLI not found in PATH, Agent SDK disabled")
        return _sdk_available

    _sdk_available = True
    logger.info("Claude Agent SDK and CLI are available")
    return _sdk_available


@dataclass
class AgentResult:
    """Result from an agent SDK query."""
    text: str
    cost_usd: float = 0.0
    turns: int = 0
    session_id: str = ""


async def _run_agent_query(
    prompt: str,
    system_prompt: str,
    tools: list = None,
    model: str = "sonnet",
    max_turns: int = 20,
    max_budget_usd: float = 1.0,
    cwd: str = None,
) -> AgentResult:
    """Run a query using the Claude Agent SDK.

    Args:
        prompt: The task prompt for the agent
        system_prompt: System instructions
        tools: List of MCP tool objects (from @tool decorator)
        model: Model to use (sonnet, opus, haiku)
        max_turns: Maximum conversation turns
        max_budget_usd: Maximum cost budget
        cwd: Working directory for the agent

    Returns:
        AgentResult with the final text output
    """
    from claude_agent_sdk import (
        ClaudeAgentOptions,
        ResultMessage,
        create_sdk_mcp_server,
        query,
    )

    # Build MCP server config from tools
    mcp_servers = {}
    if tools:
        server_config = create_sdk_mcp_server(
            name="vineyard-factory",
            version="1.0.0",
            tools=tools,
        )
        mcp_servers["vineyard-factory"] = server_config

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        model=model,
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        mcp_servers=mcp_servers,
        permission_mode="bypassPermissions",
        cwd=cwd,
        # Disable all built-in tools - only use our custom MCP tools
        tools=["mcp"] if tools else None,
        allowed_tools=[f"mcp__vineyard-factory__*"] if tools else [],
        env={"ANTHROPIC_API_KEY": _get_api_key()},
    )

    result_text = ""
    total_cost = 0.0
    turns = 0
    session_id = ""

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result_text = message.text
            if hasattr(message, "usage"):
                usage = message.usage
                total_cost = usage.get("cost_usd", 0.0) if isinstance(usage, dict) else 0.0
            if hasattr(message, "session_id"):
                session_id = message.session_id
            turns = message.num_turns if hasattr(message, "num_turns") else 0

    return AgentResult(
        text=result_text,
        cost_usd=total_cost,
        turns=turns,
        session_id=session_id,
    )


def run_agent(
    prompt: str,
    system_prompt: str,
    tools: list = None,
    model: str = "sonnet",
    max_turns: int = 20,
    max_budget_usd: float = 1.0,
    cwd: str = None,
) -> AgentResult:
    """Synchronous wrapper for running an Agent SDK query.

    Creates an event loop if needed. Safe to call from sync code.
    """
    try:
        loop = asyncio.get_running_loop()
        # If we're in an async context, create a new thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = pool.submit(
                asyncio.run,
                _run_agent_query(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    tools=tools,
                    model=model,
                    max_turns=max_turns,
                    max_budget_usd=max_budget_usd,
                    cwd=cwd,
                ),
            ).result()
        return result
    except RuntimeError:
        # No running loop, safe to use asyncio.run
        return asyncio.run(
            _run_agent_query(
                prompt=prompt,
                system_prompt=system_prompt,
                tools=tools,
                model=model,
                max_turns=max_turns,
                max_budget_usd=max_budget_usd,
                cwd=cwd,
            )
        )


def run_agent_json(
    prompt: str,
    system_prompt: str,
    tools: list = None,
    model: str = "sonnet",
    max_turns: int = 20,
    max_budget_usd: float = 1.0,
    cwd: str = None,
) -> dict[str, Any]:
    """Run an agent query and parse the result as JSON.

    The prompt should instruct the agent to output JSON as its final message.
    """
    result = run_agent(
        prompt=prompt,
        system_prompt=system_prompt,
        tools=tools,
        model=model,
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        cwd=cwd,
    )

    # Parse JSON from the result text
    text = result.text.strip()

    # Handle markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        json_lines = []
        in_json = False
        for line in lines:
            if line.startswith("```json") or line.startswith("```"):
                in_json = not in_json
                continue
            if in_json:
                json_lines.append(line)
        text = "\n".join(json_lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Agent result was not valid JSON: {e}")
        logger.debug(f"Agent result text: {text[:500]}")
        raise ValueError(f"Agent did not return valid JSON: {e}")
