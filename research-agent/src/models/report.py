"""Data models for research reports."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from .opportunity import Opportunity
from .validation import ValidationResult


class Recommendation(Enum):
    """Go/No-Go recommendation levels."""

    STRONG_GO = "strong_go"
    GO = "go"
    CONDITIONAL_GO = "conditional_go"
    NEEDS_MORE_RESEARCH = "needs_more_research"
    NO_GO = "no_go"


@dataclass
class RevenueForecast:
    """Revenue projections for an opportunity."""

    opportunity_id: str

    # Assumptions
    assumed_arpu: int  # In cents

    # 12-month projections
    mrr_month_12_conservative: int
    mrr_month_12_moderate: int
    mrr_month_12_optimistic: int

    # 24-month projections
    mrr_month_24_conservative: int
    mrr_month_24_moderate: int
    mrr_month_24_optimistic: int

    # Break-even
    estimated_build_cost: int
    break_even_month_moderate: Optional[int]

    # Exit valuations at 24 months
    exit_value_moderate: int


@dataclass
class OpportunityReport:
    """Complete analysis for a single opportunity."""

    opportunity: Opportunity
    validation: ValidationResult
    forecast: RevenueForecast

    recommendation: Recommendation
    recommendation_rationale: str

    next_steps: list[str]
    risks_to_monitor: list[str]


@dataclass
class ResearchReport:
    """Final comprehensive research report."""

    # Metadata
    report_id: str
    generated_at: datetime = field(default_factory=datetime.utcnow)
    research_duration_seconds: int = 0

    # Executive summary
    executive_summary: str = ""

    # Opportunities (ranked by overall score)
    opportunities: list[OpportunityReport] = field(default_factory=list)

    # Top recommendation
    top_recommendation: Optional[OpportunityReport] = None
    top_recommendation_rationale: str = ""

    # Methodology notes
    data_sources_used: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "research_duration_seconds": self.research_duration_seconds,
            "executive_summary": self.executive_summary,
            "opportunities": [
                {
                    "opportunity": opp.opportunity.to_dict(),
                    "validation": opp.validation.to_dict(),
                    "recommendation": opp.recommendation.value,
                    "mrr_12_moderate": opp.forecast.mrr_month_12_moderate,
                    "mrr_24_moderate": opp.forecast.mrr_month_24_moderate,
                }
                for opp in self.opportunities
            ],
            "top_recommendation": (
                self.top_recommendation.opportunity.name if self.top_recommendation else None
            ),
        }
