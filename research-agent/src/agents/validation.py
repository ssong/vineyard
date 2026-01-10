"""Validation Agent - 4U Framework and risk assessment."""

from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import VALIDATION_AGENT_PROMPT
from src.models import (
    FourUResult,
    GraveyardCheck,
    Opportunity,
    PlatformRiskAssessment,
    ValidationConfidence,
    ValidationResult,
)
from src.tools import llm


class ValidationAgent(BaseAgent):
    """Agent for validating opportunities using 4U Framework."""

    name = "ValidationAgent"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Validate opportunities using 4U Framework.

        Args:
            context: Must contain 'opportunities' list

        Returns:
            Context with validation results
        """
        self.log_start(context)

        opportunities = context.get("opportunities", [])
        validation_results = []

        for opp in opportunities:
            result = self._validate_opportunity(opp)
            validation_results.append(result)

        result = {**context, "validation_results": validation_results}
        self.log_complete(result)

        return result

    def _validate_opportunity(self, opp: Opportunity) -> ValidationResult:
        """Validate a single opportunity."""
        user_prompt = f"""Evaluate this micro-SaaS opportunity using the 4U Framework:

OPPORTUNITY: {opp.name}
ONE-LINER: {opp.one_liner}
PROBLEM: {opp.problem_statement}
TARGET: {opp.target_market_description}
COMPETITORS: {', '.join(opp.direct_competitors)}
PLATFORM DEPENDENCIES: {', '.join(opp.platform_dependencies)}

Provide a JSON response with:
{{
    "four_u": {{
        "unworkable_score": 0-25,
        "unworkable_evidence": "string",
        "unavoidable_score": 0-25,
        "unavoidable_evidence": "string",
        "urgent_score": 0-25,
        "urgent_evidence": "string",
        "underserved_score": 0-25,
        "underserved_evidence": "string"
    }},
    "graveyard": {{
        "is_graveyard": boolean,
        "signals": ["string"],
        "failed_competitors": ["string"],
        "failure_reasons": ["string"],
        "market_viability": "viable" | "risky" | "avoid"
    }},
    "platform_risk": {{
        "risk_level": "low" | "medium" | "high" | "critical",
        "specific_risks": ["string"],
        "mitigation_strategies": ["string"]
    }},
    "community_pain_signals": ["string"],
    "confidence": "high" | "medium" | "low" | "reject",
    "proceed_recommendation": boolean,
    "key_risks": ["string"],
    "key_opportunities": ["string"]
}}"""

        try:
            result = llm.generate_json(VALIDATION_AGENT_PROMPT, user_prompt)

            four_u_data = result.get("four_u", {})
            graveyard_data = result.get("graveyard", {})
            platform_data = result.get("platform_risk", {})

            return ValidationResult(
                opportunity_id=opp.id,
                four_u_result=FourUResult(
                    unworkable_score=four_u_data.get("unworkable_score", 15),
                    unworkable_evidence=four_u_data.get("unworkable_evidence", ""),
                    unavoidable_score=four_u_data.get("unavoidable_score", 15),
                    unavoidable_evidence=four_u_data.get("unavoidable_evidence", ""),
                    urgent_score=four_u_data.get("urgent_score", 15),
                    urgent_evidence=four_u_data.get("urgent_evidence", ""),
                    underserved_score=four_u_data.get("underserved_score", 15),
                    underserved_evidence=four_u_data.get("underserved_evidence", ""),
                ),
                graveyard_check=GraveyardCheck(
                    is_graveyard=graveyard_data.get("is_graveyard", False),
                    graveyard_signals=graveyard_data.get("signals", []),
                    failed_competitors=graveyard_data.get("failed_competitors", []),
                    failure_reasons=graveyard_data.get("failure_reasons", []),
                    market_viability=graveyard_data.get("market_viability", "viable"),
                ),
                platform_risk=PlatformRiskAssessment(
                    platform_dependencies=opp.platform_dependencies,
                    risk_level=platform_data.get("risk_level", "medium"),
                    specific_risks=platform_data.get("specific_risks", []),
                    mitigation_strategies=platform_data.get("mitigation_strategies", []),
                ),
                community_pain_signals=result.get("community_pain_signals", []),
                confidence=ValidationConfidence(result.get("confidence", "medium")),
                proceed_recommendation=result.get("proceed_recommendation", True),
                key_risks=result.get("key_risks", []),
                key_opportunities=result.get("key_opportunities", []),
            )

        except Exception as e:
            self.logger.error(f"Validation failed for {opp.name}: {e}")
            # Return default result
            return ValidationResult(
                opportunity_id=opp.id,
                four_u_result=FourUResult(
                    unworkable_score=15,
                    unworkable_evidence="Validation failed",
                    unavoidable_score=15,
                    unavoidable_evidence="",
                    urgent_score=15,
                    urgent_evidence="",
                    underserved_score=15,
                    underserved_evidence="",
                ),
                graveyard_check=GraveyardCheck(
                    is_graveyard=False,
                    graveyard_signals=[],
                    failed_competitors=[],
                    failure_reasons=[],
                    market_viability="risky",
                ),
                platform_risk=PlatformRiskAssessment(
                    platform_dependencies=opp.platform_dependencies,
                    risk_level="medium",
                    specific_risks=["Unable to assess"],
                    mitigation_strategies=[],
                ),
                community_pain_signals=[],
                confidence=ValidationConfidence.LOW,
                proceed_recommendation=False,
                key_risks=["Validation could not be completed"],
                key_opportunities=[],
            )
