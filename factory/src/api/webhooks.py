"""Linear webhook handlers."""

import hashlib
import hmac
import logging
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.config import settings
from src.orchestrator.persistence import load_state, list_states
from src.orchestrator.runner import resume_factory
from src.tools import linear

logger = logging.getLogger(__name__)

router = APIRouter()

# Rate limiter for webhook endpoints
limiter = Limiter(key_func=get_remote_address)

# Security constants
MAX_COMMENT_LENGTH = 10000
MAX_DESCRIPTION_LENGTH = 50000
ALLOWED_WEBHOOK_ACTIONS = {"create", "update", "remove"}
# Include common Linear webhook types to avoid 400 errors
# We only handle Issue/Comment events, but accept others silently
ALLOWED_WEBHOOK_TYPES = {"Issue", "Comment", "Project", "IssueLabel", "Reaction", "ProjectUpdate"}


# =============================================================================
# Webhook Payload Models
# =============================================================================

class LinearActor(BaseModel):
    """Linear user who triggered the action."""
    id: str = Field(..., max_length=100)
    name: Optional[str] = Field(None, max_length=200)
    email: Optional[str] = Field(None, max_length=320)


class LinearIssueData(BaseModel):
    """Issue data from Linear webhook."""
    id: str = Field(..., max_length=100)
    identifier: Optional[str] = Field(None, max_length=50)
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=MAX_DESCRIPTION_LENGTH)
    state: Optional[dict] = None
    project: Optional[dict] = None
    labels: Optional[list[dict]] = None
    priority: Optional[int] = Field(None, ge=0, le=4)


class LinearCommentData(BaseModel):
    """Comment data from Linear webhook."""
    id: str = Field(..., max_length=100)
    body: str = Field(..., max_length=MAX_COMMENT_LENGTH)
    issue: Optional[dict] = None
    user: Optional[dict] = None


class LinearWebhookPayload(BaseModel):
    """Linear webhook payload structure."""
    action: str = Field(..., max_length=20)
    type: str = Field(..., max_length=50)
    data: dict
    url: Optional[str] = Field(None, max_length=500)
    createdAt: Optional[str] = Field(None, max_length=50)
    organizationId: Optional[str] = Field(None, max_length=100)

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in ALLOWED_WEBHOOK_ACTIONS:
            raise ValueError(f"Invalid action: {v}")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ALLOWED_WEBHOOK_TYPES:
            raise ValueError(f"Invalid type: {v}")
        return v


# =============================================================================
# Webhook Signature Verification
# =============================================================================

def verify_linear_signature(
    payload: bytes,
    signature: Optional[str],
    webhook_secret: str,
) -> bool:
    """
    Verify Linear webhook signature.

    Linear signs webhooks with HMAC-SHA256 using your webhook secret.
    """
    if not signature or not webhook_secret:
        return False

    expected = hmac.new(
        webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(signature, expected)


# =============================================================================
# Retry Logic
# =============================================================================

# Keywords that trigger a retry
RETRY_KEYWORDS = [
    "retry",
    "try again",
    "rerun",
    "re-run",
    "restart",
]

# Keywords that trigger checkpoint approval
APPROVAL_KEYWORDS = [
    "approve",
    "approved",
    "lgtm",
    "looks good",
    "ship it",
    "go ahead",
    "proceed",
]

# States that trigger a retry when transitioned TO (from a failed state)
RETRY_TARGET_STATES = [
    "todo",
    "to do",
    "backlog",
    "in progress",
    "in_progress",
    "started",
]

# States considered "failed" or "blocked"
FAILED_STATES = [
    "canceled",
    "cancelled",
    "blocked",
    "failed",
]

# Pattern to extract execution ID from issue description
EXECUTION_ID_PATTERN = re.compile(r"Execution ID:\s*`([a-f0-9-]+)`", re.IGNORECASE)


def is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        uuid.UUID(value)
        return True
    except (ValueError, TypeError):
        return False


def extract_execution_id(text: str) -> Optional[str]:
    """
    Extract and validate execution ID from issue description or comment.

    Returns None if not found or invalid.
    """
    if not text or len(text) > MAX_DESCRIPTION_LENGTH:
        return None

    match = EXECUTION_ID_PATTERN.search(text)
    if not match:
        return None

    candidate = match.group(1)

    # Validate it's a proper UUID format
    if not is_valid_uuid(candidate):
        logger.warning(f"Invalid execution ID format: {candidate[:50]}")
        return None

    return candidate


def validate_execution_id(execution_id: str) -> bool:
    """
    Validate that an execution ID exists in our state store.

    This prevents injection of arbitrary execution IDs.
    """
    if not is_valid_uuid(execution_id):
        return False

    # Check if state exists for this execution
    state = load_state(execution_id)
    return state is not None


def sanitize_error_message(error: Exception, max_length: int = 100) -> str:
    """
    Sanitize error message for external display.

    Removes potentially sensitive information like paths, keys, etc.
    """
    message = str(error)

    # Remove file paths
    message = re.sub(r'/[^\s]+/', '[path]/', message)

    # Remove anything that looks like an API key or token
    message = re.sub(r'(api[_-]?key|token|secret|password|auth)[=:]\s*\S+', r'\1=[REDACTED]', message, flags=re.IGNORECASE)

    # Remove stack trace indicators
    message = re.sub(r'File "[^"]+", line \d+', '[internal]', message)

    # Truncate safely at word boundary
    if len(message) > max_length:
        truncated = message[:max_length].rsplit(' ', 1)[0]
        message = truncated + "..."

    return message


def should_retry(comment_body: str) -> bool:
    """Check if comment contains retry keywords."""
    body_lower = comment_body.lower()
    return any(keyword in body_lower for keyword in RETRY_KEYWORDS)


def should_approve(comment_body: str) -> bool:
    """Check if comment contains approval keywords."""
    body_lower = comment_body.lower()
    return any(keyword in body_lower for keyword in APPROVAL_KEYWORDS)


def find_phase_for_issue(issue_id: str) -> Optional[tuple[str, str]]:
    """
    Find the phase and execution ID for an issue.

    Returns:
        Tuple of (execution_id, phase_name) or None if not found.
    """
    all_states = list_states()
    logger.info(f"Searching {len(all_states)} states for phase issue {issue_id}")

    for state_summary in all_states:
        exec_id = state_summary.get("execution_id", "")
        state = load_state(exec_id)
        if not state:
            logger.debug(f"Could not load state for {exec_id}")
            continue

        logger.debug(f"State {exec_id[:8]} has {len(state.linear_phase_issues)} phase issues")

        for phase_name, phase_info in state.linear_phase_issues.items():
            phase_issue_id = phase_info.get("id") if isinstance(phase_info, dict) else None
            logger.debug(f"  Phase {phase_name}: issue_id={phase_issue_id}")
            if phase_issue_id == issue_id:
                logger.info(f"Found match! Execution {exec_id}, phase {phase_name}")
                return (state.execution_id, phase_name)

    logger.warning(f"No phase found for issue {issue_id} after checking {len(all_states)} states")
    return None


def find_execution_for_issue(issue_id: str) -> Optional[str]:
    """
    Find the factory execution ID associated with a Linear issue.

    Searches through all factory states to find one that references this issue.
    """
    all_states = list_states()
    logger.debug(f"Searching {len(all_states)} states for issue {issue_id}")

    for state_summary in all_states:
        exec_id = state_summary.get("execution_id", "")
        state = load_state(exec_id)
        if not state:
            logger.debug(f"Could not load state for {exec_id}")
            continue

        # Check if this issue is in the phase issues
        for phase_name, phase_info in state.linear_phase_issues.items():
            phase_issue_id = phase_info.get("id") if isinstance(phase_info, dict) else None
            logger.debug(f"Checking phase {phase_name}: {phase_issue_id} vs {issue_id}")
            if phase_issue_id == issue_id:
                logger.info(f"Found execution {exec_id} for issue {issue_id} in phase {phase_name}")
                return state.execution_id

        # Check if this issue is in the work items
        for phase_name, issue_ids in state.linear_issues.items():
            if issue_id in issue_ids:
                logger.info(f"Found execution {exec_id} for issue {issue_id} in work items")
                return state.execution_id

    logger.warning(f"No execution found for issue {issue_id}. Checked {len(all_states)} states.")
    return None


async def handle_retry_request(
    issue_id: str,
    issue_identifier: str,
    comment_body: str,
    commenter_name: str,
):
    """
    Handle a retry request from a Linear comment.

    This runs as a background task after the webhook returns.
    """
    # Sanitize commenter name for logging
    safe_commenter = commenter_name[:50] if commenter_name else "Unknown"
    logger.info(f"Processing retry request on {issue_identifier} from {safe_commenter}")

    # Find the execution associated with this issue
    execution_id = find_execution_for_issue(issue_id)

    if not execution_id:
        logger.warning(f"No factory execution found for issue {issue_identifier}")
        linear.add_comment(
            issue_id,
            "Could not find factory execution for this issue. "
            "Please use `/vineyard resume <execution-id>` in Slack instead."
        )
        return

    # Validate execution ID exists (defense in depth)
    if not validate_execution_id(execution_id):
        logger.error(f"Invalid or non-existent execution ID: {execution_id}")
        linear.add_comment(
            issue_id,
            "Factory execution not found or no longer exists."
        )
        return

    # Load the state
    state = load_state(execution_id)
    if not state:
        logger.error(f"Could not load state for execution {execution_id}")
        return

    # Add acknowledgment comment (don't include full execution ID in public comment)
    short_id = execution_id[:8]
    linear.add_comment(
        issue_id,
        f"Retry requested by {safe_commenter}. Resuming factory execution `{short_id}...`"
    )

    # Resume the factory
    try:
        updated_state = resume_factory(execution_id)

        if updated_state:
            status = updated_state.phase_statuses.get(updated_state.current_phase.value)
            phase_name = updated_state.current_phase.value.replace("_", " ").title()
            linear.add_comment(
                issue_id,
                f"Factory resumed. Current phase: **{phase_name}** ({status.value if status else 'unknown'})"
            )
        else:
            linear.add_comment(
                issue_id,
                "Failed to resume factory. Please check with administrator or try again via Slack."
            )

    except Exception as e:
        logger.exception("Error resuming factory")
        linear.add_comment(
            issue_id,
            f"Error resuming factory: {sanitize_error_message(e)}"
        )


async def handle_approval_request(
    issue_id: str,
    issue_identifier: str,
    comment_body: str,
    commenter_name: str,
):
    """
    Handle a checkpoint approval request from a Linear comment.

    This runs as a background task after the webhook returns.
    """
    safe_commenter = commenter_name[:50] if commenter_name else "Unknown"
    logger.info(f"Processing approval request on {issue_identifier} (id={issue_id}) from {safe_commenter}")

    # Find execution and phase for this issue
    result = find_phase_for_issue(issue_id)

    if not result:
        logger.warning(f"No factory phase found for issue {issue_identifier} (id={issue_id})")

        # Try to provide more helpful info - check if this is a work item
        exec_id = find_execution_for_issue(issue_id)
        if exec_id:
            linear.add_comment(
                issue_id,
                "This appears to be a work item, not a phase checkpoint issue. "
                "To approve a checkpoint, comment on the main phase issue (e.g., 'Research Enrichment', 'Design', etc.)."
            )
        else:
            linear.add_comment(
                issue_id,
                "Could not find a factory checkpoint for this issue. "
                "Make sure you're commenting on a phase issue that is awaiting approval."
            )
        return

    execution_id, phase_name = result

    # Load the state
    state = load_state(execution_id)
    if not state:
        logger.error(f"Could not load state for execution {execution_id}")
        linear.add_comment(issue_id, "Factory execution not found.")
        return

    # Check if this phase is actually awaiting approval
    from src.models import Phase, PhaseStatus

    try:
        phase = Phase(phase_name)
    except ValueError:
        logger.warning(f"Invalid phase name: {phase_name}")
        linear.add_comment(issue_id, f"Invalid phase: {phase_name}")
        return

    current_status = state.phase_statuses.get(phase.value)

    if current_status != PhaseStatus.AWAITING_APPROVAL:
        linear.add_comment(
            issue_id,
            f"This phase is not awaiting approval (current status: {current_status.value if current_status else 'unknown'})."
        )
        return

    # Add acknowledgment comment
    short_id = execution_id[:8]
    opp_name = state.handoff.opportunity.name
    linear.add_comment(
        issue_id,
        f"✅ **Checkpoint approved** by {safe_commenter} via Linear\n\n"
        f"Continuing factory execution for **{opp_name}** (`{short_id}...`)"
    )

    # Approve and continue
    try:
        from src.orchestrator.runner import approve_checkpoint

        # Get Slack channel for notifications
        channel_id = state.slack_channels.get("alerts") or state.slack_channels.get("main")

        updated_state = approve_checkpoint(state, phase, channel_id)

        if updated_state:
            if updated_state.completed_at:
                linear.add_comment(
                    issue_id,
                    f"🎉 Factory completed successfully for **{opp_name}**!"
                )
            else:
                new_phase = updated_state.current_phase.value.replace("_", " ").title()
                new_status = updated_state.phase_statuses.get(updated_state.current_phase.value)
                linear.add_comment(
                    issue_id,
                    f"Factory continuing. Now at: **{new_phase}** ({new_status.value if new_status else 'unknown'})"
                )
        else:
            linear.add_comment(issue_id, "Failed to continue factory after approval.")

    except Exception as e:
        logger.exception("Error approving checkpoint")
        linear.add_comment(
            issue_id,
            f"Error continuing factory: {sanitize_error_message(e)}"
        )


# =============================================================================
# Webhook Endpoints
# =============================================================================

@router.post("/linear")
@limiter.limit("30/minute")  # Stricter limit for webhook endpoint
async def linear_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    linear_signature: Optional[str] = Header(None, alias="Linear-Signature"),
):
    """
    Handle incoming Linear webhooks.

    Supported events:
    - Comment.create: Check for retry keywords to resume failed executions
    - Issue.update: React to status changes

    Security:
    - Requires LINEAR_WEBHOOK_SECRET to be configured
    - Validates HMAC-SHA256 signature on all requests
    - Validates payload structure and content lengths
    - Rate limited to 30 requests/minute per IP
    """
    # Get raw body for signature verification
    body = await request.body()

    # Enforce maximum payload size (1MB)
    if len(body) > 1_000_000:
        logger.warning("Webhook payload too large")
        raise HTTPException(status_code=413, detail="Payload too large")

    # SECURITY: Signature verification is MANDATORY
    if not settings.linear_webhook_secret:
        logger.error("LINEAR_WEBHOOK_SECRET not configured - rejecting webhook")
        raise HTTPException(
            status_code=503,
            detail="Webhook endpoint not configured"
        )

    if not verify_linear_signature(body, linear_signature, settings.linear_webhook_secret):
        logger.warning("Invalid Linear webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse and validate payload
    try:
        payload = LinearWebhookPayload.model_validate_json(body)
    except ValueError as e:
        logger.warning(f"Invalid webhook payload: {sanitize_error_message(e)}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except Exception as e:
        logger.error(f"Failed to parse Linear webhook payload: {sanitize_error_message(e)}")
        raise HTTPException(status_code=400, detail="Invalid payload")

    logger.info(f"Received Linear webhook: {payload.type}.{payload.action}")

    # Route to appropriate handler
    if payload.type == "Comment" and payload.action == "create":
        await handle_comment_created(payload, background_tasks)

    elif payload.type == "Issue" and payload.action == "update":
        await handle_issue_updated(payload, background_tasks)

    # Always return 200 to acknowledge receipt
    return {"status": "ok", "type": payload.type, "action": payload.action}


async def handle_comment_created(
    payload: LinearWebhookPayload,
    background_tasks: BackgroundTasks,
):
    """Handle new comment on an issue."""
    data = payload.data
    body = data.get("body", "")
    issue = data.get("issue", {})
    user = data.get("user", {})

    issue_id = issue.get("id", "")
    issue_identifier = issue.get("identifier", "unknown")
    commenter_name = user.get("name", "Unknown")

    logger.info(f"Comment on {issue_identifier} by {commenter_name}: {body[:50]}...")

    # Check for approval keywords first (checkpoint approval)
    if should_approve(body):
        logger.info(f"Approval keyword detected in comment on {issue_identifier}")
        background_tasks.add_task(
            handle_approval_request,
            issue_id,
            issue_identifier,
            body,
            commenter_name,
        )
        return  # Don't also process as retry

    # Check for retry keywords (resume failed phases)
    if should_retry(body):
        logger.info(f"Retry keyword detected in comment on {issue_identifier}")
        background_tasks.add_task(
            handle_retry_request,
            issue_id,
            issue_identifier,
            body,
            commenter_name,
        )


async def handle_issue_updated(
    payload: LinearWebhookPayload,
    background_tasks: BackgroundTasks,
):
    """
    Handle issue state changes.

    When a failed/canceled issue is moved back to "Todo" or "In Progress",
    automatically trigger a retry of the associated factory phase.
    """
    data = payload.data
    issue_id = data.get("id", "")
    identifier = data.get("identifier", "unknown")
    title = data.get("title", "")
    description = data.get("description", "")

    # Get current state
    state = data.get("state", {})
    current_state = state.get("name", "").lower() if state else ""

    # Get previous state from updatedFrom (Linear includes this in update webhooks)
    updated_from = data.get("updatedFrom", {})
    previous_state_data = updated_from.get("state", {}) if updated_from else {}
    previous_state = previous_state_data.get("name", "").lower() if previous_state_data else ""

    logger.info(
        f"Issue {identifier} updated: '{previous_state}' -> '{current_state}'"
    )

    # Check if this is a state transition we should act on
    if not should_retry_on_state_change(previous_state, current_state):
        return

    logger.info(f"Detected retry-triggering state change on {identifier}")

    # Find associated factory execution
    execution_id = find_execution_for_issue(issue_id)

    if not execution_id:
        # Try to extract from description
        execution_id = extract_execution_id(description)

    if not execution_id:
        logger.debug(f"No factory execution found for issue {identifier}")
        return

    # Check if this execution actually has a failed phase
    state_obj = load_state(execution_id)
    if not state_obj:
        logger.warning(f"Could not load state for execution {execution_id}")
        return

    from src.models import PhaseStatus
    current_phase_status = state_obj.phase_statuses.get(state_obj.current_phase.value)

    if current_phase_status != PhaseStatus.FAILED:
        logger.debug(
            f"Execution {execution_id} is not in failed state "
            f"(current: {current_phase_status}), skipping auto-retry"
        )
        return

    # Trigger retry
    background_tasks.add_task(
        handle_state_change_retry,
        issue_id,
        identifier,
        execution_id,
        previous_state,
        current_state,
    )


def should_retry_on_state_change(previous_state: str, current_state: str) -> bool:
    """
    Determine if a state transition should trigger a retry.

    Returns True if:
    - Previous state was a "failed" state (canceled, blocked, etc.)
    - Current state is a "retry" state (todo, in progress, etc.)
    """
    if not previous_state or not current_state:
        return False

    previous_lower = previous_state.lower().replace(" ", "_")
    current_lower = current_state.lower().replace(" ", "_")

    # Check if moving FROM a failed state TO a retry-triggering state
    was_failed = any(fs in previous_lower for fs in FAILED_STATES)
    now_actionable = any(rs.replace(" ", "_") in current_lower for rs in RETRY_TARGET_STATES)

    return was_failed and now_actionable


async def handle_state_change_retry(
    issue_id: str,
    issue_identifier: str,
    execution_id: str,
    previous_state: str,
    current_state: str,
):
    """
    Handle automatic retry triggered by state change.
    """
    # Validate execution ID before proceeding
    if not validate_execution_id(execution_id):
        logger.error(f"Invalid execution ID in state change retry: {execution_id[:20]}...")
        return

    short_id = execution_id[:8]
    logger.info(
        f"Auto-retrying execution {short_id}... due to state change on {issue_identifier}"
    )

    # Sanitize state names for display
    safe_prev = previous_state[:30] if previous_state else "unknown"
    safe_curr = current_state[:30] if current_state else "unknown"

    # Add comment explaining the auto-retry
    linear.add_comment(
        issue_id,
        f"Issue moved from **{safe_prev}** to **{safe_curr}**. "
        f"Automatically resuming factory execution `{short_id}...`"
    )

    try:
        updated_state = resume_factory(execution_id)

        if updated_state:
            status = updated_state.phase_statuses.get(updated_state.current_phase.value)
            phase_name = updated_state.current_phase.value.replace("_", " ").title()
            linear.add_comment(
                issue_id,
                f"Factory resumed. Current phase: **{phase_name}** "
                f"({status.value if status else 'unknown'})"
            )
        else:
            linear.add_comment(
                issue_id,
                "Failed to resume factory. Please check with administrator or retry via Slack."
            )

    except Exception as e:
        logger.exception("Error auto-retrying factory")
        linear.add_comment(
            issue_id,
            f"Error resuming factory: {sanitize_error_message(e)}"
        )


@router.get("/linear/status")
async def linear_webhook_status():
    """Check webhook configuration status."""
    return {
        "webhook_secret_configured": bool(settings.linear_webhook_secret),
        "triggers": {
            "approval_keywords": APPROVAL_KEYWORDS,
            "retry_keywords": RETRY_KEYWORDS,
            "retry_state_transitions": {
                "from_states": FAILED_STATES,
                "to_states": RETRY_TARGET_STATES,
            },
        },
        "status": "ready",
    }


@router.get("/linear/debug/states")
async def debug_list_states():
    """Debug endpoint: List all states with their linear_phase_issues."""
    from src.orchestrator.persistence import STATE_DIR, STORAGE_BACKEND, REDIS_URL
    import os

    all_states = list_states()
    result = []

    for state_summary in all_states:
        exec_id = state_summary.get("execution_id", "")
        state = load_state(exec_id)

        state_info = {
            "execution_id": exec_id,
            "current_phase": state_summary.get("current_phase"),
            "status": state_summary.get("status"),
            "opportunity_name": state_summary.get("opportunity_name"),
        }

        if state:
            state_info["linear_phase_issues"] = state.linear_phase_issues
            state_info["linear_team_id"] = state.linear_team_id
            state_info["has_linear_tracking"] = len(state.linear_phase_issues) > 0
        else:
            state_info["error"] = "Could not load full state"

        result.append(state_info)

    return {
        "total_states": len(all_states),
        "storage": {
            "backend": STORAGE_BACKEND,
            "redis_configured": bool(REDIS_URL),
            "redis_url": REDIS_URL[:20] + "..." if REDIS_URL and len(REDIS_URL) > 20 else REDIS_URL,
            "state_dir": str(STATE_DIR),
            "state_dir_exists": STATE_DIR.exists(),
            "cwd": os.getcwd(),
            "home": os.path.expanduser("~"),
        },
        "states": result,
    }


@router.get("/linear/debug/issue/{issue_id}")
async def debug_find_issue(issue_id: str):
    """Debug endpoint: Try to find which state/phase an issue belongs to."""
    # Check phase issues
    phase_result = find_phase_for_issue(issue_id)

    # Check work items
    exec_result = find_execution_for_issue(issue_id)

    return {
        "issue_id": issue_id,
        "phase_match": {
            "found": phase_result is not None,
            "execution_id": phase_result[0] if phase_result else None,
            "phase": phase_result[1] if phase_result else None,
        },
        "work_item_match": {
            "found": exec_result is not None,
            "execution_id": exec_result,
        },
    }
