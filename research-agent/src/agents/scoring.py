"""Scoring Agent - Revenue forecasting and acquirability assessment."""

from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import SCORING_AGENT_PROMPT
from src.models import (
    Opportunity,
    OpportunityReport,
    Recommendation,
    RevenueForecast,
    ValidationResult,
)
from src.tools import llm


class ScoringAgent(BaseAgent):
    """Agent for scoring opportunities and forecasting revenue."""

    name = "ScoringAgent"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Score opportunities and generate revenue forecasts.

        Args:
            context: Must contain 'opportunities' and 'validation_results'

        Returns:
            Context with scored opportunity reports
        """
        self.log_start(context)

        opportunities = context.get("opportunities", [])
        validations = context.get("validation_results", [])

        # Create lookup for validations
        validation_map = {v.opportunity_id: v for v in validations}

        opportunity_reports = []
        for opp in opportunities:
            validation = validation_map.get(opp.id)
            if validation:
                report = self._score_opportunity(opp, validation)
                opportunity_reports.append(report)

        # Sort by overall score
        opportunity_reports.sort(
            key=lambda x: x.opportunity.overall_score, reverse=True
        )

        result = {**context, "opportunity_reports": opportunity_reports}
        self.log_complete(result)

        return result

    def _score_opportunity(
        self, opp: Opportunity, validation: ValidationResult
    ) -> OpportunityReport:
        """Score a single opportunity and generate forecast."""
        user_prompt = f"""Score this micro-SaaS opportunity:

OPPORTUNITY: {opp.name}
ONE-LINER: {opp.one_liner}
TARGET SEGMENT: {opp.target_segment.value}
BUSINESS MODEL: {opp.business_model.value}
BUILD COMPLEXITY: {opp.build_complexity}
BUILD TIME: {opp.estimated_build_weeks} weeks
PRICING: ${opp.suggested_price_low/100:.0f} - ${opp.suggested_price_high/100:.0f}/month
4U SCORE: {validation.four_u_result.total_score}/100
PLATFORM RISK: {validation.platform_risk.risk_level}
TAM: {opp.estimated_tam_businesses} businesses

Provide a JSON response with:
{{
    "revenue_forecast": {{
        "assumed_arpu": {opp.suggested_price_mid},
        "mrr_month_12_conservative": number (in cents),
        "mrr_month_12_moderate": number (in cents),
        "mrr_month_12_optimistic": number (in cents),
        "mrr_month_24_conservative": number (in cents),
        "mrr_month_24_moderate": number (in cents),
        "mrr_month_24_optimistic": number (in cents),
        "estimated_build_cost": number (in cents),
        "break_even_month_moderate": number or null,
        "exit_value_moderate": number (in cents)
    }},
    "scores": {{
        "solo_viability_score": 0-100,
        "acquirability_score": 0-100,
        "overall_score": 0-100
    }},
    "recommendation": "strong_go" | "go" | "conditional_go" | "needs_more_research" | "no_go",
    "recommendation_rationale": "string",
    "next_steps": ["string"],
    "risks_to_monitor": ["string"]
}}"""

        try:
            result = llm.generate_json(SCORING_AGENT_PROMPT, user_prompt)

            forecast_data = result.get("revenue_forecast", {})
            scores = result.get("scores", {})

            # Update opportunity scores
            opp.four_u_score = validation.four_u_result.total_score
            opp.solo_viability_score = scores.get("solo_viability_score", 70)
            opp.acquirability_score = scores.get("acquirability_score", 70)
            opp.overall_score = scores.get("overall_score", 70)

            forecast = RevenueForecast(
                opportunity_id=opp.id,
                assumed_arpu=forecast_data.get("assumed_arpu", opp.suggested_price_mid),
                mrr_month_12_conservative=forecast_data.get("mrr_month_12_conservative", 240000),
                mrr_month_12_moderate=forecast_data.get("mrr_month_12_moderate", 480000),
                mrr_month_12_optimistic=forecast_data.get("mrr_month_12_optimistic", 850000),
                mrr_month_24_conservative=forecast_data.get("mrr_month_24_conservative", 600000),
                mrr_month_24_moderate=forecast_data.get("mrr_month_24_moderate", 1200000),
                mrr_month_24_optimistic=forecast_data.get("mrr_month_24_optimistic", 2000000),
                estimated_build_cost=forecast_data.get("estimated_build_cost", 500000),
                break_even_month_moderate=forecast_data.get("break_even_month_moderate", 6),
                exit_value_moderate=forecast_data.get("exit_value_moderate", 5000000),
            )

            return OpportunityReport(
                opportunity=opp,
                validation=validation,
                forecast=forecast,
                recommendation=Recommendation(result.get("recommendation", "go")),
                recommendation_rationale=result.get("recommendation_rationale", ""),
                next_steps=result.get("next_steps", []),
                risks_to_monitor=result.get("risks_to_monitor", []),
            )

        except Exception as e:
            self.logger.error(f"Scoring failed for {opp.name}: {e}")
            # Return default report
            opp.overall_score = 50

            return OpportunityReport(
                opportunity=opp,
                validation=validation,
                forecast=RevenueForecast(
                    opportunity_id=opp.id,
                    assumed_arpu=opp.suggested_price_mid,
                    mrr_month_12_conservative=200000,
                    mrr_month_12_moderate=400000,
                    mrr_month_12_optimistic=700000,
                    mrr_month_24_conservative=500000,
                    mrr_month_24_moderate=1000000,
                    mrr_month_24_optimistic=1500000,
                    estimated_build_cost=500000,
                    break_even_month_moderate=8,
                    exit_value_moderate=4000000,
                ),
                recommendation=Recommendation.NEEDS_MORE_RESEARCH,
                recommendation_rationale="Scoring could not be completed",
                next_steps=["Manual review required"],
                risks_to_monitor=["Scoring failed"],
            )
