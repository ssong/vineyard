"""Research Enrichment Agent - Personas, SEO, and competitor analysis."""

from typing import Any, Optional

from src.agents.base import BaseAgent
from src.config.prompts import RESEARCH_ENRICHMENT_PROMPT
from src.models import (
    CompetitorFeatureMatrix,
    FactoryState,
    ResearchEnrichmentOutput,
    SEOStrategy,
    UserPersona,
)
from src.tools import llm, miro

# Known placeholder values that should not be passed to LLM prompts
PLACEHOLDER_VALUES = {
    "Target users",
    "Unique approach",
    "Manual process",
    "Competition",
    "Growing market",
    "Unnamed Project",
}


def _is_placeholder(value: Optional[str]) -> bool:
    """Check if a value is a known placeholder."""
    if not value:
        return True
    return value.strip() in PLACEHOLDER_VALUES


def _is_placeholder_list(values: list[str]) -> bool:
    """Check if a list contains only placeholder values or is empty."""
    if not values:
        return True
    return all(_is_placeholder(v) for v in values)


class ResearchEnrichmentAgent(BaseAgent):
    """Agent for enriching opportunity with deeper research."""

    name = "ResearchEnrichmentAgent"
    domain = "product"

    def run(self, state: FactoryState) -> ResearchEnrichmentOutput:
        """
        Enrich opportunity with personas, SEO strategy, and competitor analysis.
        """
        self.log_start()

        opp = state.handoff.opportunity
        validation = state.handoff.validation

        # Log placeholder detection
        placeholders_detected = []
        if _is_placeholder(opp.target_market_description):
            placeholders_detected.append("target_market_description")
        if _is_placeholder(opp.differentiation_angle):
            placeholders_detected.append("differentiation_angle")
        if _is_placeholder(opp.problem_statement):
            placeholders_detected.append("problem_statement")
        if _is_placeholder_list(opp.direct_competitors):
            placeholders_detected.append("direct_competitors")
        if _is_placeholder_list(opp.competitor_weaknesses):
            placeholders_detected.append("competitor_weaknesses")

        if placeholders_detected:
            self.logger.warning(
                f"Placeholder values detected and will be omitted from prompts: {placeholders_detected}. "
                "LLM will research these values based on product name and description."
            )

        # Generate personas
        personas = self._generate_personas(opp)

        # Generate competitor matrix
        competitor_matrix = self._generate_competitor_matrix(opp)

        # Create Miro competitive landscape
        miro_url = self._create_competitive_landscape(opp, competitor_matrix)

        # Generate SEO strategy
        seo_strategy = self._generate_seo_strategy(opp)

        # Generate positioning statement
        positioning = self._generate_positioning(opp, competitor_matrix)
        # Note: Linear task tracking is now handled at the runner level

        output = ResearchEnrichmentOutput(
            personas=personas,
            primary_persona=personas[0].name if personas else "",
            competitor_matrix=competitor_matrix,
            competitive_landscape_miro_url=miro_url,
            positioning_statement=positioning,
            seo_strategy=seo_strategy,
        )

        self.log_complete()
        return output

    def _generate_personas(self, opp) -> list[UserPersona]:
        """Generate detailed user personas."""
        # Build context, skipping placeholder values
        context_lines = [
            f"PRODUCT: {opp.name}",
            f"DESCRIPTION: {opp.detailed_description}",
            f"TARGET SEGMENT: {opp.target_segment}",
        ]

        if not _is_placeholder(opp.target_market_description):
            context_lines.append(f"TARGET MARKET: {opp.target_market_description}")

        if not _is_placeholder(opp.problem_statement):
            context_lines.append(f"PROBLEM: {opp.problem_statement}")

        context = "\n".join(context_lines)

        user_prompt = f"""Create 3-5 detailed user personas for this product:

{context}

Research and identify the most likely target users based on the product description. For each persona, provide JSON array with:
{{
    "personas": [
        {{
            "name": "Persona Name",
            "role": "Job title / role",
            "demographics": "Brief demographic context",
            "goals": ["goal1", "goal2"],
            "frustrations": ["frustration1", "frustration2"],
            "jobs_to_be_done": ["When [situation], I want to [motivation], so I can [outcome]"],
            "willingness_to_pay": "$X-$Y/month",
            "acquisition_channels": ["channel1", "channel2"]
        }}
    ]
}}"""

        try:
            result = llm.generate_json(
                RESEARCH_ENRICHMENT_PROMPT, user_prompt, model=llm.MODEL_OPUS
            )
            personas = []

            for p in result.get("personas", [])[:5]:
                persona = UserPersona(
                    name=p.get("name", "Unknown"),
                    role=p.get("role", ""),
                    demographics=p.get("demographics", ""),
                    goals=p.get("goals", []),
                    frustrations=p.get("frustrations", []),
                    jobs_to_be_done=p.get("jobs_to_be_done", []),
                    willingness_to_pay=p.get("willingness_to_pay", "$0"),
                    acquisition_channels=p.get("acquisition_channels", []),
                )
                personas.append(persona)

            return personas

        except Exception as e:
            self.logger.error(f"Failed to generate personas: {e}")
            return [
                UserPersona(
                    name="Default Persona",
                    role=opp.target_segment,
                    demographics="",
                    goals=["Solve the problem"],
                    frustrations=[opp.problem_statement],
                    jobs_to_be_done=[],
                    willingness_to_pay=f"${opp.suggested_price_mid/100}/month",
                    acquisition_channels=["organic search"],
                )
            ]

    def _generate_competitor_matrix(self, opp) -> list[CompetitorFeatureMatrix]:
        """Generate detailed competitor analysis."""
        # Build context, skipping placeholder values
        context_lines = [f"PRODUCT: {opp.name}"]

        has_competitors = not _is_placeholder_list(opp.direct_competitors)
        if has_competitors:
            context_lines.append(f"KNOWN COMPETITORS: {', '.join(opp.direct_competitors)}")

        if not _is_placeholder(opp.differentiation_angle):
            context_lines.append(f"DIFFERENTIATION: {opp.differentiation_angle}")

        if not _is_placeholder_list(opp.competitor_weaknesses):
            context_lines.append(f"COMPETITOR WEAKNESSES: {', '.join(opp.competitor_weaknesses)}")

        context = "\n".join(context_lines)

        # If no competitors provided, ask LLM to research them
        research_instruction = ""
        if not has_competitors:
            research_instruction = "First, research and identify 3-5 direct competitors in this space. "

        user_prompt = f"""Analyze competitors for this product:

{context}

{research_instruction}For each competitor, provide JSON:
{{
    "competitors": [
        {{
            "competitor_name": "Name",
            "website": "https://...",
            "pricing_tiers": [
                {{"name": "Free", "price": 0, "features": ["feature1"]}},
                {{"name": "Pro", "price": 29, "features": ["feature1", "feature2"]}}
            ],
            "feature_comparison": {{"Feature A": true, "Feature B": false}},
            "key_strengths": ["strength1"],
            "key_gaps": ["gap1"],
            "review_summary": "Brief summary of user sentiment"
        }}
    ]
}}"""

        try:
            result = llm.generate_json(
                RESEARCH_ENRICHMENT_PROMPT, user_prompt, model=llm.MODEL_OPUS
            )
            competitors = []

            for c in result.get("competitors", []):
                comp = CompetitorFeatureMatrix(
                    competitor_name=c.get("competitor_name", "Unknown"),
                    website=c.get("website", ""),
                    pricing_tiers=c.get("pricing_tiers", []),
                    feature_comparison=c.get("feature_comparison", {}),
                    key_strengths=c.get("key_strengths", []),
                    key_gaps=c.get("key_gaps", []),
                    review_summary=c.get("review_summary", ""),
                )
                competitors.append(comp)

            return competitors

        except Exception as e:
            self.logger.error(f"Failed to generate competitor matrix: {e}")
            return []

    def _create_competitive_landscape(
        self, opp, competitors: list[CompetitorFeatureMatrix]
    ) -> str:
        """Create Miro competitive landscape board."""
        try:
            comp_data = [
                {
                    "name": c.competitor_name,
                    "price_position": 50,  # Would calculate from pricing
                    "feature_score": 50,
                    "is_target": False,
                }
                for c in competitors
            ]

            # Add our product
            comp_data.append(
                {
                    "name": opp.name,
                    "price_position": 40,  # Position ourselves competitively
                    "feature_score": 70,
                    "is_target": True,
                }
            )

            return miro.create_competitive_landscape(
                f"Competitive Landscape: {opp.name}", comp_data
            )

        except Exception as e:
            self.logger.error(f"Failed to create Miro board: {e}")
            return ""

    def _generate_seo_strategy(self, opp) -> SEOStrategy:
        """Generate SEO and keyword strategy."""
        # Build context, skipping placeholder values
        context_lines = [
            f"PRODUCT: {opp.name}",
            f"DESCRIPTION: {opp.one_liner}",
        ]

        if not _is_placeholder(opp.target_market_description):
            context_lines.append(f"TARGET: {opp.target_market_description}")

        if not _is_placeholder_list(opp.direct_competitors):
            context_lines.append(f"COMPETITORS: {', '.join(opp.direct_competitors)}")

        context = "\n".join(context_lines)

        user_prompt = f"""Create an SEO strategy for this product:

{context}

Research relevant keywords and competitors in this space. Provide JSON:
{{
    "primary_keywords": [
        {{"keyword": "keyword phrase", "volume": 1200, "difficulty": "low"}}
    ],
    "long_tail_keywords": ["long tail phrase 1"],
    "content_opportunities": ["Blog post idea 1"],
    "competitor_ranking_gaps": ["Keywords competitors rank for we can target"],
    "estimated_organic_potential": "X-Y visitors/month in 6 months"
}}"""

        try:
            result = llm.generate_json(
                RESEARCH_ENRICHMENT_PROMPT, user_prompt, model=llm.MODEL_OPUS
            )

            return SEOStrategy(
                primary_keywords=result.get("primary_keywords", []),
                long_tail_keywords=result.get("long_tail_keywords", []),
                content_opportunities=result.get("content_opportunities", []),
                competitor_ranking_gaps=result.get("competitor_ranking_gaps", []),
                estimated_organic_potential=result.get(
                    "estimated_organic_potential", "Unknown"
                ),
            )

        except Exception as e:
            self.logger.error(f"Failed to generate SEO strategy: {e}")
            return SEOStrategy(
                primary_keywords=[],
                long_tail_keywords=[],
                content_opportunities=[],
                competitor_ranking_gaps=[],
                estimated_organic_potential="Unknown",
            )

    def _generate_positioning(
        self, opp, competitors: list[CompetitorFeatureMatrix]
    ) -> str:
        """Generate positioning statement."""
        # Build context, skipping placeholder values
        context_lines = [
            f"PRODUCT: {opp.name}",
            f"DESCRIPTION: {opp.detailed_description}",
        ]

        if not _is_placeholder(opp.differentiation_angle):
            context_lines.append(f"DIFFERENTIATION: {opp.differentiation_angle}")

        if not _is_placeholder(opp.target_market_description):
            context_lines.append(f"TARGET: {opp.target_market_description}")

        # Only include competitor gaps if we have real competitor data
        competitor_gaps = [g for c in competitors for g in c.key_gaps][:5]
        if competitor_gaps:
            context_lines.append(f"COMPETITOR GAPS: {', '.join(competitor_gaps)}")

        context = "\n".join(context_lines)

        user_prompt = f"""Write a positioning statement for this product:

{context}

Based on the product and any competitor analysis, craft a compelling positioning statement.
Format: "For [target customer] who [statement of need], [product name] is a [product category] that [key benefit]. Unlike [competitors], we [key differentiator]."
"""

        try:
            return llm.generate(
                RESEARCH_ENRICHMENT_PROMPT, user_prompt, model=llm.MODEL_OPUS
            )
        except Exception as e:
            self.logger.error(f"Failed to generate positioning: {e}")
            return f"{opp.name}: A solution for {opp.target_segment}"

