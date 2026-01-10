"""Linear API client for project management."""

import logging
from typing import Optional

import httpx

from src.config import settings
from src.models import OpportunityReport

logger = logging.getLogger(__name__)

LINEAR_API_URL = "https://api.linear.app/graphql"


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

    project_description = f"""# {opp.name}

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

    variables = {
        "input": {
            "name": opp.name,
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

    issues_to_create = [
        {
            "title": f"[Research] Market Analysis Complete",
            "description": (
                f"Market research completed by Vineyard Research Agent.\n\n"
                f"**4U Score:** {opp.four_u_score}/100\n"
                f"**Competitors:** {', '.join(opp.direct_competitors[:3])}\n"
                f"**Differentiation:** {opp.differentiation_angle}"
            ),
            "labels": ["research"],
        },
        {
            "title": f"[Research] Opportunity Selected",
            "description": (
                f"**{opp.name}** selected for development.\n\n"
                f"**Recommendation:** {opp_report.recommendation.value}\n\n"
                f"{opp_report.recommendation_rationale}"
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
            variables = {
                "input": {
                    "title": issue["title"],
                    "description": issue["description"],
                    "teamId": team_id,
                    "projectId": project_id,
                }
            }
            _make_request(create_issue_mutation, variables)
        except Exception as e:
            logger.warning(f"Failed to create issue '{issue['title']}': {e}")
