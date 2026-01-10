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
