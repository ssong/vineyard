"""Base agent class for all factory agents."""

import logging
from abc import ABC, abstractmethod
from dataclasses import is_dataclass
from typing import Any, Optional

from src.models import FactoryState

logger = logging.getLogger(__name__)

# Mapping of phase names to their output dataclass types
# This allows get_previous_output to reconstruct proper types from dicts
_OUTPUT_TYPE_MAP: dict[str, type] = {}


def _register_output_types():
    """Register output type mappings (called lazily to avoid circular imports)."""
    global _OUTPUT_TYPE_MAP
    if _OUTPUT_TYPE_MAP:
        return

    from src.models.outputs import (
        ResearchEnrichmentOutput,
        DesignOutput,
        SpecOutput,
        BuildOutput,
        LaunchPrepOutput,
        LaunchOutput,
        GrowthOutput,
        UserPersona,
        CompetitorFeatureMatrix,
        SEOStrategy,
        FeatureSpec,
        APIEndpoint,
        DatabaseTable,
        EngineeringTask,
        GeneratedFile,
        EmailSequence,
        SocialContent,
        ProductHuntListing,
        GrowthExperiment,
    )

    _OUTPUT_TYPE_MAP = {
        "research_enrichment": ResearchEnrichmentOutput,
        "design": DesignOutput,
        "spec": SpecOutput,
        # Note: "build" is excluded because it stores a composite dict {"code": {...}, "test": {...}, ...}
        # rather than a BuildOutput dataclass. Access via build.get("code", {}).get("files", [])
        "launch_prep": LaunchPrepOutput,
        "launch": LaunchOutput,
        "growth": GrowthOutput,
    }


def _reconstruct_dataclass(data: dict, cls: type) -> Any:
    """Reconstruct a dataclass from a dict, handling nested dataclasses."""
    if not is_dataclass(cls) or isinstance(cls, type) is False:
        return data

    import dataclasses
    from typing import get_type_hints, get_origin, get_args

    # Get type hints for the class
    try:
        hints = get_type_hints(cls)
    except Exception:
        hints = {}

    kwargs = {}
    for field in dataclasses.fields(cls):
        field_name = field.name
        if field_name not in data:
            continue

        value = data[field_name]
        field_type = hints.get(field_name, field.type)

        # Handle list of dataclasses
        origin = get_origin(field_type)
        if origin is list and value:
            args = get_args(field_type)
            if args and is_dataclass(args[0]):
                value = [_reconstruct_dataclass(item, args[0]) for item in value if isinstance(item, dict)]

        # Handle nested dataclass
        elif is_dataclass(field_type) and isinstance(value, dict):
            value = _reconstruct_dataclass(value, field_type)

        kwargs[field_name] = value

    try:
        return cls(**kwargs)
    except Exception as e:
        logger.warning(f"Failed to reconstruct {cls.__name__}: {e}")
        return data


class BaseAgent(ABC):
    """Base class for all factory agents."""

    name: str = "BaseAgent"
    domain: str = "base"

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    @abstractmethod
    def run(self, state: FactoryState) -> dict[str, Any]:
        """
        Execute the agent's task.

        Args:
            state: Current factory state with handoff and previous outputs

        Returns:
            Output dictionary for this phase
        """
        pass

    def get_previous_output(self, state: FactoryState, phase: str) -> Any:
        """
        Get output from a previous phase.

        If the output is a dict and we know the expected type for this phase,
        reconstruct the proper dataclass to ensure attribute access works.
        """
        output = state.phase_outputs.get(phase)

        if output is None:
            return None

        # If already a dataclass, return as-is
        if is_dataclass(output) and not isinstance(output, type):
            return output

        # If it's a dict, try to reconstruct the proper type
        if isinstance(output, dict):
            _register_output_types()
            output_cls = _OUTPUT_TYPE_MAP.get(phase)
            if output_cls:
                return _reconstruct_dataclass(output, output_cls)

        return output

    def log_start(self):
        """Log agent start."""
        self.logger.info(f"[{self.domain.upper()}] {self.name} starting...")

    def log_complete(self):
        """Log agent completion."""
        self.logger.info(f"[{self.domain.upper()}] {self.name} complete")

    def log_error(self, error: Exception):
        """Log agent error."""
        self.logger.error(f"[{self.domain.upper()}] {self.name} failed: {error}")

    # =========================================================================
    # Task Tracking Methods
    # =========================================================================

    def start_task(
        self,
        state: FactoryState,
        task_id: str,
        description: str,
        feedback_incorporated: str | None = None,
    ) -> bool:
        """
        Mark a Linear task as in-progress and add start comment.
        
        Args:
            state: Factory state with Linear tracking info
            task_id: Linear issue ID for the task
            description: Description of what's being started
            feedback_incorporated: Optional summary of operator feedback being used
            
        Returns:
            True if update successful
        """
        from src.tools import linear
        
        if not task_id or not state.linear_team_id:
            return False
        
        # Transition to in-progress
        success = linear.start_issue(task_id, state.linear_team_id)
        
        # Add start comment
        if feedback_incorporated:
            comment = f"🚀 **Starting**: {description}\n\n📝 **Incorporating feedback**: {feedback_incorporated}"
        else:
            comment = f"🚀 **Starting**: {description}"
        
        linear.add_comment(task_id, comment)
        
        self.logger.info(f"Started task {task_id}: {description}")
        return success

    def complete_task(
        self,
        state: FactoryState,
        task_id: str,
        summary: str,
        output_links: list[str] | None = None,
    ) -> bool:
        """
        Mark a Linear task as done with summary comment.
        
        Args:
            state: Factory state with Linear tracking info
            task_id: Linear issue ID for the task
            summary: Summary of what was accomplished
            output_links: Optional list of output artifact URLs to attach
            
        Returns:
            True if update successful
        """
        from src.tools import linear
        
        if not task_id or not state.linear_team_id:
            return False
        
        # Transition to done
        success = linear.complete_issue(task_id, state.linear_team_id)
        
        # Add completion comment
        comment = f"✅ **Completed**\n\n{summary}"
        
        if output_links:
            comment += "\n\n**Outputs:**\n"
            comment += "\n".join([f"- {link}" for link in output_links])
        
        linear.add_comment(task_id, comment)
        
        self.logger.info(f"Completed task {task_id}")
        return success

    def fail_task(
        self,
        state: FactoryState,
        task_id: str,
        error: str,
        operator_name: str = "sang",
    ) -> bool:
        """
        Mark a Linear task as failed and tag operator.
        
        Args:
            state: Factory state with Linear tracking info
            task_id: Linear issue ID for the task
            error: Error message explaining the failure
            operator_name: Operator to tag (default: sang)
            
        Returns:
            True if update successful
        """
        from src.tools import linear
        
        if not task_id or not state.linear_team_id:
            return False
        
        # Add failed label
        labels = linear.ensure_labels(state.linear_team_id, ["failed"])
        if "failed" in labels:
            linear._add_label_to_issue(task_id, labels["failed"])
        
        # Add failure comment with operator mention
        error_snippet = error[:1500] if len(error) > 1500 else error
        body = f"""## ❌ Task Failed

**Error:**
```
{error_snippet}
```

Please review and advise on next steps."""
        
        linear.mention_user_in_comment(task_id, operator_name, body)
        
        self.logger.error(f"Task {task_id} failed: {error[:100]}...")
        return True

    def get_task_feedback(
        self,
        state: FactoryState,
        task_id: str,
    ) -> list[str]:
        """
        Read operator comments from a task issue for incorporating feedback.
        
        Returns comments from the operator (not from the automation),
        newest first.
        
        Args:
            state: Factory state
            task_id: Linear issue ID for the task
            
        Returns:
            List of comment bodies from the operator
        """
        from src.tools import linear
        
        if not task_id:
            return []
        
        comments = linear.get_issue_comments(task_id)
        
        # Filter to human comments (exclude automation comments)
        # Automation comments typically start with emojis like 🚀, ✅, 📝
        automation_prefixes = ("🚀", "✅", "❌", "📝", "🔄", "⏸️", "**Blocked**", "**Starting**", "**Completed**")
        
        feedback = []
        for comment in comments:
            body = comment.get("body", "").strip()
            user_name = comment.get("user", {}).get("name", "").lower()
            
            # Skip automation comments
            if any(body.startswith(prefix) for prefix in automation_prefixes):
                continue
            
            # Skip comments from vineyard (automation user)
            if "vineyard" in user_name:
                continue
            
            if body:
                feedback.append(body)
        
        return feedback

    def incorporate_feedback(self, feedback: list[str]) -> str | None:
        """
        Summarize feedback comments for incorporation into task execution.
        
        Args:
            feedback: List of comment bodies from operator
            
        Returns:
            Summary string for task execution, or None if no feedback
        """
        if not feedback:
            return None
        
        # Take the most recent feedback (first in list since sorted newest first)
        # Could be enhanced to summarize multiple comments if needed
        return feedback[0][:500] if feedback[0] else None

