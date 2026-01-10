"""Design Agent - PRD, user flows, and feature specs."""

from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import DESIGN_AGENT_PROMPT
from src.models import (
    DesignOutput,
    FactoryState,
    FeatureSpec,
    ResearchEnrichmentOutput,
)
from src.tools import linear, llm, miro


class DesignAgent(BaseAgent):
    """Agent for creating product design artifacts."""

    name = "DesignAgent"
    domain = "product"

    def run(self, state: FactoryState) -> DesignOutput:
        """
        Generate PRD, user flows, and feature specifications.
        """
        self.log_start()

        opp = state.handoff.opportunity
        research = self.get_previous_output(state, "research_enrichment")

        # Generate PRD
        prd = self._generate_prd(opp, research)

        # Generate user flows
        user_flows = self._generate_user_flows(opp, research)

        # Create Miro user flow board
        miro_url = self._create_user_flow_board(opp, user_flows)

        # Generate feature specs
        features = self._generate_feature_specs(opp, research)

        # Generate UI copy
        ui_copy = self._generate_ui_copy(opp, research)

        # Create Linear issues
        linear_issues = self._create_linear_issues(state, features)

        output = DesignOutput(
            prd_markdown=prd,
            user_flows=user_flows,
            user_flow_miro_url=miro_url,
            features=features,
            ui_copy=ui_copy,
            linear_issues=linear_issues,
        )

        self.log_complete()
        return output

    def _generate_prd(self, opp, research: ResearchEnrichmentOutput) -> str:
        """Generate comprehensive PRD."""
        personas_text = ""
        if research and research.personas:
            personas_text = "\n".join(
                [f"- {p.name}: {p.role}" for p in research.personas]
            )

        user_prompt = f"""Write a comprehensive PRD for this product:

PRODUCT: {opp.name}
ONE-LINER: {opp.one_liner}
DESCRIPTION: {opp.detailed_description}
PROBLEM: {opp.problem_statement}
TARGET: {opp.target_market_description}
PERSONAS:
{personas_text}

PRICING:
- Low: ${opp.suggested_price_low/100}/month
- Mid: ${opp.suggested_price_mid/100}/month
- High: ${opp.suggested_price_high/100}/month

Write a complete PRD in markdown format with:
1. Problem Statement
2. Target Users (reference personas)
3. Goals and Success Metrics
4. Core Features (P0, P1, P2 priorities)
5. User Stories
6. Out of Scope
7. Technical Considerations
8. Open Questions
"""

        try:
            return llm.generate(
                DESIGN_AGENT_PROMPT, user_prompt, model=llm.MODEL_OPUS
            )
        except Exception as e:
            self.logger.error(f"Failed to generate PRD: {e}")
            return f"# {opp.name} PRD\n\n## Problem Statement\n{opp.problem_statement}"

    def _generate_user_flows(self, opp, research: ResearchEnrichmentOutput) -> list[dict]:
        """Generate user flow definitions."""
        user_prompt = f"""Define key user flows for this product:

PRODUCT: {opp.name}
PROBLEM: {opp.problem_statement}
BUSINESS MODEL: {opp.business_model}

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

    def _create_user_flow_board(self, opp, user_flows: list[dict]) -> str:
        """Create Miro user flow visualization."""
        try:
            board = miro.create_board(
                f"User Flows: {opp.name}",
                "User flow diagrams",
            )
            board_id = board.get("id", "mock-id")

            # Create a frame for each flow
            y_offset = 0
            for flow in user_flows:
                miro.create_frame(
                    board_id,
                    flow.get("name", "Flow"),
                    0,
                    y_offset,
                )

                # Create step boxes
                x_offset = 0
                for step in flow.get("steps", []):
                    miro.create_shape(
                        board_id,
                        f"{step.get('step', 0)}. {step.get('action', '')}",
                        "rectangle",
                        x_offset,
                        y_offset + 100,
                        180,
                        80,
                    )
                    x_offset += 220

                y_offset += 700

            return board.get("viewLink", "")

        except Exception as e:
            self.logger.error(f"Failed to create Miro board: {e}")
            return ""

    def _generate_feature_specs(
        self, opp, research: ResearchEnrichmentOutput
    ) -> list[FeatureSpec]:
        """Generate detailed feature specifications."""
        user_prompt = f"""Create feature specifications for this product:

PRODUCT: {opp.name}
DESCRIPTION: {opp.detailed_description}
KEY COMPONENTS: {', '.join(opp.key_technical_components)}
BUILD COMPLEXITY: {opp.build_complexity}

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

    def _generate_ui_copy(self, opp, research: ResearchEnrichmentOutput) -> dict[str, str]:
        """Generate UI copy."""
        user_prompt = f"""Generate UI copy for this product:

PRODUCT: {opp.name}
ONE-LINER: {opp.one_liner}
TARGET: {opp.target_market_description}

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
            return {"headline": opp.one_liner}

    def _create_linear_issues(
        self, state: FactoryState, features: list[FeatureSpec]
    ) -> list[str]:
        """Create Linear issues for design artifacts."""
        try:
            project = linear.get_project(state.handoff.linear_project_id)
            team_id = project.get("teams", {}).get("nodes", [{}])[0].get("id", "")

            if not team_id:
                return []

            issues = [
                {
                    "title": "[Design] PRD Complete",
                    "description": "Product Requirements Document has been generated.",
                },
                {
                    "title": "[Design] User Flows Complete",
                    "description": "User flow diagrams created in Miro.",
                },
            ]

            # Add issues for P0 features
            for feature in features:
                if feature.priority == "P0":
                    issues.append(
                        {
                            "title": f"[Design] Feature Spec: {feature.name}",
                            "description": f"{feature.description}\n\n"
                            f"**User Stories:**\n"
                            + "\n".join([f"- {s}" for s in feature.user_stories]),
                        }
                    )

            return linear.create_issues_batch(
                state.handoff.linear_project_id, team_id, issues
            )

        except Exception as e:
            self.logger.error(f"Failed to create Linear issues: {e}")
            return []
