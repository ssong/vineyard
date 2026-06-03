"""Backwards-compatible alias for the cloud Outcomes executor.

The ``managed_agents`` executor used to run the *local* Claude Agent SDK
(``claude_agent_sdk.query``), which has no Outcomes support. It now means the
cloud Managed Agents + Outcomes platform (``anthropic.beta.sessions``), where a
separate grader agent scores the build against the stack rubric and the worker
iterates until the verdict is terminal.

Implementation lives in :mod:`vineyard.build.outcomes_exec`; this module keeps
the old import path working.
"""

from vineyard.build.outcomes_exec import OutcomesExecutor

# Old name kept so existing imports / the factory don't break.
ManagedAgentsExecutor = OutcomesExecutor

__all__ = ["ManagedAgentsExecutor", "OutcomesExecutor"]
