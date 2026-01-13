"""Discovery Agent - Market scanning and opportunity identification.

This agent discovers micro-SaaS opportunities through:
1. Diverse web search queries (randomized per run)
2. Framework-enforced opportunity generation
3. Deduplication against past suggestions
"""

import random
import uuid
from typing import Any, Optional

from src.agents.base import BaseAgent
from src.config.diversity import (
    DiversityConfig,
    generate_diverse_queries,
    get_llm_parameters,
    sample_industries,
    INDUSTRIES,
)
from src.config.prompts import DISCOVERY_AGENT_PROMPT
from src.models import (
    BusinessModel,
    Opportunity,
    OpportunityCategory,
    TargetSegment,
)
from src.tools import llm, web_search
from src.tools.history import get_history


# Framework definitions for enforced diversity
FRAMEWORKS = [
    {
        "id": "unbundling",
        "name": "Unbundling",
        "description": "Extract focused features from complex platforms",
        "category": OpportunityCategory.UNBUNDLING,
    },
    {
        "id": "productized_service",
        "name": "Productized Service",
        "description": "Turn expensive services into affordable software",
        "category": OpportunityCategory.PRODUCTIZED_SERVICE,
    },
    {
        "id": "integration",
        "name": "Integration Gap",
        "description": "Connect tools that don't work well together",
        "category": OpportunityCategory.INTEGRATION,
    },
    {
        "id": "boring_business",
        "name": "Boring Business Software",
        "description": "Modern tools for unglamorous industries",
        "category": OpportunityCategory.BORING_BUSINESS,
    },
    {
        "id": "developer_tools",
        "name": "Developer Tools",
        "description": "Productivity tools for programmers",
        "category": OpportunityCategory.DEVELOPER_TOOLS,
    },
    {
        "id": "automation",
        "name": "Automation & Workflows",
        "description": "Automate manual multi-step processes",
        "category": OpportunityCategory.AUTOMATION,
    },
]


class DiscoveryAgent(BaseAgent):
    """Agent for discovering micro-SaaS opportunities with diversity."""

    name = "DiscoveryAgent"

    def __init__(self, config: Optional[DiversityConfig] = None):
        """
        Initialize the discovery agent.

        Args:
            config: Diversity configuration. If None, uses defaults.
        """
        super().__init__()
        self.config = config or DiversityConfig()
        self.history = get_history()

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Discover opportunities through market scanning.

        Args:
            context: May contain:
                - diversity_config: DiversityConfig override
                - focus_frameworks: List of framework IDs to focus on
                - focus_industries: List of industries to focus on

        Returns:
            Context with list of raw opportunities
        """
        self.log_start(context)

        # Apply context overrides
        if "diversity_config" in context:
            self.config = context["diversity_config"]
        if "focus_frameworks" in context:
            self.config.focus_frameworks = context["focus_frameworks"]
        if "focus_industries" in context:
            self.config.focus_industries = context["focus_industries"]

        # Get history context for deduplication
        recent_slugs = self.history.get_recent_slugs(days=90)
        recent_problems = self.history.get_recent_problems(days=90)
        underexplored = self.history.get_underexplored_categories(days=90)

        self.logger.info(f"Found {len(recent_slugs)} recent opportunities to avoid")
        self.logger.info(f"Underexplored categories: {underexplored}")

        # Update config with history context
        self.config.exclude_slugs = recent_slugs
        self.config.exclude_problems = recent_problems[:20]  # Limit for prompt size

        # Bias toward underexplored categories
        if not self.config.focus_frameworks and underexplored:
            # 50% chance to focus on underexplored frameworks
            if random.random() < 0.5:
                self.config.focus_frameworks = underexplored[:3]
                self.logger.info(f"Focusing on underexplored: {self.config.focus_frameworks}")

        # Get market signals via web search
        queries = generate_diverse_queries(self.config)
        self.logger.info(f"Generated queries: {queries}")

        search_results = self._gather_market_signals(queries)

        # Sample industries for this run
        industries = sample_industries(self.config)
        self.logger.info(f"Sampled industries: {industries}")

        # Generate opportunities using framework-enforced approach
        opportunities = self._generate_opportunities_diverse(
            search_results,
            industries,
        )

        # Record to history
        run_id = str(uuid.uuid4())
        for opp in opportunities:
            self.history.record(opp)

        self.history.record_run(
            run_id=run_id,
            opportunity_ids=[o.id for o in opportunities],
            queries=queries,
            industries=industries,
            frameworks=[f["id"] for f in self._get_active_frameworks()],
        )

        result = {
            "opportunities": opportunities,
            "search_results": search_results,
            "run_metadata": {
                "run_id": run_id,
                "queries_used": queries,
                "industries_sampled": industries,
                "frameworks_used": [f["id"] for f in self._get_active_frameworks()],
            },
        }
        self.log_complete(result)

        return result

    def _get_active_frameworks(self) -> list[dict]:
        """Get frameworks to use based on configuration."""
        if self.config.focus_frameworks:
            return [f for f in FRAMEWORKS if f["id"] in self.config.focus_frameworks]
        return FRAMEWORKS

    def _gather_market_signals(self, queries: list[str]) -> list[dict]:
        """Gather market signals from diverse web searches."""
        all_results = []

        for query in queries:
            try:
                results = web_search.search(query, max_results=3)
                all_results.extend(results)
            except Exception as e:
                self.logger.warning(f"Search failed for '{query}': {e}")

        self.logger.info(f"Gathered {len(all_results)} search results")
        return all_results

    def _generate_opportunities_diverse(
        self,
        search_results: list[dict],
        industries: list[str],
    ) -> list[Opportunity]:
        """
        Generate opportunities with enforced framework diversity.

        This ensures each opportunity comes from a different framework
        and avoids duplicating past suggestions.
        """
        active_frameworks = self._get_active_frameworks()

        # Shuffle frameworks for variety
        random.shuffle(active_frameworks)

        # Format search results for LLM
        search_context = "\n\n".join(
            [f"Source: {r['url']}\n{r['content'][:500]}" for r in search_results[:15]]
        )

        # Build exclusion context
        exclusion_context = ""
        if self.config.exclude_slugs:
            exclusion_context += f"\n\nPREVIOUSLY SUGGESTED (DO NOT REPEAT):\n"
            exclusion_context += "Slugs to avoid: " + ", ".join(self.config.exclude_slugs[:30])

        if self.config.exclude_problems:
            exclusion_context += "\n\nProblem areas already covered (find different angles):\n"
            for prob in self.config.exclude_problems[:10]:
                exclusion_context += f"- {prob[:100]}...\n"

        # Build framework assignments
        framework_assignments = "\n".join([
            f"- Opportunity {i+1}: MUST use {fw['name']} framework ({fw['description']})"
            for i, fw in enumerate(active_frameworks[:5])
        ])

        # Build industry suggestions
        industry_suggestions = ", ".join(industries[:10])

        # Get LLM parameters with variation
        llm_params = get_llm_parameters(self.config)

        user_prompt = f"""Based on the following market signals, identify 5 promising micro-SaaS opportunities.

CRITICAL DIVERSITY REQUIREMENTS:
Each opportunity MUST come from a DIFFERENT ideation framework as assigned below:
{framework_assignments}

INDUSTRY FOCUS FOR THIS RUN:
Consider opportunities in these industries: {industry_suggestions}
(But don't force it - only if there's genuine opportunity)
{exclusion_context}

MARKET SIGNALS:
{search_context}

For each opportunity, provide a JSON array with objects containing:
- name: Product name (creative, memorable)
- slug: URL-friendly slug
- one_liner: 100 char max description
- detailed_description: 2-3 sentence explanation
- category: one of [unbundling, productized_service, integration, boring_business, developer_tools, automation]
- target_segment: one of [smb, mid_market, prosumer, developer, creator, agency]
- business_model: one of [subscription_monthly, subscription_annual, usage_based, freemium]
- problem_statement: Clear problem being solved (be specific, not generic)
- current_solutions: Array of how target solves today
- pain_intensity: 1-10 score
- frequency: daily, weekly, or monthly
- target_market_description: Who is the buyer (be specific)
- estimated_tam_businesses: Number of potential customers
- geographic_focus: Array like ["global"] or ["us", "uk"]
- direct_competitors: Array of competitor names
- competitor_weaknesses: Array of gaps in competitors
- differentiation_angle: How this differs (be specific, not "better UX")
- build_complexity: low, medium, or high
- estimated_build_weeks: Number
- key_technical_components: Array of main tech needed
- platform_dependencies: Array of platforms relied on
- suggested_price_low: Monthly price in cents (low tier)
- suggested_price_mid: Monthly price in cents (mid tier)
- suggested_price_high: Monthly price in cents (high tier)

QUALITY REQUIREMENTS:
- Each opportunity must solve a DIFFERENT problem
- Be specific about the target customer (not just "small businesses")
- Differentiation must be concrete (not "simpler" or "better")
- Include real competitor names where possible
- Problems should be quantifiable (time/money impact)

Return ONLY a JSON array of 5 opportunities."""

        try:
            result = llm.generate_json(
                DISCOVERY_AGENT_PROMPT,
                user_prompt,
                model=llm.MODEL_OPUS,
                use_extended_thinking=True,
                thinking_budget=llm_params["thinking_budget"],
            )

            opportunities = []
            for opp_data in result[:5]:
                opp = self._parse_opportunity(opp_data, search_results)

                # Skip if duplicate
                if self.history.is_duplicate(opp, days=90):
                    self.logger.warning(f"Skipping duplicate: {opp.slug}")
                    continue

                opportunities.append(opp)

            # If we filtered too many, try to generate more
            if len(opportunities) < 3:
                self.logger.warning(
                    f"Only {len(opportunities)} unique opportunities, "
                    "consider clearing old history or adjusting thresholds"
                )

            return opportunities

        except Exception as e:
            self.logger.error(f"Failed to generate opportunities: {e}")
            return []

    def _parse_opportunity(
        self,
        opp_data: dict,
        search_results: list[dict],
    ) -> Opportunity:
        """Parse opportunity data from LLM response."""
        return Opportunity(
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


# Backwards compatibility - simple run function
def run_discovery(context: Optional[dict] = None) -> dict[str, Any]:
    """Run discovery with default configuration."""
    agent = DiscoveryAgent()
    return agent.run(context or {})
