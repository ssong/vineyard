"""Growth Agent - Analytics, experiments, and optimization."""

from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import GROWTH_AGENT_PROMPT
from src.models import FactoryState, GrowthExperiment
from src.tools import linear, llm


class GrowthAgent(BaseAgent):
    """Agent for growth optimization and experimentation."""

    name = "GrowthAgent"
    domain = "gtm"

    def run(self, state: FactoryState) -> dict[str, Any]:
        """
        Generate growth experiments, analytics setup, and playbook.
        """
        self.log_start()

        opp = state.handoff.opportunity

        # Generate experiment hypotheses
        experiments = self._generate_experiments(opp)

        # Generate analytics events
        analytics_events = self._generate_analytics_events(opp)

        # Generate growth playbook
        playbook = self._generate_growth_playbook(opp)

        # Generate weekly report template
        report_template = self._generate_report_template(opp)

        # Create Linear issues
        linear_issues = self._create_linear_issues(state, experiments)

        output = {
            "experiments": experiments,
            "analytics_events": analytics_events,
            "growth_playbook": playbook,
            "weekly_report_template": report_template,
            "linear_issues": linear_issues,
        }

        self.log_complete()
        return output

    def _generate_experiments(self, opp) -> list[GrowthExperiment]:
        """Generate growth experiment hypotheses."""
        user_prompt = f"""Generate growth experiments for:

PRODUCT: {opp.name}
BUSINESS MODEL: {opp.business_model}
TARGET: {opp.target_market_description}
PRICING: ${opp.suggested_price_low/100} - ${opp.suggested_price_high/100}/month

Generate JSON:
{{
    "experiments": [
        {{
            "name": "Trial Length Experiment",
            "hypothesis": "7-day trial will have higher conversion than 14-day",
            "metric": "trial_to_paid_conversion",
            "success_criteria": "10% relative improvement",
            "implementation_notes": "Use feature flag for trial length"
        }}
    ]
}}

Include experiments for:
- Pricing/trial optimization
- Onboarding improvements
- Activation rate optimization
- Retention/engagement
- Viral/referral mechanics
"""

        try:
            result = llm.generate_json(GROWTH_AGENT_PROMPT, user_prompt)
            experiments = []

            for exp in result.get("experiments", []):
                experiments.append(
                    GrowthExperiment(
                        name=exp.get("name", "Experiment"),
                        hypothesis=exp.get("hypothesis", ""),
                        metric=exp.get("metric", ""),
                        success_criteria=exp.get("success_criteria", ""),
                        implementation_notes=exp.get("implementation_notes", ""),
                    )
                )

            return experiments

        except Exception as e:
            self.logger.error(f"Failed to generate experiments: {e}")
            return []

    def _generate_analytics_events(self, opp) -> list[dict]:
        """Generate analytics event definitions."""
        user_prompt = f"""Generate analytics events for:

PRODUCT: {opp.name}
BUSINESS MODEL: {opp.business_model}

Generate JSON:
{{
    "events": [
        {{
            "name": "user_signed_up",
            "description": "User completes signup",
            "properties": ["signup_source", "plan_selected"],
            "trigger": "On successful signup"
        }},
        {{
            "name": "feature_used",
            "description": "User uses a core feature",
            "properties": ["feature_name", "time_spent"],
            "trigger": "On feature interaction"
        }}
    ]
}}

Include events for:
- User lifecycle (signup, activation, churn)
- Core feature usage
- Conversion points (trial, paid, upgrade)
- Engagement (session, feature use)
"""

        try:
            result = llm.generate_json(GROWTH_AGENT_PROMPT, user_prompt)
            return result.get("events", [])
        except Exception as e:
            self.logger.error(f"Failed to generate analytics events: {e}")
            return []

    def _generate_growth_playbook(self, opp) -> str:
        """Generate growth strategy playbook."""
        user_prompt = f"""Generate a growth playbook for:

PRODUCT: {opp.name}
TARGET: {opp.target_market_description}
BUSINESS MODEL: {opp.business_model}

Write a markdown growth playbook covering:
1. North Star Metric
2. Key Growth Levers
3. Acquisition Channels (prioritized)
4. Activation Strategy
5. Retention Playbook
6. Monetization Optimization
7. Referral Mechanics
8. Weekly/Monthly Rituals

Keep it actionable and specific to this product.
"""

        try:
            return llm.generate(GROWTH_AGENT_PROMPT, user_prompt)
        except Exception as e:
            self.logger.error(f"Failed to generate playbook: {e}")
            return f"# {opp.name} Growth Playbook\n\n[To be generated]"

    def _generate_report_template(self, opp) -> str:
        """Generate weekly metrics report template."""
        user_prompt = f"""Generate a weekly metrics report template for:

PRODUCT: {opp.name}
BUSINESS MODEL: {opp.business_model}

Write a markdown template with:
1. Key Metrics Summary (week over week)
2. Funnel Analysis
3. Experiment Results
4. Wins & Learnings
5. Focus for Next Week

Use placeholder values like [X%] or [N users].
"""

        try:
            return llm.generate(GROWTH_AGENT_PROMPT, user_prompt)
        except Exception as e:
            self.logger.error(f"Failed to generate report template: {e}")
            return "# Weekly Metrics Report\n\n[Template to be generated]"

    def _create_linear_issues(
        self, state: FactoryState, experiments: list[GrowthExperiment]
    ) -> list[str]:
        """Create Linear issues for growth tasks."""
        try:
            project = linear.get_project(state.handoff.linear_project_id)
            team_id = project.get("teams", {}).get("nodes", [{}])[0].get("id", "")

            if not team_id:
                return []

            issues = [
                {
                    "title": "[Growth] Analytics Setup",
                    "description": "Implement analytics events tracking.",
                    "labels": ["growth"],
                },
                {
                    "title": "[Growth] Growth Playbook Ready",
                    "description": "Growth strategy document completed.",
                    "labels": ["growth"],
                },
            ]

            # Add experiment issues
            for exp in experiments[:3]:
                issues.append({
                    "title": f"[Growth] Experiment: {exp.name}",
                    "description": f"**Hypothesis:** {exp.hypothesis}\n\n"
                    f"**Metric:** {exp.metric}\n"
                    f"**Success Criteria:** {exp.success_criteria}\n\n"
                    f"**Implementation:** {exp.implementation_notes}",
                    "labels": ["growth", "experiment"],
                })

            return linear.create_issues_batch(
                state.handoff.linear_project_id, team_id, issues
            )

        except Exception as e:
            self.logger.error(f"Failed to create Linear issues: {e}")
            return []
