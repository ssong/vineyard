"""Support Agent - FAQ, help docs, and ticket triage."""

from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import SUPPORT_AGENT_PROMPT
from src.models import FactoryState
from src.tools import llm


class SupportAgent(BaseAgent):
    """Agent for support infrastructure and documentation."""

    name = "SupportAgent"
    domain = "gtm"

    def run(self, state: FactoryState) -> dict[str, Any]:
        """
        Generate FAQ, help articles, and support templates.
        """
        self.log_start()

        opp = state.handoff.opportunity
        design = self.get_previous_output(state, "design")

        # Generate FAQ
        faq = self._generate_faq(opp, design)

        # Generate help articles
        help_articles = self._generate_help_articles(opp, design)

        # Generate ticket categories
        ticket_categories = self._generate_ticket_categories(opp)

        # Generate response templates
        response_templates = self._generate_response_templates(opp)
        # Note: Linear task tracking is now handled at the runner level

        output = {
            "faq": faq,
            "help_articles": help_articles,
            "ticket_categories": ticket_categories,
            "response_templates": response_templates,
        }

        self.log_complete()
        return output

    def _generate_faq(self, opp, design) -> list[dict]:
        """Generate FAQ content."""
        features_text = ""
        if design and design.features:
            features_text = ", ".join([f.name for f in design.features[:5]])

        user_prompt = f"""Generate FAQ for:

PRODUCT: {opp.name}
DESCRIPTION: {opp.detailed_description}
PRICING: ${opp.suggested_price_low/100} - ${opp.suggested_price_high/100}/month
FEATURES: {features_text}

Generate JSON:
{{
    "faq": [
        {{
            "category": "Getting Started",
            "questions": [
                {{
                    "question": "How do I sign up?",
                    "answer": "Clear, helpful answer"
                }}
            ]
        }}
    ]
}}

Include categories:
- Getting Started
- Account & Billing
- Features
- Technical/Troubleshooting
- Pricing & Plans
"""

        try:
            result = llm.generate_json(SUPPORT_AGENT_PROMPT, user_prompt)
            return result.get("faq", [])
        except Exception as e:
            self.logger.error(f"Failed to generate FAQ: {e}")
            return []

    def _generate_help_articles(self, opp, design) -> list[dict]:
        """Generate help center articles."""
        features = design.features if design else []

        user_prompt = f"""Generate help articles for:

PRODUCT: {opp.name}
FEATURES: {[f.name for f in features[:5]] if features else []}

Generate JSON:
{{
    "articles": [
        {{
            "title": "Getting Started with {opp.name}",
            "category": "Getting Started",
            "content_outline": ["Introduction", "Step 1", "Step 2", "Next Steps"],
            "estimated_read_time": "3 min"
        }}
    ]
}}

Include:
- Getting started guide
- Feature tutorials (one per major feature)
- Best practices
- Troubleshooting guide
"""

        try:
            result = llm.generate_json(SUPPORT_AGENT_PROMPT, user_prompt)
            return result.get("articles", [])
        except Exception as e:
            self.logger.error(f"Failed to generate help articles: {e}")
            return []

    def _generate_ticket_categories(self, opp) -> list[dict]:
        """Generate support ticket categories."""
        user_prompt = f"""Generate ticket categories for {opp.name}:

Generate JSON:
{{
    "categories": [
        {{
            "name": "Bug Report",
            "description": "Something isn't working as expected",
            "priority": "high",
            "sla_hours": 24,
            "auto_tags": ["bug"]
        }},
        {{
            "name": "Feature Request",
            "description": "Suggestion for new functionality",
            "priority": "low",
            "sla_hours": 72,
            "auto_tags": ["feature-request"]
        }}
    ]
}}

Include:
- Bug reports
- Feature requests
- Billing/account issues
- General questions
- Integration help
"""

        try:
            result = llm.generate_json(SUPPORT_AGENT_PROMPT, user_prompt)
            return result.get("categories", [])
        except Exception as e:
            self.logger.error(f"Failed to generate categories: {e}")
            return []

    def _generate_response_templates(self, opp) -> dict[str, str]:
        """Generate support response templates."""
        user_prompt = f"""Generate support response templates for {opp.name}:

Generate JSON:
{{
    "bug_acknowledgment": "Template for acknowledging a bug report",
    "bug_resolved": "Template for notifying bug is fixed",
    "feature_request_received": "Template for acknowledging feature request",
    "feature_shipped": "Template for notifying feature was built",
    "billing_inquiry": "Template for billing questions",
    "refund_approved": "Template for approving refund",
    "account_reset": "Template for password/account reset help",
    "closing_ticket": "Template for closing resolved tickets"
}}

Keep templates friendly, concise, and professional.
Use placeholders like {{customer_name}}, {{ticket_id}}.
"""

        try:
            return llm.generate_json(SUPPORT_AGENT_PROMPT, user_prompt)
        except Exception as e:
            self.logger.error(f"Failed to generate templates: {e}")
            return {}
