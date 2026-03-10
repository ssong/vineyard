"""Persistent state storage for factory execution.

Provides file-based persistence for development and Redis for production.
State is automatically persisted after each phase update.
"""

import json
import logging
import os
import re
import stat
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.models import FactoryHandoff, FactoryState, Phase, PhaseStatus

logger = logging.getLogger(__name__)

# Storage backend: "file" or "redis"
STORAGE_BACKEND = os.getenv("FACTORY_STORAGE_BACKEND", "file")

# File storage path - use a more secure default than /tmp
# In production, set FACTORY_STATE_DIR to a dedicated directory with restricted permissions
DEFAULT_STATE_DIR = os.path.expanduser("~/.vineyard-factory/state")
STATE_DIR = Path(os.getenv("FACTORY_STATE_DIR", DEFAULT_STATE_DIR))

# Redis connection (optional)
REDIS_URL = os.getenv("REDIS_URL")

# UUID pattern for execution IDs
UUID_PATTERN = re.compile(
    r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$',
    re.IGNORECASE
)


def _is_valid_execution_id(execution_id: str) -> bool:
    """
    Validate that execution_id is a valid UUID format.

    This prevents path traversal attacks by ensuring the ID
    can only contain hexadecimal characters and hyphens.
    """
    if not execution_id or not isinstance(execution_id, str):
        return False

    if len(execution_id) != 36:
        return False

    if not UUID_PATTERN.match(execution_id):
        return False

    # Additional validation: try to parse as UUID
    try:
        uuid.UUID(execution_id)
        return True
    except (ValueError, TypeError):
        return False


def _ensure_state_dir():
    """
    Ensure state directory exists with secure permissions.

    Creates the directory with mode 0700 (owner-only access).
    """
    if not STATE_DIR.exists():
        STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        logger.info(f"Created state directory: {STATE_DIR}")
    else:
        # Verify the directory has secure permissions
        current_mode = STATE_DIR.stat().st_mode
        if current_mode & (stat.S_IRWXG | stat.S_IRWXO):
            logger.warning(
                f"State directory {STATE_DIR} has insecure permissions. "
                f"Consider running: chmod 700 {STATE_DIR}"
            )


def _state_file_path(execution_id: str) -> Optional[Path]:
    """
    Get path to state file with path traversal protection.

    Returns None if execution_id is invalid.
    """
    # Validate execution ID format
    if not _is_valid_execution_id(execution_id):
        logger.warning(f"Invalid execution ID format rejected: {execution_id[:50] if execution_id else 'None'}...")
        return None

    # Construct path
    filepath = STATE_DIR / f"{execution_id}.json"

    # Verify the resolved path is within STATE_DIR (defense in depth)
    try:
        resolved = filepath.resolve()
        state_dir_resolved = STATE_DIR.resolve()

        if not str(resolved).startswith(str(state_dir_resolved)):
            logger.error(f"Path traversal attempt detected: {execution_id[:50]}...")
            return None
    except (OSError, ValueError) as e:
        logger.error(f"Path resolution error: {e}")
        return None

    return filepath


def _serialize_phase_outputs(outputs: dict) -> dict:
    """Serialize phase outputs, converting Pydantic models and dataclasses to dicts."""
    from dataclasses import asdict, is_dataclass

    def _convert(value):
        """Convert a single value to JSON-serializable form."""
        if is_dataclass(value) and not isinstance(value, type):
            return asdict(value)
        elif hasattr(value, "model_dump"):
            return value.model_dump()
        elif hasattr(value, "dict"):
            return value.dict()
        elif isinstance(value, dict):
            return {k: _convert(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [_convert(v) for v in value]
        else:
            return value

    return {key: _convert(value) for key, value in outputs.items()}


def _serialize_state(state: FactoryState) -> dict:
    """Serialize FactoryState to JSON-compatible dict."""
    return {
        "execution_id": state.execution_id,
        "handoff": _serialize_handoff(state.handoff),
        "current_phase": state.current_phase.value,
        "phase_statuses": {k: v.value if isinstance(v, PhaseStatus) else v
                          for k, v in state.phase_statuses.items()},
        "phase_outputs": _serialize_phase_outputs(state.phase_outputs),
        "checkpoints_cleared": state.checkpoints_cleared,
        "linear_issues": state.linear_issues,
        "linear_phase_issues": state.linear_phase_issues,
        "linear_team_id": state.linear_team_id,
        "slack_channels": state.slack_channels,
        "slack_qa_thread_ts": state.slack_qa_thread_ts,
        "errors": state.errors,
        "started_at": state.started_at.isoformat(),
        "last_updated_at": state.last_updated_at.isoformat(),
        "completed_at": state.completed_at.isoformat() if state.completed_at else None,
    }


def _serialize_handoff(handoff: FactoryHandoff) -> dict:
    """Serialize FactoryHandoff to dict."""
    return {
        "handoff_id": handoff.handoff_id,
        "triggered_at": handoff.triggered_at.isoformat(),
        "triggered_by": handoff.triggered_by,
        "linear_project_id": handoff.linear_project_id,
        "linear_project_url": handoff.linear_project_url,
        "prd_input": {
            "name": handoff.prd_input.name,
            "slug": handoff.prd_input.slug,
            "prd_text": handoff.prd_input.prd_text,
            "submitted_by": handoff.prd_input.submitted_by,
            "tech_stack_preference": handoff.prd_input.tech_stack_preference,
            "additional_context": handoff.prd_input.additional_context,
        },
        "build_preferences": {
            "tech_stack": handoff.build_preferences.tech_stack,
            "hosting_preference": handoff.build_preferences.hosting_preference,
            "database_preference": handoff.build_preferences.database_preference,
            "auth_preference": handoff.build_preferences.auth_preference,
            "payments_preference": handoff.build_preferences.payments_preference,
        },
        "approval_checkpoints": handoff.approval_checkpoints,
    }


def _deserialize_state(data: dict) -> FactoryState:
    """Deserialize dict to FactoryState."""
    from src.models import (
        BuildPreferences,
        FactoryHandoff,
        PRDInput,
    )

    handoff_data = data["handoff"]

    # Handle old state files gracefully
    if "prd_input" not in handoff_data:
        raise ValueError(
            "State file uses old format (pre-PRD redesign). "
            "Cannot load states from the research-agent era."
        )

    prd_data = handoff_data["prd_input"]
    prd_input = PRDInput(
        name=prd_data["name"],
        slug=prd_data["slug"],
        prd_text=prd_data["prd_text"],
        submitted_by=prd_data["submitted_by"],
        tech_stack_preference=prd_data.get("tech_stack_preference"),
        additional_context=prd_data.get("additional_context"),
    )

    # Deserialize build preferences
    bp_data = handoff_data.get("build_preferences", {})
    if bp_data:
        defaults = BuildPreferences()
        build_prefs = BuildPreferences(
            tech_stack=bp_data.get("tech_stack", defaults.tech_stack),
            hosting_preference=bp_data.get("hosting_preference", defaults.hosting_preference),
            database_preference=bp_data.get("database_preference", defaults.database_preference),
            auth_preference=bp_data.get("auth_preference", defaults.auth_preference),
            payments_preference=bp_data.get("payments_preference", defaults.payments_preference),
        )
    else:
        build_prefs = BuildPreferences()

    handoff = FactoryHandoff(
        handoff_id=handoff_data["handoff_id"],
        triggered_at=datetime.fromisoformat(handoff_data["triggered_at"]),
        triggered_by=handoff_data["triggered_by"],
        linear_project_id=handoff_data["linear_project_id"],
        linear_project_url=handoff_data["linear_project_url"],
        prd_input=prd_input,
        build_preferences=build_prefs,
        approval_checkpoints=handoff_data.get("approval_checkpoints", []),
    )

    state = FactoryState(
        execution_id=data["execution_id"],
        handoff=handoff,
        current_phase=Phase(data["current_phase"]),
        phase_statuses={k: PhaseStatus(v) for k, v in data["phase_statuses"].items()},
        phase_outputs=data.get("phase_outputs", {}),
        checkpoints_cleared=data.get("checkpoints_cleared", []),
        linear_issues=data.get("linear_issues", {}),
        linear_phase_issues=data.get("linear_phase_issues", {}),
        linear_team_id=data.get("linear_team_id"),
        slack_channels=data.get("slack_channels", {}),
        slack_qa_thread_ts=data.get("slack_qa_thread_ts"),
        errors=data.get("errors", []),
        started_at=datetime.fromisoformat(data["started_at"]),
        last_updated_at=datetime.fromisoformat(data["last_updated_at"]),
        completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
    )

    return state


def save_state(state: FactoryState) -> None:
    """Persist factory state to storage."""
    if STORAGE_BACKEND == "redis" and REDIS_URL:
        _save_state_redis(state)
    else:
        _save_state_file(state)


def _save_state_file(state: FactoryState) -> None:
    """Save state to JSON file."""
    _ensure_state_dir()
    filepath = _state_file_path(state.execution_id)

    if filepath is None:
        raise ValueError(f"Invalid execution ID: {state.execution_id[:20] if state.execution_id else 'None'}...")

    try:
        data = _serialize_state(state)
        # Write atomically using a temp file
        temp_path = filepath.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        temp_path.replace(filepath)
        logger.debug(f"Saved state to {filepath.name}")
    except Exception as e:
        logger.error(f"Failed to save state to file: {e}")
        raise


def _save_state_redis(state: FactoryState) -> None:
    """Save state to Redis."""
    try:
        import redis
        r = redis.from_url(REDIS_URL)
        data = _serialize_state(state)
        r.setex(
            f"factory:state:{state.execution_id}",
            86400 * 7,  # 7 day TTL
            json.dumps(data, default=str)
        )
        logger.debug(f"Saved state to Redis: {state.execution_id}")
    except Exception as e:
        logger.error(f"Failed to save state to Redis: {e}")
        # Fallback to file
        _save_state_file(state)


def load_state(execution_id: str) -> Optional[FactoryState]:
    """Load factory state from storage."""
    if STORAGE_BACKEND == "redis" and REDIS_URL:
        state = _load_state_redis(execution_id)
        if state:
            return state

    return _load_state_file(execution_id)


def _load_state_file(execution_id: str) -> Optional[FactoryState]:
    """Load state from JSON file."""
    filepath = _state_file_path(execution_id)

    if filepath is None:
        return None

    if not filepath.exists():
        return None

    try:
        with open(filepath, "r") as f:
            data = json.load(f)
        return _deserialize_state(data)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in state file: {e}")
        return None
    except ValueError as e:
        logger.error(f"State file format error: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to load state from file: {e}")
        return None


def _load_state_redis(execution_id: str) -> Optional[FactoryState]:
    """Load state from Redis."""
    try:
        import redis
        r = redis.from_url(REDIS_URL)
        data = r.get(f"factory:state:{execution_id}")
        if data:
            return _deserialize_state(json.loads(data))
    except Exception as e:
        logger.error(f"Failed to load state from Redis: {e}")
    return None


def list_states(status_filter: Optional[str] = None) -> list[dict]:
    """List all factory states, optionally filtered by status."""
    states = []

    if STORAGE_BACKEND == "redis" and REDIS_URL:
        states = _list_states_redis(status_filter)
    else:
        states = _list_states_file(status_filter)

    return sorted(states, key=lambda x: x["started_at"], reverse=True)


def _list_states_redis(status_filter: Optional[str] = None) -> list[dict]:
    """List states from Redis."""
    states = []
    try:
        import redis
        r = redis.from_url(REDIS_URL)

        # Scan for all factory state keys
        cursor = 0
        all_keys = []
        while True:
            cursor, keys = r.scan(cursor, match="factory:state:*", count=100)
            all_keys.extend(keys)
            if cursor == 0:
                break

        logger.info(f"Found {len(all_keys)} states in Redis")

        for key in all_keys:
            try:
                data_str = r.get(key)
                if not data_str:
                    continue

                data = json.loads(data_str)

                # Filter by status if requested
                if status_filter:
                    current_status = data.get("phase_statuses", {}).get(
                        data.get("current_phase"), ""
                    )
                    if current_status != status_filter:
                        continue

                # Get product name from prd_input
                prd_input = data.get("handoff", {}).get("prd_input", {})
                product_name = prd_input.get("name", "Unknown")

                states.append({
                    "execution_id": data["execution_id"],
                    "current_phase": data["current_phase"],
                    "status": data.get("phase_statuses", {}).get(data["current_phase"], "unknown"),
                    "started_at": data["started_at"],
                    "product_name": product_name,
                })
            except Exception as e:
                logger.warning(f"Failed to read state from Redis key {key}: {e}")

    except Exception as e:
        logger.error(f"Failed to list states from Redis: {e}")
        # Fallback to file storage
        return _list_states_file(status_filter)

    return states


def _list_states_file(status_filter: Optional[str] = None) -> list[dict]:
    """List states from file storage."""
    states = []
    _ensure_state_dir()
    logger.info(f"Listing states from: {STATE_DIR} (exists={STATE_DIR.exists()})")
    json_files = list(STATE_DIR.glob("*.json"))
    logger.info(f"Found {len(json_files)} state files")

    for filepath in json_files:
        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            # Filter by status if requested
            if status_filter:
                current_status = data.get("phase_statuses", {}).get(
                    data.get("current_phase"), ""
                )
                if current_status != status_filter:
                    continue

            # Get product name from prd_input (new format) or opportunity (old format)
            prd_input = data.get("handoff", {}).get("prd_input", {})
            product_name = prd_input.get("name") if prd_input else None
            if not product_name:
                product_name = data.get("handoff", {}).get("opportunity", {}).get("name", "Unknown")

            states.append({
                "execution_id": data["execution_id"],
                "current_phase": data["current_phase"],
                "status": data.get("phase_statuses", {}).get(data["current_phase"], "unknown"),
                "started_at": data["started_at"],
                "product_name": product_name,
            })
        except Exception as e:
            logger.warning(f"Failed to read state file {filepath}: {e}")

    return states


def delete_state(execution_id: str) -> bool:
    """Delete a factory state."""
    # Validate execution ID first
    if not _is_valid_execution_id(execution_id):
        logger.warning(f"Attempted to delete invalid execution ID: {execution_id[:20] if execution_id else 'None'}...")
        return False

    if STORAGE_BACKEND == "redis" and REDIS_URL:
        try:
            import redis
            r = redis.from_url(REDIS_URL)
            r.delete(f"factory:state:{execution_id}")
        except Exception:
            pass

    filepath = _state_file_path(execution_id)
    if filepath is None:
        return False

    if filepath.exists():
        filepath.unlink()
        logger.info(f"Deleted state: {execution_id[:8]}...")
        return True
    return False
