"""Marketing Agent - Landing pages, emails, and social content."""

from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import MARKETING_AGENT_PROMPT
from src.models import (
    EmailSequence,
    FactoryState,
    SocialContent,
)
from src.tools import llm


class MarketingAgent(BaseAgent):
    """Agent for generating marketing content."""

    name = "MarketingAgent"
    domain = "gtm"

    def run(self, state: FactoryState) -> dict[str, Any]:
        """
        Generate landing page copy, email sequences, and social content.
        """
        self.log_start()

        opp = state.handoff.opportunity
        research = self.get_previous_output(state, "research_enrichment")

        # Generate landing page copy
        landing_copy = self._generate_landing_page_copy(opp, research)

        # Generate email sequences
        email_sequences = self._generate_email_sequences(opp, research)

        # Generate social content
        social = self._generate_social_content(opp)

        # Generate blog post outlines
        blog_outlines = self._generate_blog_outlines(opp, research)
        # Note: Linear task tracking is now handled at the runner level

        output = {
            "landing_page_copy": landing_copy,
            "email_sequences": email_sequences,
            "social_content": social,
            "blog_outlines": blog_outlines,
        }

        self.log_complete()
        return output

    def _generate_landing_page_copy(self, opp, research) -> dict:
        """Generate landing page copy."""
        personas_text = ""
        if research and research.personas:
            personas_text = "\n".join(
                [f"- {p.name}: {p.role}" for p in research.personas]
            )

        user_prompt = f"""Generate landing page copy for:

PRODUCT: {opp.name}
ONE-LINER: {opp.one_liner}
PROBLEM: {opp.problem_statement}
TARGET: {opp.target_market_description}
DIFFERENTIATION: {opp.differentiation_angle}
PRICING: ${opp.suggested_price_low/100} - ${opp.suggested_price_high/100}/month

PERSONAS:
{personas_text}

Generate JSON with landing page sections:
{{
    "hero": {{
        "headline": "Compelling headline (max 10 words)",
        "subheadline": "Supporting text (max 25 words)",
        "cta_primary": "Primary button text",
        "cta_secondary": "Secondary link text"
    }},
    "problem": {{
        "headline": "Problem section headline",
        "description": "2-3 sentences describing the pain"
    }},
    "solution": {{
        "headline": "Solution section headline",
        "description": "2-3 sentences about how we solve it"
    }},
    "features": [
        {{
            "title": "Feature name",
            "description": "Brief benefit-focused description",
            "icon": "suggested icon name"
        }}
    ],
    "social_proof": {{
        "headline": "Social proof section headline",
        "testimonial_template": "Template for testimonials"
    }},
    "pricing": {{
        "headline": "Pricing section headline",
        "subheadline": "Supporting pricing text"
    }},
    "cta_final": {{
        "headline": "Final CTA headline",
        "button_text": "Final button text"
    }}
}}
"""

        try:
            return llm.generate_json(MARKETING_AGENT_PROMPT, user_prompt)
        except Exception as e:
            self.logger.error(f"Failed to generate landing copy: {e}")
            return {"hero": {"headline": opp.one_liner}}

    def _generate_email_sequences(self, opp, research) -> list[EmailSequence]:
        """Generate email sequences."""
        user_prompt = f"""Generate email sequences for:

PRODUCT: {opp.name}
DESCRIPTION: {opp.detailed_description}
TARGET: {opp.target_market_description}

Generate JSON with email sequences:
{{
    "sequences": [
        {{
            "name": "Welcome Sequence",
            "emails": [
                {{
                    "name": "Welcome Email",
                    "subject": "Welcome to {opp.name}! Here's how to get started",
                    "body_html": "<HTML content>",
                    "send_delay_hours": 0
                }},
                {{
                    "name": "Day 2 Tips",
                    "subject": "3 tips to get more from {opp.name}",
                    "body_html": "<HTML content>",
                    "send_delay_hours": 48
                }}
            ]
        }}
    ]
}}

Include:
1. Welcome sequence (5 emails over 2 weeks)
2. Activation nudge (for users who haven't engaged)
3. Feature announcement template
"""

        try:
            result = llm.generate_json(MARKETING_AGENT_PROMPT, user_prompt)
            sequences = []

            for seq in result.get("sequences", []):
                for email in seq.get("emails", []):
                    sequences.append(
                        EmailSequence(
                            name=email.get("name", "Email"),
                            subject=email.get("subject", ""),
                            body_html=email.get("body_html", ""),
                            send_delay_hours=email.get("send_delay_hours", 0),
                        )
                    )

            return sequences

        except Exception as e:
            self.logger.error(f"Failed to generate email sequences: {e}")
            return []

    def _generate_social_content(self, opp) -> SocialContent:
        """Generate social media content."""
        user_prompt = f"""Generate social media content for launch:

PRODUCT: {opp.name}
ONE-LINER: {opp.one_liner}
DIFFERENTIATION: {opp.differentiation_angle}

Generate JSON:
{{
    "twitter_thread": [
        "Tweet 1: Hook",
        "Tweet 2: Problem",
        "Tweet 3: Solution",
        "Tweet 4: Feature 1",
        "Tweet 5: Feature 2",
        "Tweet 6: CTA"
    ],
    "linkedin_post": "Full LinkedIn announcement post (2-3 paragraphs)",
    "twitter_launch_tweet": "Single launch tweet (max 280 chars)"
}}
"""

        try:
            result = llm.generate_json(MARKETING_AGENT_PROMPT, user_prompt)
            return SocialContent(
                twitter_thread=result.get("twitter_thread", []),
                linkedin_post=result.get("linkedin_post", ""),
                twitter_launch_tweet=result.get("twitter_launch_tweet", ""),
            )
        except Exception as e:
            self.logger.error(f"Failed to generate social content: {e}")
            return SocialContent(
                twitter_thread=[],
                linkedin_post="",
                twitter_launch_tweet="",
            )

    def _generate_blog_outlines(self, opp, research) -> list[dict]:
        """Generate SEO blog post outlines."""
        seo_keywords = []
        if research and research.seo_strategy:
            seo_keywords = research.seo_strategy.primary_keywords[:5]

        user_prompt = f"""Generate blog post outlines for SEO:

PRODUCT: {opp.name}
TARGET KEYWORDS: {seo_keywords}
PROBLEM: {opp.problem_statement}

Generate JSON with blog outlines:
{{
    "posts": [
        {{
            "title": "SEO-optimized title",
            "target_keyword": "primary keyword",
            "outline": ["Section 1", "Section 2", "Section 3"],
            "key_points": ["Point 1", "Point 2"]
        }}
    ]
}}

Generate 5 blog post outlines.
"""

        try:
            result = llm.generate_json(MARKETING_AGENT_PROMPT, user_prompt)
            return result.get("posts", [])
        except Exception as e:
            self.logger.error(f"Failed to generate blog outlines: {e}")
            return []
