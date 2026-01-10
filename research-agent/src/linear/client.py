"""Linear API client for project management."""

import logging
from typing import Optional

import httpx

from src.config import settings
from src.models import OpportunityReport

logger = logging.getLogger(__name__)

LINEAR_API_URL = "https://api.linear.app/graphql"

# Linear API character limits
MAX_PROJECT_DESCRIPTION_LENGTH = 255
MAX_ISSUE_TITLE_LENGTH = 500
MAX_ISSUE_DESCRIPTION_LENGTH = 50000
MAX_COMMENT_LENGTH = 10000
MAX_LABEL_NAME_LENGTH = 50

# Cache for labels (cleared on module reload)
_labels_cache: dict[str, dict[str, str]] = {}


def _truncate(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to max_length, adding suffix if truncated."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def _make_request(query: str, variables: Optional[dict] = None) -> dict:
    """Make a GraphQL request to Linear API."""
    if not settings.linear_api_key:
        raise ValueError("LINEAR_API_KEY not configured")

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
        "opportunity": "#8B5CF6",   # Purple
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


def create_project_for_opportunity(opp_report: OpportunityReport) -> str:
    """
    Create a Linear project for the selected opportunity.

    Args:
        opp_report: The selected opportunity report

    Returns:
        URL to the created project
    """
    opp = opp_report.opportunity

    # Get first team (or could be configurable)
    teams = get_teams()
    if not teams:
        raise ValueError("No teams found in Linear workspace")

    team_id = teams[0]["id"]

    # Create project
    create_project_mutation = """
    mutation CreateProject($input: ProjectCreateInput!) {
        projectCreate(input: $input) {
            success
            project {
                id
                url
                name
            }
        }
    }
    """

    # Project description is limited to 255 chars by Linear API
    # Keep it concise - detailed info goes in project issues
    project_description = _truncate(
        f"{opp.one_liner} | Score: {opp.overall_score}/100 | {opp.build_complexity} complexity, {opp.estimated_build_weeks} weeks",
        MAX_PROJECT_DESCRIPTION_LENGTH,
    )

    variables = {
        "input": {
            "name": _truncate(opp.name, MAX_ISSUE_TITLE_LENGTH),
            "description": project_description,
            "teamIds": [team_id],
        }
    }

    data = _make_request(create_project_mutation, variables)
    project = data.get("projectCreate", {}).get("project", {})
    project_id = project.get("id")
    project_url = project.get("url", "")

    if not project_id:
        raise ValueError("Failed to create project")

    logger.info(f"Created Linear project: {project_url}")

    # Create initial issues
    _create_initial_issues(project_id, team_id, opp_report)

    return project_url


def _create_initial_issues(project_id: str, team_id: str, opp_report: OpportunityReport):
    """Create initial issues for the project."""
    opp = opp_report.opportunity

    # Ensure required labels exist
    label_ids = ensure_labels(team_id, ["research", "validation"])

    # Build detailed project overview (this content was previously in project description)
    project_overview = f"""# {opp.name}

{opp.one_liner}

## Problem Statement
{opp.problem_statement}

## Target Market
{opp.target_market_description}

## Scores
- Overall: {opp.overall_score}/100
- 4U Score: {opp.four_u_score}/100
- Solo Viability: {opp.solo_viability_score}/100
- Acquirability: {opp.acquirability_score}/100

## Build Estimate
- Complexity: {opp.build_complexity}
- Time: {opp.estimated_build_weeks} weeks

## Revenue Forecast (12 months)
- Conservative: ${opp_report.forecast.mrr_month_12_conservative/100:,.0f}/mo
- Moderate: ${opp_report.forecast.mrr_month_12_moderate/100:,.0f}/mo
- Optimistic: ${opp_report.forecast.mrr_month_12_optimistic/100:,.0f}/mo

---
*Created by Vineyard Research Agent*
"""

    issues_to_create = [
        {
            "title": "[Research] Project Overview",
            "description": _truncate(project_overview, MAX_ISSUE_DESCRIPTION_LENGTH),
            "labels": ["research"],
        },
        {
            "title": "[Research] Market Analysis Complete",
            "description": _truncate(
                f"Market research completed by Vineyard Research Agent.\n\n"
                f"**4U Score:** {opp.four_u_score}/100\n"
                f"**Competitors:** {', '.join(opp.direct_competitors[:3])}\n"
                f"**Differentiation:** {opp.differentiation_angle}",
                MAX_ISSUE_DESCRIPTION_LENGTH,
            ),
            "labels": ["research"],
        },
        {
            "title": "[Research] Opportunity Selected",
            "description": _truncate(
                f"**{opp.name}** selected for development.\n\n"
                f"**Recommendation:** {opp_report.recommendation.value}\n\n"
                f"{opp_report.recommendation_rationale}",
                MAX_ISSUE_DESCRIPTION_LENGTH,
            ),
            "labels": ["research"],
        },
    ]

    # Add next steps as issues
    for i, step in enumerate(opp_report.next_steps[:3], 1):
        issues_to_create.append({
            "title": f"[Validation] {step}",
            "description": f"Recommended validation step from research.\n\nPriority: {i}",
            "labels": ["validation"],
        })

    create_issue_mutation = """
    mutation CreateIssue($input: IssueCreateInput!) {
        issueCreate(input: $input) {
            success
            issue {
                id
                identifier
            }
        }
    }
    """

    for issue in issues_to_create:
        try:
            # Resolve label names to IDs
            issue_label_ids = [
                label_ids[l.lower()]
                for l in issue.get("labels", [])
                if l.lower() in label_ids
            ]

            input_data = {
                "title": issue["title"],
                "description": issue["description"],
                "teamId": team_id,
                "projectId": project_id,
            }

            if issue_label_ids:
                input_data["labelIds"] = issue_label_ids

            variables = {"input": input_data}
            result = _make_request(create_issue_mutation, variables)
            issue_data = result.get("issueCreate", {}).get("issue", {})
            logger.info(f"Created issue {issue_data.get('identifier')}: {issue['title']}")
        except Exception as e:
            logger.warning(f"Failed to create issue '{issue['title']}': {e}")
