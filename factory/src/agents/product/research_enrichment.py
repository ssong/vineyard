"""Research Enrichment Agent - Personas, SEO, and competitor analysis."""

from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import RESEARCH_ENRICHMENT_PROMPT
from src.models import (
    CompetitorFeatureMatrix,
    FactoryState,
    ResearchEnrichmentOutput,
    SEOStrategy,
    UserPersona,
)
from src.tools import linear, llm, miro


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

        # Create Linear issues
        linear_issues = self._create_linear_issues(state, personas, seo_strategy)

        output = ResearchEnrichmentOutput(
            personas=personas,
            primary_persona=personas[0].name if personas else "",
            competitor_matrix=competitor_matrix,
            competitive_landscape_miro_url=miro_url,
            positioning_statement=positioning,
            seo_strategy=seo_strategy,
            linear_issues=linear_issues,
        )

        self.log_complete()
        return output

    def _generate_personas(self, opp) -> list[UserPersona]:
        """Generate detailed user personas."""
        user_prompt = f"""Create 3-5 detailed user personas for this product:

PRODUCT: {opp.name}
DESCRIPTION: {opp.detailed_description}
TARGET SEGMENT: {opp.target_segment}
TARGET MARKET: {opp.target_market_description}
PROBLEM: {opp.problem_statement}

For each persona, provide JSON array with:
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
        user_prompt = f"""Analyze competitors for this product:

PRODUCT: {opp.name}
COMPETITORS: {', '.join(opp.direct_competitors)}
DIFFERENTIATION: {opp.differentiation_angle}
COMPETITOR WEAKNESSES: {', '.join(opp.competitor_weaknesses)}

For each competitor, provide JSON:
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
        user_prompt = f"""Create an SEO strategy for this product:

PRODUCT: {opp.name}
DESCRIPTION: {opp.one_liner}
TARGET: {opp.target_market_description}
COMPETITORS: {', '.join(opp.direct_competitors)}

Provide JSON:
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
        user_prompt = f"""Write a positioning statement for this product:

PRODUCT: {opp.name}
DESCRIPTION: {opp.detailed_description}
DIFFERENTIATION: {opp.differentiation_angle}
TARGET: {opp.target_market_description}
COMPETITOR GAPS: {', '.join([g for c in competitors for g in c.key_gaps][:5])}

Format: "For [target customer] who [statement of need], [product name] is a [product category] that [key benefit]. Unlike [competitors], we [key differentiator]."
"""

        try:
            return llm.generate(
                RESEARCH_ENRICHMENT_PROMPT, user_prompt, model=llm.MODEL_OPUS
            )
        except Exception as e:
            self.logger.error(f"Failed to generate positioning: {e}")
            return f"{opp.name} helps {opp.target_segment} by {opp.differentiation_angle}"

    def _create_linear_issues(
        self, state: FactoryState, personas: list[UserPersona], seo: SEOStrategy
    ) -> list[str]:
        """Create Linear issues for research enrichment."""
        try:
            project = linear.get_project(state.handoff.linear_project_id)
            team_id = project.get("teams", {}).get("nodes", [{}])[0].get("id", "")

            if not team_id:
                return []

            issues = [
                {
                    "title": "[Research] Personas Complete",
                    "description": f"Created {len(personas)} personas:\n\n"
                    + "\n".join([f"- {p.name}: {p.role}" for p in personas]),
                },
                {
                    "title": "[Research] SEO Strategy Complete",
                    "description": f"Target keywords: {len(seo.primary_keywords)}\n"
                    f"Content opportunities: {len(seo.content_opportunities)}",
                },
            ]

            return linear.create_issues_batch(
                state.handoff.linear_project_id, team_id, issues
            )

        except Exception as e:
            self.logger.error(f"Failed to create Linear issues: {e}")
            return []
