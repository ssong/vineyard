"""Linear API client for project management."""

import logging
from functools import lru_cache
from typing import Optional

import httpx

from src.config import settings
from src.utils import truncate_text, LinearLimits

logger = logging.getLogger(__name__)

LINEAR_API_URL = "https://api.linear.app/graphql"

# Cache for workflow states and labels (cleared on module reload)
_workflow_states_cache: dict[str, dict[str, str]] = {}
_labels_cache: dict[str, dict[str, str]] = {}


def _make_request(query: str, variables: Optional[dict] = None) -> dict:
    """Make a GraphQL request to Linear API."""
    if not settings.linear_api_key:
        logger.warning("LINEAR_API_KEY not configured")
        return {}

    headers = {
        "Authorization": settings.linear_api_key,
        "Content-Type": "application/json",
    }

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    with httpx.Client(timeout=30.0) as client:
        response = client.post(LINEAR_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            raise ValueError(f"Linear API error: {data['errors']}")

        return data.get("data", {})


def get_teams() -> list[dict]:
    """Get list of teams in the workspace."""
    query = """
    query {
        teams {
            nodes {
                id
                name
                key
            }
        }
    }
    """
    data = _make_request(query)
    return data.get("teams", {}).get("nodes", [])


def get_workflow_states(team_id: str) -> dict[str, str]:
    """
    Get workflow states for a team.

    Returns:
        Dict mapping state names (lowercase) to state IDs.
        Common states: backlog, todo, in_progress, done, canceled
    """
    if team_id in _workflow_states_cache:
        return _workflow_states_cache[team_id]

    query = """
    query GetWorkflowStates($teamId: String!) {
        team(id: $teamId) {
            states {
                nodes {
                    id
                    name
                    type
                }
            }
        }
    }
    """

    data = _make_request(query, {"teamId": team_id})
    states = data.get("team", {}).get("states", {}).get("nodes", [])

    # Map state names to IDs (lowercase for easy lookup)
    state_map = {}
    for state in states:
        name = state.get("name", "").lower().replace(" ", "_")
        state_map[name] = state.get("id", "")
        # Also map by type for fallback
        state_type = state.get("type", "").lower()
        if state_type and state_type not in state_map:
            state_map[state_type] = state.get("id", "")

    _workflow_states_cache[team_id] = state_map
    logger.info(f"Cached workflow states for team {team_id}: {list(state_map.keys())}")
    return state_map


def get_labels(team_id: str) -> dict[str, str]:
    """
    Get labels for a team.

    Returns:
        Dict mapping label names (lowercase) to label IDs.
    """
    if team_id in _labels_cache:
        return _labels_cache[team_id]

    query = """
    query GetLabels($teamId: String!) {
        team(id: $teamId) {
            labels {
                nodes {
                    id
                    name
                    color
                }
            }
        }
    }
    """

    data = _make_request(query, {"teamId": team_id})
    labels = data.get("team", {}).get("labels", {}).get("nodes", [])

    label_map = {label.get("name", "").lower(): label.get("id", "") for label in labels}
    _labels_cache[team_id] = label_map
    logger.info(f"Cached labels for team {team_id}: {list(label_map.keys())}")
    return label_map


def create_label(team_id: str, name: str, color: str = "#6B7280") -> Optional[str]:
    """
    Create a label for a team.

    Args:
        team_id: The team ID
        name: Label name
        color: Hex color code (default: gray)

    Returns:
        Label ID if created successfully, None otherwise
    """
    mutation = """
    mutation CreateLabel($input: IssueLabelCreateInput!) {
        issueLabelCreate(input: $input) {
            success
            issueLabel {
                id
                name
            }
        }
    }
    """

    variables = {
        "input": {
            "teamId": team_id,
            "name": name,
            "color": color,
        }
    }

    try:
        data = _make_request(mutation, variables)
        result = data.get("issueLabelCreate", {})
        if result.get("success"):
            label_id = result.get("issueLabel", {}).get("id")
            # Update cache
            if team_id in _labels_cache:
                _labels_cache[team_id][name.lower()] = label_id
            logger.info(f"Created label '{name}' with ID {label_id}")
            return label_id
    except Exception as e:
        logger.warning(f"Failed to create label '{name}': {e}")
    return None


def ensure_labels(team_id: str, label_names: list[str]) -> dict[str, str]:
    """
    Ensure labels exist for a team, creating them if necessary.

    Args:
        team_id: The team ID
        label_names: List of label names to ensure exist

    Returns:
        Dict mapping label names to their IDs
    """
    # Standard colors for different label types
    label_colors = {
        "research": "#10B981",      # Green
        "validation": "#3B82F6",    # Blue
        "design": "#8B5CF6",        # Purple
        "spec": "#F59E0B",          # Amber
        "engineering": "#EF4444",   # Red
        "build": "#EF4444",         # Red
        "test": "#06B6D4",          # Cyan
        "security": "#F97316",      # Orange
        "devops": "#6366F1",        # Indigo
        "marketing": "#EC4899",     # Pink
        "launch": "#14B8A6",        # Teal
        "growth": "#84CC16",        # Lime
        "support": "#A855F7",       # Fuchsia
        "phase": "#6B7280",         # Gray
        "blocked": "#DC2626",       # Red
        "failed": "#DC2626",        # Red
        "needs-review": "#FBBF24",  # Yellow
    }

    existing_labels = get_labels(team_id)
    result = {}

    for name in label_names:
        name_lower = name.lower()
        if name_lower in existing_labels:
            result[name_lower] = existing_labels[name_lower]
        else:
            color = label_colors.get(name_lower, "#6B7280")
            label_id = create_label(team_id, name, color)
            if label_id:
                result[name_lower] = label_id

    return result


def get_project(project_id: str) -> dict:
    """Get project details."""
    query = """
    query GetProject($id: String!) {
        project(id: $id) {
            id
            name
            url
            state
            teams {
                nodes {
                    id
                    name
                }
            }
        }
    }
    """
    data = _make_request(query, {"id": project_id})
    return data.get("project", {})


def list_projects(limit: int = 20) -> list[dict]:
    """
    List recent projects from Linear.

    Args:
        limit: Maximum number of projects to return (default 20)

    Returns:
        List of project dicts with id, name, url, state, and team info
    """
    query = """
    query ListProjects($first: Int!) {
        projects(first: $first, orderBy: updatedAt) {
            nodes {
                id
                name
                url
                state
                description
                updatedAt
                teams {
                    nodes {
                        id
                        name
                        key
                    }
                }
            }
        }
    }
    """
    data = _make_request(query, {"first": limit})
    return data.get("projects", {}).get("nodes", [])


def create_issue(
    project_id: str,
    team_id: str,
    title: str,
    description: str,
    labels: Optional[list[str]] = None,
    priority: int = 2,
    state_name: Optional[str] = None,
    parent_id: Optional[str] = None,
) -> dict:
    """
    Create an issue in Linear.

    Args:
        project_id: Linear project ID
        team_id: Linear team ID
        title: Issue title
        description: Issue description (markdown)
        labels: List of label names (will be resolved to IDs)
        priority: 0=none, 1=urgent, 2=high, 3=medium, 4=low
        state_name: Initial state name (e.g., 'backlog', 'todo', 'in_progress')
        parent_id: Parent issue ID for sub-issues

    Returns:
        Issue dict with id, identifier, url
    """
    mutation = """
    mutation CreateIssue($input: IssueCreateInput!) {
        issueCreate(input: $input) {
            success
            issue {
                id
                identifier
                url
            }
        }
    }
    """

    input_data = {
        "projectId": project_id,
        "teamId": team_id,
        "title": truncate_text(title, LinearLimits.ISSUE_TITLE),
        "description": truncate_text(description, LinearLimits.ISSUE_DESCRIPTION),
        "priority": priority,
    }

    # Resolve label names to IDs
    if labels:
        label_map = ensure_labels(team_id, labels)
        label_ids = [label_map[l.lower()] for l in labels if l.lower() in label_map]
        if label_ids:
            input_data["labelIds"] = label_ids

    # Resolve state name to ID
    if state_name:
        states = get_workflow_states(team_id)
        state_id = states.get(state_name.lower().replace(" ", "_"))
        if state_id:
            input_data["stateId"] = state_id

    # Set parent for sub-issues
    if parent_id:
        input_data["parentId"] = parent_id

    variables = {"input": input_data}

    data = _make_request(mutation, variables)
    result = data.get("issueCreate", {})

    if result.get("success"):
        issue = result.get("issue", {})
        logger.info(f"Created issue {issue.get('identifier')}: {title}")
        return issue
    return {}


def create_issues_batch(
    project_id: str,
    team_id: str,
    issues: list[dict],
) -> list[str]:
    """Create multiple issues and return their IDs."""
    created_ids = []

    for issue in issues:
        result = create_issue(
            project_id=project_id,
            team_id=team_id,
            title=issue.get("title", "Untitled"),
            description=issue.get("description", ""),
            labels=issue.get("labels", []),
            priority=issue.get("priority", 2),
        )
        if result:
            created_ids.append(result.get("id", ""))

    return [id for id in created_ids if id]


def update_issue_status(issue_id: str, state_id: str) -> bool:
    """Update the status of an issue by state ID."""
    mutation = """
    mutation UpdateIssue($id: String!, $input: IssueUpdateInput!) {
        issueUpdate(id: $id, input: $input) {
            success
        }
    }
    """

    variables = {
        "id": issue_id,
        "input": {"stateId": state_id},
    }

    data = _make_request(mutation, variables)
    return data.get("issueUpdate", {}).get("success", False)


def transition_issue(issue_id: str, team_id: str, state_name: str) -> bool:
    """
    Transition an issue to a new state by name.

    Args:
        issue_id: The issue ID
        team_id: The team ID (for state lookup)
        state_name: Target state name (e.g., 'in_progress', 'done', 'canceled')

    Returns:
        True if successful
    """
    states = get_workflow_states(team_id)
    state_id = states.get(state_name.lower().replace(" ", "_"))

    if not state_id:
        logger.warning(f"State '{state_name}' not found for team {team_id}")
        return False

    success = update_issue_status(issue_id, state_id)
    if success:
        logger.info(f"Transitioned issue {issue_id} to '{state_name}'")
    return success


def start_issue(issue_id: str, team_id: str) -> bool:
    """Mark an issue as in progress."""
    # Try common state names for "in progress"
    states = get_workflow_states(team_id)
    for state_name in ["in_progress", "in progress", "started", "doing"]:
        if state_name in states:
            return update_issue_status(issue_id, states[state_name])
    logger.warning(f"Could not find 'in progress' state for team {team_id}")
    return False


def complete_issue(issue_id: str, team_id: str) -> bool:
    """Mark an issue as done/completed."""
    states = get_workflow_states(team_id)
    for state_name in ["done", "completed", "complete", "closed"]:
        if state_name in states:
            return update_issue_status(issue_id, states[state_name])
    logger.warning(f"Could not find 'done' state for team {team_id}")
    return False


def cancel_issue(issue_id: str, team_id: str) -> bool:
    """Mark an issue as canceled."""
    states = get_workflow_states(team_id)
    for state_name in ["canceled", "cancelled", "won't_do", "wont_do"]:
        if state_name in states:
            return update_issue_status(issue_id, states[state_name])
    logger.warning(f"Could not find 'canceled' state for team {team_id}")
    return False


def block_issue(issue_id: str, team_id: str, reason: str) -> bool:
    """
    Mark an issue as blocked by adding a label and comment.

    Args:
        issue_id: The issue ID
        team_id: The team ID
        reason: Why the issue is blocked

    Returns:
        True if successful
    """
    # Add blocked label
    labels = ensure_labels(team_id, ["blocked"])
    if "blocked" in labels:
        mutation = """
        mutation UpdateIssue($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
            }
        }
        """
        variables = {
            "id": issue_id,
            "input": {"labelIds": [labels["blocked"]]},
        }
        _make_request(mutation, variables)

    # Add comment explaining why
    return add_comment(issue_id, f"**Blocked:** {reason}")


def add_comment(issue_id: str, body: str) -> bool:
    """Add a comment to an issue."""
    mutation = """
    mutation CreateComment($input: CommentCreateInput!) {
        commentCreate(input: $input) {
            success
        }
    }
    """

    variables = {
        "input": {
            "issueId": issue_id,
            "body": truncate_text(body, LinearLimits.COMMENT_BODY),
        }
    }


    data = _make_request(mutation, variables)
    return data.get("commentCreate", {}).get("success", False)


def add_project_comment(project_id: str, body: str) -> bool:
    """Add a comment to a project (creates an issue as a workaround since Linear projects don't have comments)."""
    # Linear projects don't support comments directly, so we create a tracking issue
    try:
        project = get_project(project_id)
        teams = project.get("teams", {}).get("nodes", [])
        if not teams:
            logger.warning("No team found for project")
            return False
        
        team_id = teams[0]["id"]
        
        result = create_issue(
            project_id=project_id,
            team_id=team_id,
            title="📋 Factory Status Update",
            description=body,
            priority=4,  # Low priority for status updates
        )
        return bool(result)
    except Exception as e:
        logger.error(f"Failed to add project comment: {e}")
        return False


def create_error_issue(
    project_id: str,
    phase: str,
    error_message: str,
    execution_id: str,
) -> Optional[str]:
    """
    Create an error issue in Linear when a factory phase fails.
    
    Returns the issue URL if successful, None otherwise.
    """
    try:
        project = get_project(project_id)
        teams = project.get("teams", {}).get("nodes", [])
        
        if not teams:
            logger.warning("No team found for project")
            return None
        
        team_id = teams[0]["id"]
        
        # Format error description
        description = f"""## ❌ Factory Phase Failed

**Phase:** {phase.replace('_', ' ').title()}
**Execution ID:** `{execution_id}`

### Error Details

```
{error_message[:2000]}
```

### Next Steps

1. Review the error message above
2. Check logs for more context
3. Fix the underlying issue
4. Resume the factory from Slack or restart manually

---
*This issue was automatically created by the Vineyard Factory*
"""

        result = create_issue(
            project_id=project_id,
            team_id=team_id,
            title=f"🔴 Factory Error: {phase.replace('_', ' ').title()} Failed",
            description=description,
            priority=1,  # Urgent
        )
        
        if result:
            logger.info(f"Created error issue: {result.get('url')}")
            return result.get("url")
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to create error issue: {e}")
        return None


def update_project_status(
    project_id: str,
    phase: str,
    status: str,
    details: Optional[str] = None,
) -> bool:
    """
    Update project with phase status via a status tracking issue.

    Args:
        project_id: Linear project ID
        phase: Current phase name
        status: Status (completed, failed, in_progress)
        details: Optional additional details
    """
    status_emoji = {
        "completed": "✅",
        "failed": "❌",
        "in_progress": "🔄",
        "awaiting_approval": "⏸️",
    }

    emoji = status_emoji.get(status, "📋")

    body = f"## {emoji} Phase Update: {phase.replace('_', ' ').title()}\n\n"
    body += f"**Status:** {status.replace('_', ' ').title()}\n\n"

    if details:
        body += f"**Details:**\n{details}\n"

    return add_project_comment(project_id, body)


# =============================================================================
# Factory Integration - Upfront Issue Creation & Tracking
# =============================================================================

# Phase metadata for creating upfront issues
PHASE_ISSUE_CONFIG = {
    "research_enrichment": {
        "title": "[Phase] Research Enrichment",
        "description": "Deep-dive research to enrich the opportunity with additional market data, competitor analysis, and validation signals.",
        "label": "research",
        "tasks": [
            "Analyze competitor landscape",
            "Validate market size assumptions",
            "Identify key differentiators",
            "Research pricing benchmarks",
        ],
    },
    "design": {
        "title": "[Phase] Product Design",
        "description": "Create product requirements, user flows, and feature specifications.",
        "label": "design",
        "tasks": [
            "Draft product requirements document",
            "Design user flows and wireframes",
            "Define P0/P1/P2 features",
            "Create UI/UX specifications",
        ],
    },
    "spec": {
        "title": "[Phase] Technical Specification",
        "description": "Generate technical architecture, API design, database schema, and engineering task breakdown.",
        "label": "spec",
        "tasks": [
            "Define system architecture",
            "Design API endpoints",
            "Create database schema",
            "Break down engineering tasks",
        ],
    },
    "build": {
        "title": "[Phase] Build & Implementation",
        "description": "Code generation, testing, security review, and DevOps setup.",
        "label": "build",
        "tasks": [
            "Generate application code",
            "Create test suite",
            "Perform security review",
            "Configure deployment infrastructure",
        ],
    },
    "launch_prep": {
        "title": "[Phase] Launch Preparation",
        "description": "Marketing content, landing pages, and launch materials.",
        "label": "marketing",
        "tasks": [
            "Create marketing copy",
            "Design landing page",
            "Prepare launch emails",
            "Set up analytics",
        ],
    },
    "launch": {
        "title": "[Phase] Launch",
        "description": "Deploy to production and execute launch plan.",
        "label": "launch",
        "tasks": [
            "Deploy to production",
            "Execute launch checklist",
            "Monitor initial metrics",
            "Address launch issues",
        ],
    },
    "growth": {
        "title": "[Phase] Growth & Support",
        "description": "Growth experiments, customer support setup, and ongoing optimization.",
        "label": "growth",
        "tasks": [
            "Set up growth experiments",
            "Create support documentation",
            "Configure feedback channels",
            "Plan iteration roadmap",
        ],
    },
}


def create_factory_issues(
    project_id: str,
    product_name: str,
    execution_id: str,
    phases: Optional[list[str]] = None,
) -> dict[str, dict]:
    """
    Create upfront issues for all factory phases before work begins.

    This creates:
    1. A root "Factory Run" issue to track the entire execution
    2. Phase issues for each factory phase
    3. Task sub-issues under each phase

    Args:
        project_id: Linear project ID
        product_name: Name of the product being built
        execution_id: Factory execution ID for tracking
        phases: Optional list of phases to create (defaults to all)

    Returns:
        Dict mapping phase names to their issue info:
        {
            "root": {"id": "...", "identifier": "...", "url": "..."},
            "research_enrichment": {"id": "...", "identifier": "...", "tasks": [...]},
            ...
        }
    """
    project = get_project(project_id)
    teams = project.get("teams", {}).get("nodes", [])

    if not teams:
        logger.error("No team found for project")
        return {}

    team_id = teams[0]["id"]

    # Ensure all required labels exist
    all_labels = ["phase"] + [cfg["label"] for cfg in PHASE_ISSUE_CONFIG.values()]
    ensure_labels(team_id, all_labels)

    result = {}

    # 1. Create root factory issue
    root_description = f"""# Factory Run: {product_name}

**Execution ID:** `{execution_id}`

This issue tracks the entire factory execution for building {product_name}.

## Phases

| Phase | Status |
|-------|--------|
| Research Enrichment | ⏳ Pending |
| Design | ⏳ Pending |
| Specification | ⏳ Pending |
| Build | ⏳ Pending |
| Launch Prep | ⏳ Pending |
| Launch | ⏳ Pending |
| Growth | ⏳ Pending |

---
*This issue is automatically managed by Vineyard Factory*
"""

    root_issue = create_issue(
        project_id=project_id,
        team_id=team_id,
        title=f"🏭 Factory: {product_name}",
        description=root_description,
        labels=["phase"],
        priority=2,
        state_name="backlog",
    )

    if root_issue:
        result["root"] = root_issue
        logger.info(f"Created factory root issue: {root_issue.get('identifier')}")

    root_id = root_issue.get("id") if root_issue else None

    # 2. Create phase issues
    phases_to_create = phases or list(PHASE_ISSUE_CONFIG.keys())

    for phase_name in phases_to_create:
        if phase_name not in PHASE_ISSUE_CONFIG:
            continue

        config = PHASE_ISSUE_CONFIG[phase_name]

        # Build task checklist for description
        task_list = "\n".join([f"- [ ] {task}" for task in config["tasks"]])

        phase_description = f"""{config['description']}

## Tasks

{task_list}

---
**Phase:** {phase_name.replace('_', ' ').title()}
**Execution ID:** `{execution_id}`
"""

        phase_issue = create_issue(
            project_id=project_id,
            team_id=team_id,
            title=config["title"],
            description=phase_description,
            labels=["phase", config["label"]],
            priority=3,
            state_name="backlog",
            parent_id=root_id,
        )

        if phase_issue:
            result[phase_name] = {
                "id": phase_issue.get("id"),
                "identifier": phase_issue.get("identifier"),
                "url": phase_issue.get("url"),
                "task_ids": [],  # Will be populated as tasks are created
            }
            logger.info(f"Created phase issue for {phase_name}: {phase_issue.get('identifier')}")

    return result


def update_phase_issue(
    phase_issue_id: str,
    team_id: str,
    status: str,
    progress_message: Optional[str] = None,
    completed_tasks: Optional[list[str]] = None,
    execution_id: Optional[str] = None,
) -> bool:
    """
    Update a phase issue with progress.

    Args:
        phase_issue_id: The phase issue ID
        team_id: Team ID for state lookup
        status: One of 'started', 'in_progress', 'completed', 'failed', 'blocked'
        progress_message: Optional message to add as comment
        completed_tasks: List of completed task descriptions (for updating checklist)
        execution_id: Factory execution ID (for failed status comments)

    Returns:
        True if update successful
    """
    success = True

    # Transition to appropriate state
    # For failed: stay in_progress so the issue remains visible and actionable
    state_map = {
        "started": "in_progress",
        "in_progress": "in_progress",
        "completed": "done",
        "failed": "in_progress",  # Keep visible, add failed label instead
        "blocked": "in_progress",  # Stay in progress but add blocked label
    }

    target_state = state_map.get(status, "in_progress")
    if not transition_issue(phase_issue_id, team_id, target_state):
        success = False

    # Handle blocked status specially
    if status == "blocked" and progress_message:
        block_issue(phase_issue_id, team_id, progress_message)

    # Handle failed status - add failed label and detailed comment
    if status == "failed":
        # Add failed label
        labels = ensure_labels(team_id, ["failed"])
        if "failed" in labels:
            _add_label_to_issue(phase_issue_id, labels["failed"])

        # Add detailed error comment
        error_comment = f"""## ❌ Phase Failed

**Error:**
```
{progress_message[:2000] if progress_message else 'Unknown error'}
```

### Next Steps

1. Review the error message above
2. Check logs for more context
3. Fix the underlying issue
4. Comment "retry" on this issue or move it back to "Todo" to resume

"""
        if execution_id:
            error_comment += f"**Execution ID:** `{execution_id}`\n\n"
        error_comment += "---\n*This issue can be retried by commenting \"retry\" or moving to Todo*"
        add_comment(phase_issue_id, error_comment)

    # Add progress comment if provided (for non-blocked, non-failed statuses)
    elif progress_message and status != "blocked":
        status_emoji = {
            "started": "🚀",
            "in_progress": "🔄",
            "completed": "✅",
        }
        emoji = status_emoji.get(status, "📋")
        comment = f"{emoji} **{status.replace('_', ' ').title()}**\n\n{progress_message}"
        add_comment(phase_issue_id, comment)

    return success


def _add_label_to_issue(issue_id: str, label_id: str) -> bool:
    """Add a label to an issue."""
    mutation = """
    mutation UpdateIssue($id: String!, $input: IssueUpdateInput!) {
        issueUpdate(id: $id, input: $input) {
            success
        }
    }
    """
    variables = {
        "id": issue_id,
        "input": {"labelIds": [label_id]},
    }
    try:
        data = _make_request(mutation, variables)
        return data.get("issueUpdate", {}).get("success", False)
    except Exception as e:
        logger.warning(f"Failed to add label to issue: {e}")
        return False


def create_work_items(
    project_id: str,
    team_id: str,
    phase_issue_id: str,
    work_items: list[dict],
    label: str,
) -> list[dict]:
    """
    Create work item issues under a phase issue.

    Args:
        project_id: Linear project ID
        team_id: Linear team ID
        phase_issue_id: Parent phase issue ID
        work_items: List of work items with 'title', 'description', optional 'priority'
        label: Label to apply to all work items

    Returns:
        List of created issue dicts with id, identifier, url
    """
    created = []

    for item in work_items:
        issue = create_issue(
            project_id=project_id,
            team_id=team_id,
            title=item.get("title", "Untitled Task"),
            description=item.get("description", ""),
            labels=[label],
            priority=item.get("priority", 3),
            state_name="todo",
            parent_id=phase_issue_id,
        )
        if issue:
            created.append(issue)

    return created


class FactoryLinearTracker:
    """
    Manages Linear issue tracking throughout a factory run.

    Usage:
        tracker = FactoryLinearTracker(project_id, product_name, execution_id)
        phase_issues = tracker.initialize()

        # When starting a phase
        tracker.start_phase("design")

        # When adding work items during a phase
        tracker.add_work_items("design", [{"title": "...", "description": "..."}])

        # When completing work items
        tracker.complete_work_item(issue_id)

        # When phase completes
        tracker.complete_phase("design", "PRD and user flows generated")

        # When phase fails
        tracker.fail_phase("build", "Code generation failed: ...")
    """

    def __init__(self, project_id: str, product_name: str, execution_id: str):
        self.project_id = project_id
        self.product_name = product_name
        self.execution_id = execution_id
        self.team_id: Optional[str] = None
        self.phase_issues: dict[str, dict] = {}
        self.work_items: dict[str, list[str]] = {}  # phase -> [issue_ids]

    def initialize(self) -> dict[str, dict]:
        """Create all upfront issues and return phase mapping."""
        # Get team ID
        project = get_project(self.project_id)
        teams = project.get("teams", {}).get("nodes", [])
        if teams:
            self.team_id = teams[0]["id"]

        # Create upfront issues
        self.phase_issues = create_factory_issues(
            project_id=self.project_id,
            product_name=self.product_name,
            execution_id=self.execution_id,
        )

        return self.phase_issues

    def start_phase(self, phase_name: str, message: Optional[str] = None) -> bool:
        """Mark a phase as started/in-progress."""
        if phase_name not in self.phase_issues:
            logger.warning(f"Phase {phase_name} not found in tracked issues")
            return False

        phase_id = self.phase_issues[phase_name].get("id")
        if not phase_id or not self.team_id:
            return False

        return update_phase_issue(
            phase_issue_id=phase_id,
            team_id=self.team_id,
            status="started",
            progress_message=message or f"Starting {phase_name.replace('_', ' ')} phase...",
        )

    def update_phase_progress(self, phase_name: str, message: str) -> bool:
        """Add a progress update to a phase."""
        if phase_name not in self.phase_issues:
            return False

        phase_id = self.phase_issues[phase_name].get("id")
        if not phase_id:
            return False

        return add_comment(phase_id, f"🔄 {message}")

    def complete_phase(self, phase_name: str, summary: Optional[str] = None) -> bool:
        """Mark a phase as completed."""
        if phase_name not in self.phase_issues:
            return False

        phase_id = self.phase_issues[phase_name].get("id")
        if not phase_id or not self.team_id:
            return False

        # Complete all work items for this phase
        for item_id in self.work_items.get(phase_name, []):
            complete_issue(item_id, self.team_id)

        return update_phase_issue(
            phase_issue_id=phase_id,
            team_id=self.team_id,
            status="completed",
            progress_message=summary,
        )

    def fail_phase(self, phase_name: str, error_message: str) -> bool:
        """Mark a phase as failed."""
        if phase_name not in self.phase_issues:
            return False

        phase_id = self.phase_issues[phase_name].get("id")
        if not phase_id or not self.team_id:
            return False

        # Also create error issue
        create_error_issue(
            project_id=self.project_id,
            phase=phase_name,
            error_message=error_message,
            execution_id=self.execution_id,
        )

        return update_phase_issue(
            phase_issue_id=phase_id,
            team_id=self.team_id,
            status="failed",
            progress_message=error_message,
        )

    def block_phase(self, phase_name: str, reason: str) -> bool:
        """Mark a phase as blocked (e.g., awaiting approval)."""
        if phase_name not in self.phase_issues:
            return False

        phase_id = self.phase_issues[phase_name].get("id")
        if not phase_id or not self.team_id:
            return False

        return update_phase_issue(
            phase_issue_id=phase_id,
            team_id=self.team_id,
            status="blocked",
            progress_message=reason,
        )

    def add_work_items(
        self,
        phase_name: str,
        items: list[dict],
    ) -> list[dict]:
        """
        Add work item issues under a phase.

        Args:
            phase_name: The phase these items belong to
            items: List of {"title": str, "description": str, "priority": int}

        Returns:
            List of created issue dicts
        """
        if phase_name not in self.phase_issues:
            return []

        phase_id = self.phase_issues[phase_name].get("id")
        if not phase_id or not self.team_id:
            return []

        label = PHASE_ISSUE_CONFIG.get(phase_name, {}).get("label", "phase")

        created = create_work_items(
            project_id=self.project_id,
            team_id=self.team_id,
            phase_issue_id=phase_id,
            work_items=items,
            label=label,
        )

        # Track created items
        if phase_name not in self.work_items:
            self.work_items[phase_name] = []
        self.work_items[phase_name].extend([i.get("id") for i in created if i.get("id")])

        return created

    def start_work_item(self, issue_id: str) -> bool:
        """Mark a work item as in-progress."""
        if not self.team_id:
            return False
        return start_issue(issue_id, self.team_id)

    def complete_work_item(self, issue_id: str) -> bool:
        """Mark a work item as done."""
        if not self.team_id:
            return False
        return complete_issue(issue_id, self.team_id)

    def get_phase_issue_id(self, phase_name: str) -> Optional[str]:
        """Get the issue ID for a phase."""
        return self.phase_issues.get(phase_name, {}).get("id")
