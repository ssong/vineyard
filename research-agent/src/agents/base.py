"""Base agent class."""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all research agents."""

    name: str = "BaseAgent"

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    @abstractmethod
    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the agent's task.

        Args:
            context: Input context from previous agents

        Returns:
            Output context for next agents
        """
        pass

    def log_start(self, context: dict[str, Any]):
        """Log agent start."""
        self.logger.info(f"{self.name} starting...")

    def log_complete(self, result: dict[str, Any]):
        """Log agent completion."""
        self.logger.info(f"{self.name} complete")
