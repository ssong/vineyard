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
