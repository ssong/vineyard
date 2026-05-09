"""BUILD-phase executors.

Two executors are wired up:
- ``pydantic_ai`` (default): a Pydantic AI ``Agent`` with file-system tools that
  generates the codebase in-process, routed through the Pydantic AI Gateway.
- ``managed_agents`` (beta): the Anthropic Claude Agent SDK, intended to leverage
  Managed Agents + Outcomes for long-horizon code generation.

Pick one via ``Handoff.executor`` (defaults to ``pydantic_ai``) or the
``--executor`` CLI flag / TUI toggle.
"""

from vineyard.build.executor import BuildContext, Executor, get_executor

__all__ = ["BuildContext", "Executor", "get_executor"]
