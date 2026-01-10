"""Data models for validation results."""

from dataclasses import dataclass
from enum import Enum


class ValidationConfidence(Enum):
    """Confidence level in validation results."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    REJECT = "reject"


@dataclass
class FourUResult:
    """4U Framework evaluation result."""

    unworkable_score: int  # 0-25
    unworkable_evidence: str
    unavoidable_score: int  # 0-25
    unavoidable_evidence: str
    urgent_score: int  # 0-25
    urgent_evidence: str
    underserved_score: int  # 0-25
    underserved_evidence: str

    @property
    def total_score(self) -> int:
        """Calculate total 4U score (0-100)."""
        return (
            self.unworkable_score
            + self.unavoidable_score
            + self.urgent_score
            + self.underserved_score
        )

    @property
    def passes_threshold(self) -> bool:
        """Requires 75+ to pass."""
        return self.total_score >= 75


@dataclass
class GraveyardCheck:
    """Check if market is a known graveyard."""

    is_graveyard: bool
    graveyard_signals: list[str]
    failed_competitors: list[str]
    failure_reasons: list[str]
    market_viability: str  # "viable", "risky", "avoid"


@dataclass
class PlatformRiskAssessment:
    """Evaluate platform dependency risks."""

    platform_dependencies: list[str]
    risk_level: str  # "low", "medium", "high", "critical"
    specific_risks: list[str]
    mitigation_strategies: list[str]


@dataclass
class ValidationResult:
    """Complete validation result for an opportunity."""

    opportunity_id: str

    # Framework results
    four_u_result: FourUResult
    graveyard_check: GraveyardCheck
    platform_risk: PlatformRiskAssessment

    # Community signals
    community_pain_signals: list[str]

    # Overall assessment
    confidence: ValidationConfidence
    proceed_recommendation: bool
    key_risks: list[str]
    key_opportunities: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "opportunity_id": self.opportunity_id,
            "four_u_result": {
                "unworkable": self.four_u_result.unworkable_score,
                "unavoidable": self.four_u_result.unavoidable_score,
                "urgent": self.four_u_result.urgent_score,
                "underserved": self.four_u_result.underserved_score,
                "total_score": self.four_u_result.total_score,
                "passes_threshold": self.four_u_result.passes_threshold,
            },
            "graveyard_check": {
                "is_graveyard": self.graveyard_check.is_graveyard,
                "market_viability": self.graveyard_check.market_viability,
            },
            "platform_risk": {
                "risk_level": self.platform_risk.risk_level,
                "dependencies": self.platform_risk.platform_dependencies,
            },
            "confidence": self.confidence.value,
            "proceed": self.proceed_recommendation,
            "key_risks": self.key_risks,
            "key_opportunities": self.key_opportunities,
        }
