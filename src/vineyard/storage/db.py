"""SQLite-backed run store. State is persisted as Pydantic JSON blobs."""

from __future__ import annotations

import shutil
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from vineyard.config import settings
from vineyard.models import PhaseStatus, RunState

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    slug TEXT NOT NULL,
    product_name TEXT NOT NULL,
    stack TEXT NOT NULL,
    current_phase TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    cost_usd REAL DEFAULT 0,
    state_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs (status);
"""


class RunStore:
    def __init__(self, db_path: Path | None = None):
        settings.ensure_dirs()
        self.db_path = db_path or settings.db_path()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save(self, state: RunState) -> None:
        current_status = state.phase_statuses.get(state.current_phase.value, PhaseStatus.PENDING)
        payload = state.model_dump_json()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, slug, product_name, stack, current_phase, status,
                                  started_at, completed_at, cost_usd, state_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    current_phase = excluded.current_phase,
                    status        = excluded.status,
                    completed_at  = excluded.completed_at,
                    cost_usd      = excluded.cost_usd,
                    state_json    = excluded.state_json
                """,
                (
                    state.run_id,
                    state.handoff.prd_input.slug,
                    state.handoff.prd_input.name,
                    state.handoff.build_preferences.stack,
                    state.current_phase.value,
                    current_status.value if isinstance(current_status, PhaseStatus) else str(current_status),
                    state.started_at.isoformat(),
                    state.completed_at.isoformat() if state.completed_at else None,
                    state.cost_usd,
                    payload,
                ),
            )

    def load(self, run_id: str) -> RunState | None:
        with self._connect() as conn:
            row = conn.execute("SELECT state_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if not row:
            return None
        return RunState.model_validate_json(row["state_json"])

    def list(self, status_filter: str | None = None) -> list[dict]:
        sql = (
            "SELECT run_id, slug, product_name, stack, current_phase, status, "
            "started_at, completed_at, cost_usd FROM runs"
        )
        params: tuple = ()
        if status_filter:
            sql += " WHERE status = ?"
            params = (status_filter,)
        sql += " ORDER BY started_at DESC"
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def delete(self, run_id: str, *, remove_files: bool = True) -> bool:
        """Delete a run from the DB and (by default) its on-disk directory.

        Returns True if a row was actually removed.
        """
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
            removed = cur.rowcount > 0
        if remove_files:
            run_dir = settings.runs_dir() / run_id
            if run_dir.exists():
                shutil.rmtree(run_dir, ignore_errors=True)
        return removed

    def failed_runs(self) -> list[dict]:
        return self.list(status_filter=PhaseStatus.FAILED.value)

    def awaiting_approval(self) -> list[dict]:
        return self.list(status_filter=PhaseStatus.AWAITING_APPROVAL.value)
