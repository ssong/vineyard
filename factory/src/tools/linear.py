"""Linear API client for project management."""

import logging
from typing import Optional

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

LINEAR_API_URL = "https://api.linear.app/graphql"


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


def create_issue(
    project_id: str,
    team_id: str,
    title: str,
    description: str,
    labels: Optional[list[str]] = None,
    priority: int = 2,
) -> dict:
    """Create an issue in Linear."""
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

    variables = {
        "input": {
            "projectId": project_id,
            "teamId": team_id,
            "title": title,
            "description": description,
            "priority": priority,
        }
    }

    data = _make_request(mutation, variables)
    result = data.get("issueCreate", {})

    if result.get("success"):
        return result.get("issue", {})
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
    """Update the status of an issue."""
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
            "body": body,
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
