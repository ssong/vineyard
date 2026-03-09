"""Design Agent - PRD enhancement, user flows, and feature specs."""

from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import DESIGN_AGENT_PROMPT
from src.models import (
    DesignOutput,
    FactoryState,
    FeatureSpec,
    PRDAnalysisOutput,
)
from src.tools import llm


class DesignAgent(BaseAgent):
    """Agent for creating product design artifacts."""

    name = "DesignAgent"
    domain = "product"

    def run(self, state: FactoryState) -> DesignOutput:
        """
        Enhance PRD, generate user flows, and feature specifications.
        """
        self.log_start()

        prd_input = state.handoff.prd_input
        prd_analysis = self.get_previous_output(state, "prd_analysis")

        # Enhance PRD with structured sections
        prd = self._enhance_prd(prd_input, prd_analysis)

        # Generate user flows
        user_flows = self._generate_user_flows(prd_input, prd_analysis)

        # Generate feature specs
        features = self._generate_feature_specs(prd_input, prd_analysis)

        # Generate UI copy
        ui_copy = self._generate_ui_copy(prd_input, prd_analysis)

        output = DesignOutput(
            prd_markdown=prd,
            user_flows=user_flows,
            features=features,
            ui_copy=ui_copy,
        )

        self.log_complete()
        return output

    def _enhance_prd(self, prd_input, prd_analysis: PRDAnalysisOutput) -> str:
        """Enhance the enriched PRD with structured design sections."""
        enriched_prd = prd_analysis.enriched_prd_markdown if prd_analysis else prd_input.prd_text
        target_users = ", ".join(prd_analysis.target_users) if prd_analysis and prd_analysis.target_users else "Target users"
        core_problem = prd_analysis.core_problem if prd_analysis else ""

        user_prompt = f"""Enhance this PRD with structured product design sections:

PRODUCT: {prd_input.name}
CORE PROBLEM: {core_problem}
TARGET USERS: {target_users}

ENRICHED PRD:
{enriched_prd}

Take the enriched PRD and add:
1. Feature priority matrix (P0/P1/P2 with acceptance criteria)
2. Detailed user stories in Given/When/Then format
3. Success metrics with measurable targets
4. Edge cases and error scenarios
5. Information architecture

Output the complete enhanced PRD in markdown format.
"""

        try:
            return llm.generate(
                DESIGN_AGENT_PROMPT, user_prompt, model=llm.MODEL_OPUS
            )
        except Exception as e:
            self.logger.error(f"Failed to enhance PRD: {e}")
            return enriched_prd or f"# {prd_input.name} PRD\n\n{prd_input.prd_text}"

    def _generate_user_flows(self, prd_input, prd_analysis: PRDAnalysisOutput) -> list[dict]:
        """Generate user flow definitions."""
        enriched_prd = prd_analysis.enriched_prd_markdown if prd_analysis else prd_input.prd_text
        mvp_notes = prd_analysis.mvp_scope_notes if prd_analysis else ""

        user_prompt = f"""Define key user flows for this product:

PRODUCT: {prd_input.name}
PRD:
{enriched_prd[:3000]}

MVP SCOPE: {mvp_notes}

Generate JSON with user flows:
{{
    "flows": [
        {{
            "name": "Signup to Activation",
            "description": "New user signs up and reaches first value",
            "steps": [
                {{"step": 1, "action": "Land on homepage", "screen": "Landing Page"}},
                {{"step": 2, "action": "Click sign up", "screen": "Signup Modal"}}
            ],
            "success_metric": "User completes first [action]"
        }}
    ]
}}

Include flows for:
1. Signup to Activation
2. Core value loop
3. Upgrade flow
4. Key error/edge cases
"""

        try:
            result = llm.generate_json(
                DESIGN_AGENT_PROMPT, user_prompt, model=llm.MODEL_OPUS
            )
            return result.get("flows", [])
        except Exception as e:
            self.logger.error(f"Failed to generate user flows: {e}")
            return [{"name": "Default Flow", "steps": []}]

    def _generate_feature_specs(
        self, prd_input, prd_analysis: PRDAnalysisOutput
    ) -> list[FeatureSpec]:
        """Generate detailed feature specifications."""
        enriched_prd = prd_analysis.enriched_prd_markdown if prd_analysis else prd_input.prd_text
        tech_stack = prd_input.tech_stack_preference or "Rails + PostgreSQL"

        user_prompt = f"""Create feature specifications for this product:

PRODUCT: {prd_input.name}
TECH STACK: {tech_stack}

PRD:
{enriched_prd[:3000]}

Generate JSON with features:
{{
    "features": [
        {{
            "name": "Feature Name",
            "description": "What this feature does",
            "priority": "P0",
            "user_stories": [
                "As a [user], I want to [action], so that [benefit]"
            ],
            "acceptance_criteria": [
                "Given [context], when [action], then [result]"
            ],
            "technical_notes": "Key implementation considerations"
        }}
    ]
}}

Include P0 (MVP), P1 (post-launch), and P2 (future) features.
"""

        try:
            result = llm.generate_json(
                DESIGN_AGENT_PROMPT, user_prompt, model=llm.MODEL_OPUS
            )
            features = []

            for f in result.get("features", []):
                feature = FeatureSpec(
                    name=f.get("name", "Unknown"),
                    description=f.get("description", ""),
                    priority=f.get("priority", "P1"),
                    user_stories=f.get("user_stories", []),
                    acceptance_criteria=f.get("acceptance_criteria", []),
                    technical_notes=f.get("technical_notes", ""),
                )
                features.append(feature)

            return features

        except Exception as e:
            self.logger.error(f"Failed to generate features: {e}")
            return []

    def _generate_ui_copy(self, prd_input, prd_analysis: PRDAnalysisOutput) -> dict[str, str]:
        """Generate UI copy."""
        summary = prd_analysis.product_summary if prd_analysis else prd_input.prd_text[:200]
        target_users = ", ".join(prd_analysis.target_users) if prd_analysis and prd_analysis.target_users else "Target users"

        user_prompt = f"""Generate UI copy for this product:

PRODUCT: {prd_input.name}
SUMMARY: {summary}
TARGET USERS: {target_users}

Generate JSON with UI copy:
{{
    "headline": "Main landing page headline",
    "subheadline": "Supporting text",
    "cta_primary": "Primary CTA button text",
    "cta_secondary": "Secondary CTA text",
    "onboarding_welcome": "Welcome message for new users",
    "onboarding_step1": "First onboarding step text",
    "success_message": "Generic success message",
    "error_generic": "Generic error message",
    "empty_state": "Empty state message"
}}
"""

        try:
            return llm.generate_json(
                DESIGN_AGENT_PROMPT, user_prompt, model=llm.MODEL_OPUS
            )
        except Exception as e:
            self.logger.error(f"Failed to generate UI copy: {e}")
            return {"headline": prd_input.name}
