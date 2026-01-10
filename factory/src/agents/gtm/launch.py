"""Launch Agent - Product Hunt and launch coordination."""

from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import LAUNCH_AGENT_PROMPT
from src.models import FactoryState, ProductHuntListing
from src.tools import linear, llm


class LaunchAgent(BaseAgent):
    """Agent for coordinating product launch."""

    name = "LaunchAgent"
    domain = "gtm"

    def run(self, state: FactoryState) -> dict[str, Any]:
        """
        Prepare Product Hunt listing and launch checklist.
        """
        self.log_start()

        opp = state.handoff.opportunity
        launch_prefs = state.handoff.launch_preferences

        # Generate Product Hunt listing
        ph_listing = self._generate_ph_listing(opp)

        # Generate launch checklist
        checklist = self._generate_launch_checklist(opp, launch_prefs)

        # Generate response templates
        templates = self._generate_response_templates(opp)

        # Schedule coordination
        schedule = self._generate_launch_schedule(launch_prefs)

        # Create Linear issues
        linear_issues = self._create_linear_issues(state, checklist)

        output = {
            "product_hunt_listing": ph_listing,
            "launch_checklist": checklist,
            "response_templates": templates,
            "launch_schedule": schedule,
            "linear_issues": linear_issues,
        }

        self.log_complete()
        return output

    def _generate_ph_listing(self, opp) -> ProductHuntListing:
        """Generate Product Hunt listing content."""
        user_prompt = f"""Generate Product Hunt listing for:

PRODUCT: {opp.name}
ONE-LINER: {opp.one_liner}
DETAILED: {opp.detailed_description}
TARGET: {opp.target_market_description}
DIFFERENTIATION: {opp.differentiation_angle}

Generate JSON:
{{
    "tagline": "Max 60 characters tagline",
    "description": "2-3 paragraph description for PH page",
    "first_comment": "Maker's first comment (personal story, why you built this)",
    "topics": ["SaaS", "Productivity", "Developer Tools"]
}}

The tagline should be punchy and benefit-focused.
The first comment should be personal and authentic.
"""

        try:
            result = llm.generate_json(LAUNCH_AGENT_PROMPT, user_prompt)
            return ProductHuntListing(
                tagline=result.get("tagline", opp.one_liner)[:60],
                description=result.get("description", ""),
                first_comment=result.get("first_comment", ""),
                topics=result.get("topics", ["SaaS"]),
            )
        except Exception as e:
            self.logger.error(f"Failed to generate PH listing: {e}")
            return ProductHuntListing(
                tagline=opp.one_liner[:60],
                description=opp.detailed_description,
                first_comment="",
                topics=["SaaS"],
            )

    def _generate_launch_checklist(self, opp, launch_prefs) -> list[dict]:
        """Generate comprehensive launch checklist."""
        user_prompt = f"""Generate launch checklist for:

PRODUCT: {opp.name}
LAUNCH ON PH: {launch_prefs.launch_on_product_hunt}
LAUNCH ON TWITTER: {launch_prefs.launch_on_twitter}
LAUNCH ON LINKEDIN: {launch_prefs.launch_on_linkedin}

Generate JSON:
{{
    "checklist": [
        {{
            "phase": "T-7 (1 week before)",
            "tasks": [
                {{"task": "Finalize landing page", "owner": "marketing"}},
                {{"task": "Test payment flow", "owner": "engineering"}}
            ]
        }},
        {{
            "phase": "T-1 (day before)",
            "tasks": []
        }},
        {{
            "phase": "Launch Day",
            "tasks": []
        }},
        {{
            "phase": "T+1 (day after)",
            "tasks": []
        }}
    ]
}}

Be comprehensive. Include:
- Pre-launch prep
- Day-of coordination
- Post-launch follow-up
"""

        try:
            result = llm.generate_json(LAUNCH_AGENT_PROMPT, user_prompt)
            return result.get("checklist", [])
        except Exception as e:
            self.logger.error(f"Failed to generate checklist: {e}")
            return []

    def _generate_response_templates(self, opp) -> dict[str, str]:
        """Generate response templates for launch day."""
        user_prompt = f"""Generate response templates for {opp.name} launch:

Generate JSON:
{{
    "thank_you": "Response to thank supporters",
    "question_answer": "Template for answering questions",
    "feature_request": "Response to feature requests",
    "pricing_question": "Response to pricing questions",
    "competitor_comparison": "Response when asked about competitors",
    "bug_report": "Response to bug reports during launch"
}}

Keep responses friendly, concise, and helpful.
"""

        try:
            return llm.generate_json(LAUNCH_AGENT_PROMPT, user_prompt)
        except Exception as e:
            self.logger.error(f"Failed to generate templates: {e}")
            return {}

    def _generate_launch_schedule(self, launch_prefs) -> dict:
        """Generate optimal launch timing schedule."""
        user_prompt = f"""Generate launch schedule:

LAUNCH ON PH: {launch_prefs.launch_on_product_hunt}
EMAIL PROVIDER: {launch_prefs.email_provider}

Generate JSON:
{{
    "optimal_launch_day": "Tuesday/Wednesday/Thursday",
    "optimal_time_pst": "00:01 PST for Product Hunt",
    "schedule": [
        {{"time": "00:01 PST", "action": "Product Hunt goes live"}},
        {{"time": "06:00 PST", "action": "First Twitter post"}},
        {{"time": "09:00 PST", "action": "LinkedIn post"}},
        {{"time": "12:00 PST", "action": "Email to list"}},
        {{"time": "15:00 PST", "action": "Twitter thread"}}
    ],
    "time_zone_notes": "Schedule based on US Pacific Time"
}}
"""

        try:
            return llm.generate_json(LAUNCH_AGENT_PROMPT, user_prompt)
        except Exception as e:
            self.logger.error(f"Failed to generate schedule: {e}")
            return {"optimal_launch_day": "Tuesday"}

    def _create_linear_issues(
        self, state: FactoryState, checklist: list
    ) -> list[str]:
        """Create Linear issues for launch tasks."""
        try:
            project = linear.get_project(state.handoff.linear_project_id)
            team_id = project.get("teams", {}).get("nodes", [{}])[0].get("id", "")

            if not team_id:
                return []

            issues = [
                {
                    "title": "[Launch] Product Hunt Listing Ready",
                    "description": "PH tagline, description, and first comment drafted.",
                }
            ]

            # Add checklist items as issues
            for phase in checklist:
                phase_name = phase.get("phase", "")
                for task in phase.get("tasks", [])[:3]:  # Limit per phase
                    issues.append({
                        "title": f"[Launch] {task.get('task', 'Task')}",
                        "description": f"**Phase:** {phase_name}\n**Owner:** {task.get('owner', 'TBD')}",
                        "labels": ["launch"],
                    })

            return linear.create_issues_batch(
                state.handoff.linear_project_id, team_id, issues[:10]
            )

        except Exception as e:
            self.logger.error(f"Failed to create Linear issues: {e}")
            return []
