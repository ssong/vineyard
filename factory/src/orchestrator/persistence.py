"""Persistent state storage for factory execution.

Provides file-based persistence for development and Redis for production.
State is automatically persisted after each phase update.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.models import FactoryHandoff, FactoryState, Phase, PhaseStatus

logger = logging.getLogger(__name__)

# Storage backend: "file" or "redis"
STORAGE_BACKEND = os.getenv("FACTORY_STORAGE_BACKEND", "file")

# File storage path
STATE_DIR = Path(os.getenv("FACTORY_STATE_DIR", "/tmp/vineyard-factory-state"))

# Redis connection (optional)
REDIS_URL = os.getenv("REDIS_URL")


def _ensure_state_dir():
    """Ensure state directory exists."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _state_file_path(execution_id: str) -> Path:
    """Get path to state file."""
    return STATE_DIR / f"{execution_id}.json"


def _serialize_state(state: FactoryState) -> dict:
    """Serialize FactoryState to JSON-compatible dict."""
    return {
        "execution_id": state.execution_id,
        "handoff": _serialize_handoff(state.handoff),
        "current_phase": state.current_phase.value,
        "phase_statuses": {k: v.value if isinstance(v, PhaseStatus) else v 
                          for k, v in state.phase_statuses.items()},
        "phase_outputs": state.phase_outputs,  # Assumes outputs are JSON-serializable
        "checkpoints_cleared": state.checkpoints_cleared,
        "linear_issues": state.linear_issues,
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
        "research_report_id": handoff.research_report_id,
        "opportunity_id": handoff.opportunity_id,
        "linear_project_id": handoff.linear_project_id,
        "linear_project_url": handoff.linear_project_url,
        "opportunity": {
            "name": handoff.opportunity.name,
            "slug": handoff.opportunity.slug,
            "one_liner": handoff.opportunity.one_liner,
            "detailed_description": handoff.opportunity.detailed_description,
            "category": handoff.opportunity.category,
            "target_segment": handoff.opportunity.target_segment,
            "business_model": handoff.opportunity.business_model,
            "problem_statement": handoff.opportunity.problem_statement,
            "current_solutions": handoff.opportunity.current_solutions,
            "pain_intensity": handoff.opportunity.pain_intensity,
            "frequency": handoff.opportunity.frequency,
            "target_market_description": handoff.opportunity.target_market_description,
            "geographic_focus": handoff.opportunity.geographic_focus,
            "direct_competitors": handoff.opportunity.direct_competitors,
            "competitor_weaknesses": handoff.opportunity.competitor_weaknesses,
            "differentiation_angle": handoff.opportunity.differentiation_angle,
            "build_complexity": handoff.opportunity.build_complexity,
            "estimated_build_weeks": handoff.opportunity.estimated_build_weeks,
            "key_technical_components": handoff.opportunity.key_technical_components,
            "platform_dependencies": handoff.opportunity.platform_dependencies,
            "suggested_price_low": handoff.opportunity.suggested_price_low,
            "suggested_price_mid": handoff.opportunity.suggested_price_mid,
            "suggested_price_high": handoff.opportunity.suggested_price_high,
        },
        "validation": {
            "four_u_score": handoff.validation.four_u_score,
            "four_u_breakdown": handoff.validation.four_u_breakdown,
            "is_graveyard_market": handoff.validation.is_graveyard_market,
            "platform_risk_level": handoff.validation.platform_risk_level,
            "key_risks": handoff.validation.key_risks,
            "key_opportunities": handoff.validation.key_opportunities,
        },
        "forecast": {
            "assumed_arpu": handoff.forecast.assumed_arpu,
            "mrr_month_12_conservative": handoff.forecast.mrr_month_12_conservative,
            "mrr_month_12_moderate": handoff.forecast.mrr_month_12_moderate,
            "mrr_month_12_optimistic": handoff.forecast.mrr_month_12_optimistic,
            "mrr_month_24_moderate": handoff.forecast.mrr_month_24_moderate,
        },
        "approval_checkpoints": handoff.approval_checkpoints,
    }


def _deserialize_state(data: dict) -> FactoryState:
    """Deserialize dict to FactoryState."""
    from src.models import (
        BuildPreferences,
        FactoryHandoff,
        ForecastSummary,
        LaunchPreferences,
        OpportunitySummary,
        ValidationSummary,
    )

    handoff_data = data["handoff"]
    
    handoff = FactoryHandoff(
        handoff_id=handoff_data["handoff_id"],
        triggered_at=datetime.fromisoformat(handoff_data["triggered_at"]),
        triggered_by=handoff_data["triggered_by"],
        research_report_id=handoff_data["research_report_id"],
        opportunity_id=handoff_data["opportunity_id"],
        linear_project_id=handoff_data["linear_project_id"],
        linear_project_url=handoff_data["linear_project_url"],
        opportunity=OpportunitySummary(**handoff_data["opportunity"]),
        validation=ValidationSummary(**handoff_data["validation"]),
        forecast=ForecastSummary(**handoff_data["forecast"]),
        build_preferences=BuildPreferences(),
        launch_preferences=LaunchPreferences(),
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
    
    try:
        data = _serialize_state(state)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.debug(f"Saved state to {filepath}")
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
    
    if not filepath.exists():
        return None
    
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
        return _deserialize_state(data)
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
    
    if STORAGE_BACKEND == "file":
        _ensure_state_dir()
        for filepath in STATE_DIR.glob("*.json"):
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
                
                states.append({
                    "execution_id": data["execution_id"],
                    "current_phase": data["current_phase"],
                    "status": data.get("phase_statuses", {}).get(data["current_phase"], "unknown"),
                    "started_at": data["started_at"],
                    "opportunity_name": data.get("handoff", {}).get("opportunity", {}).get("name", "Unknown"),
                })
            except Exception as e:
                logger.warning(f"Failed to read state file {filepath}: {e}")
    
    return sorted(states, key=lambda x: x["started_at"], reverse=True)


def delete_state(execution_id: str) -> bool:
    """Delete a factory state."""
    if STORAGE_BACKEND == "redis" and REDIS_URL:
        try:
            import redis
            r = redis.from_url(REDIS_URL)
            r.delete(f"factory:state:{execution_id}")
        except Exception:
            pass
    
    filepath = _state_file_path(execution_id)
    if filepath.exists():
        filepath.unlink()
        return True
    return False
