"""Local persistence: SQLite for runs, filesystem for outputs."""

from vineyard.storage.db import RunStore

__all__ = ["RunStore"]
