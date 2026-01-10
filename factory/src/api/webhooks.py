"""Linear webhook handlers."""

import hashlib
import hmac
import logging
import re
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel

from src.config import settings
from src.orchestrator.persistence import load_state, list_states
from src.orchestrator.runner import resume_factory
from src.tools import linear

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Webhook Payload Models
# =============================================================================

class LinearActor(BaseModel):
    """Linear user who triggered the action."""
    id: str
    name: Optional[str] = None
    email: Optional[str] = None


class LinearIssueData(BaseModel):
    """Issue data from Linear webhook."""
    id: str
    identifier: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    state: Optional[dict] = None
    project: Optional[dict] = None
    labels: Optional[list[dict]] = None
    priority: Optional[int] = None


class LinearCommentData(BaseModel):
    """Comment data from Linear webhook."""
    id: str
    body: str
    issue: Optional[dict] = None
    user: Optional[dict] = None


class LinearWebhookPayload(BaseModel):
    """Linear webhook payload structure."""
    action: str  # create, update, remove
    type: str  # Issue, Comment, Project, etc.
    data: dict
    url: Optional[str] = None
    createdAt: Optional[str] = None
    organizationId: Optional[str] = None


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


def extract_execution_id(text: str) -> Optional[str]:
    """Extract execution ID from issue description or comment."""
    match = EXECUTION_ID_PATTERN.search(text)
    return match.group(1) if match else None


def should_retry(comment_body: str) -> bool:
    """Check if comment contains retry keywords."""
    body_lower = comment_body.lower()
    return any(keyword in body_lower for keyword in RETRY_KEYWORDS)


def find_execution_for_issue(issue_id: str) -> Optional[str]:
    """
    Find the factory execution ID associated with a Linear issue.

    Searches through all factory states to find one that references this issue.
    """
    for state_summary in list_states():
        state = load_state(state_summary.get("execution_id", ""))
        if not state:
            continue

        # Check if this issue is in the phase issues
        for phase_name, phase_info in state.linear_phase_issues.items():
            if phase_info.get("id") == issue_id:
                return state.execution_id

        # Check if this issue is in the work items
        for phase_name, issue_ids in state.linear_issues.items():
            if issue_id in issue_ids:
                return state.execution_id

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
    logger.info(f"Processing retry request on {issue_identifier} from {commenter_name}")

    # Find the execution associated with this issue
    execution_id = find_execution_for_issue(issue_id)

    if not execution_id:
        logger.warning(f"No factory execution found for issue {issue_identifier}")
        # Add comment to issue explaining we couldn't find the execution
        linear.add_comment(
            issue_id,
            f"Could not find factory execution for this issue. "
            f"Please use `/vineyard resume <execution-id>` in Slack instead."
        )
        return

    # Load the state
    state = load_state(execution_id)
    if not state:
        logger.error(f"Could not load state for execution {execution_id}")
        return

    # Add acknowledgment comment
    linear.add_comment(
        issue_id,
        f"Retry requested by {commenter_name}. Resuming factory execution `{execution_id}`..."
    )

    # Resume the factory
    try:
        updated_state = resume_factory(execution_id)

        if updated_state:
            status = updated_state.phase_statuses.get(updated_state.current_phase.value)
            linear.add_comment(
                issue_id,
                f"Factory resumed. Current phase: **{updated_state.current_phase.value}** ({status.value if status else 'unknown'})"
            )
        else:
            linear.add_comment(
                issue_id,
                "Failed to resume factory. Please check logs or try again via Slack."
            )

    except Exception as e:
        logger.exception(f"Error resuming factory: {e}")
        linear.add_comment(
            issue_id,
            f"Error resuming factory: {str(e)[:200]}"
        )


# =============================================================================
# Webhook Endpoints
# =============================================================================

@router.post("/linear")
async def linear_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    linear_signature: Optional[str] = Header(None, alias="Linear-Signature"),
):
    """
    Handle incoming Linear webhooks.

    Supported events:
    - Comment.create: Check for retry keywords to resume failed executions
    - Issue.update: React to status changes (future)
    """
    # Get raw body for signature verification
    body = await request.body()

    # Verify signature if webhook secret is configured
    if settings.linear_webhook_secret:
        if not verify_linear_signature(body, linear_signature, settings.linear_webhook_secret):
            logger.warning("Invalid Linear webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")
    else:
        logger.warning("LINEAR_WEBHOOK_SECRET not configured - skipping signature verification")

    # Parse payload
    try:
        payload = LinearWebhookPayload.model_validate_json(body)
    except Exception as e:
        logger.error(f"Failed to parse Linear webhook payload: {e}")
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

    # Check for retry keywords
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
    logger.info(
        f"Auto-retrying execution {execution_id} due to state change on {issue_identifier}"
    )

    # Add comment explaining the auto-retry
    linear.add_comment(
        issue_id,
        f"Issue moved from **{previous_state}** to **{current_state}**. "
        f"Automatically resuming factory execution `{execution_id}`..."
    )

    try:
        updated_state = resume_factory(execution_id)

        if updated_state:
            status = updated_state.phase_statuses.get(updated_state.current_phase.value)
            linear.add_comment(
                issue_id,
                f"Factory resumed. Current phase: **{updated_state.current_phase.value}** "
                f"({status.value if status else 'unknown'})"
            )
        else:
            linear.add_comment(
                issue_id,
                "Failed to resume factory. Please check logs or retry manually via Slack."
            )

    except Exception as e:
        logger.exception(f"Error auto-retrying factory: {e}")
        linear.add_comment(
            issue_id,
            f"Error resuming factory: {str(e)[:200]}"
        )


@router.get("/linear/status")
async def linear_webhook_status():
    """Check webhook configuration status."""
    return {
        "webhook_secret_configured": bool(settings.linear_webhook_secret),
        "retry_triggers": {
            "comment_keywords": RETRY_KEYWORDS,
            "state_transitions": {
                "from_states": FAILED_STATES,
                "to_states": RETRY_TARGET_STATES,
            },
        },
        "status": "ready",
    }
