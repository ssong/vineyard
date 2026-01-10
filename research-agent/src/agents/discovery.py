"""Discovery Agent - Market scanning and opportunity identification."""

import uuid
from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import DISCOVERY_AGENT_PROMPT
from src.models import (
    BusinessModel,
    Opportunity,
    OpportunityCategory,
    TargetSegment,
)
from src.tools import llm, web_search


class DiscoveryAgent(BaseAgent):
    """Agent for discovering micro-SaaS opportunities."""

    name = "DiscoveryAgent"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Discover opportunities through market scanning.

        Args:
            context: May contain optional focus areas or constraints

        Returns:
            Context with list of raw opportunities
        """
        self.log_start(context)

        # Get market signals via web search
        search_results = self._gather_market_signals()

        # Generate opportunities using LLM
        opportunities = self._generate_opportunities(search_results)

        result = {"opportunities": opportunities, "search_results": search_results}
        self.log_complete(result)

        return result

    def _gather_market_signals(self) -> list[dict]:
        """Gather market signals from web searches."""
        all_results = []

        # Search for underserved markets
        queries = [
            "micro saas ideas 2024 underserved",
            "solo founder saas opportunities",
            "boring business software needs modernization",
            "developer tools pain points site:reddit.com",
            "small business software complaints",
        ]

        for query in queries:
            results = web_search.search(query, max_results=3)
            all_results.extend(results)

        return all_results

    def _generate_opportunities(self, search_results: list[dict]) -> list[Opportunity]:
        """Use LLM to generate opportunities from market signals."""
        # Format search results for LLM
        search_context = "\n\n".join(
            [f"Source: {r['url']}\n{r['content'][:500]}" for r in search_results[:10]]
        )

        user_prompt = f"""Based on the following market signals, identify 5 promising micro-SaaS opportunities.

MARKET SIGNALS:
{search_context}

For each opportunity, provide a JSON array with objects containing:
- name: Product name
- slug: URL-friendly slug
- one_liner: 100 char max description
- detailed_description: 2-3 sentence explanation
- category: one of [unbundling, productized_service, integration, boring_business, developer_tools, automation]
- target_segment: one of [smb, mid_market, prosumer, developer, creator, agency]
- business_model: one of [subscription_monthly, subscription_annual, usage_based, freemium]
- problem_statement: Clear problem being solved
- current_solutions: Array of how target solves today
- pain_intensity: 1-10 score
- frequency: daily, weekly, or monthly
- target_market_description: Who is the buyer
- estimated_tam_businesses: Number of potential customers
- geographic_focus: Array like ["global"] or ["us", "uk"]
- direct_competitors: Array of competitor names
- competitor_weaknesses: Array of gaps in competitors
- differentiation_angle: How this differs
- build_complexity: low, medium, or high
- estimated_build_weeks: Number
- key_technical_components: Array of main tech needed
- platform_dependencies: Array of platforms relied on
- suggested_price_low: Monthly price in cents (low tier)
- suggested_price_mid: Monthly price in cents (mid tier)
- suggested_price_high: Monthly price in cents (high tier)

Return ONLY a JSON array of 5 opportunities."""

        try:
            # Use extended thinking for complex market analysis
            result = llm.generate_json(
                DISCOVERY_AGENT_PROMPT,
                user_prompt,
                model=llm.MODEL_OPUS,
                use_extended_thinking=True,
                thinking_budget=8000,
            )

            opportunities = []
            for opp_data in result[:5]:
                opp = Opportunity(
                    id=str(uuid.uuid4()),
                    name=opp_data.get("name", "Unknown"),
                    slug=opp_data.get("slug", "unknown"),
                    one_liner=opp_data.get("one_liner", ""),
                    detailed_description=opp_data.get("detailed_description", ""),
                    category=OpportunityCategory(
                        opp_data.get("category", "automation")
                    ),
                    target_segment=TargetSegment(
                        opp_data.get("target_segment", "smb")
                    ),
                    business_model=BusinessModel(
                        opp_data.get("business_model", "subscription_monthly")
                    ),
                    problem_statement=opp_data.get("problem_statement", ""),
                    current_solutions=opp_data.get("current_solutions", []),
                    pain_intensity=opp_data.get("pain_intensity", 5),
                    frequency=opp_data.get("frequency", "weekly"),
                    target_market_description=opp_data.get("target_market_description", ""),
                    estimated_tam_businesses=opp_data.get("estimated_tam_businesses", 10000),
                    geographic_focus=opp_data.get("geographic_focus", ["global"]),
                    direct_competitors=opp_data.get("direct_competitors", []),
                    competitor_weaknesses=opp_data.get("competitor_weaknesses", []),
                    differentiation_angle=opp_data.get("differentiation_angle", ""),
                    build_complexity=opp_data.get("build_complexity", "medium"),
                    estimated_build_weeks=opp_data.get("estimated_build_weeks", 4),
                    key_technical_components=opp_data.get("key_technical_components", []),
                    platform_dependencies=opp_data.get("platform_dependencies", []),
                    suggested_price_low=opp_data.get("suggested_price_low", 1900),
                    suggested_price_mid=opp_data.get("suggested_price_mid", 4900),
                    suggested_price_high=opp_data.get("suggested_price_high", 9900),
                    sources=[r["url"] for r in search_results[:5]],
                )
                opportunities.append(opp)

            return opportunities

        except Exception as e:
            self.logger.error(f"Failed to generate opportunities: {e}")
            return []
