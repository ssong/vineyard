"""Base agent class for all factory agents."""

import logging
from abc import ABC, abstractmethod
from typing import Any

from src.models import FactoryState

logger = logging.getLogger(__name__)


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
        """Get output from a previous phase."""
        return state.phase_outputs.get(phase)

    def log_start(self):
        """Log agent start."""
        self.logger.info(f"[{self.domain.upper()}] {self.name} starting...")

    def log_complete(self):
        """Log agent completion."""
        self.logger.info(f"[{self.domain.upper()}] {self.name} complete")

    def log_error(self, error: Exception):
        """Log agent error."""
        self.logger.error(f"[{self.domain.upper()}] {self.name} failed: {error}")
