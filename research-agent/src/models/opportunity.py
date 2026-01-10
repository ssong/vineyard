"""Data models for opportunities."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OpportunityCategory(Enum):
    """Categories of micro-SaaS opportunities."""

    UNBUNDLING = "unbundling"
    PRODUCTIZED_SERVICE = "productized_service"
    INTEGRATION = "integration"
    BORING_BUSINESS = "boring_business"
    SCRATCH_OWN_ITCH = "scratch_own_itch"
    DEV_TOOLS = "developer_tools"
    AUTOMATION = "automation"
    AI_WRAPPER = "ai_wrapper"


class TargetSegment(Enum):
    """Target customer segments."""

    SMB = "smb"
    MID_MARKET = "mid_market"
    PROSUMER = "prosumer"
    DEVELOPER = "developer"
    CREATOR = "creator"
    AGENCY = "agency"


class BusinessModel(Enum):
    """Pricing/business models."""

    SUBSCRIPTION_MONTHLY = "subscription_monthly"
    SUBSCRIPTION_ANNUAL = "subscription_annual"
    USAGE_BASED = "usage_based"
    ONE_TIME = "one_time"
    CREDITS = "credits"
    FREEMIUM = "freemium"


@dataclass
class Opportunity:
    """Represents a micro-SaaS opportunity identified by the system."""

    # Core identification
    id: str
    name: str
    slug: str
    one_liner: str
    detailed_description: str

    # Classification
    category: OpportunityCategory
    target_segment: TargetSegment
    business_model: BusinessModel

    # Problem definition
    problem_statement: str
    current_solutions: list[str]
    pain_intensity: int  # 1-10
    frequency: str  # "daily", "weekly", "monthly"

    # Market characteristics
    target_market_description: str
    estimated_tam_businesses: int
    geographic_focus: list[str]

    # Competitive landscape
    direct_competitors: list[str]
    competitor_weaknesses: list[str]
    differentiation_angle: str

    # Technical assessment
    build_complexity: str  # "low", "medium", "high"
    estimated_build_weeks: int
    key_technical_components: list[str]
    platform_dependencies: list[str]

    # Pricing
    suggested_price_low: int  # Monthly, in cents
    suggested_price_mid: int
    suggested_price_high: int

    # Scores (0-100)
    four_u_score: int = 0
    solo_viability_score: int = 0
    acquirability_score: int = 0
    overall_score: int = 0

    # Metadata
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "one_liner": self.one_liner,
            "detailed_description": self.detailed_description,
            "category": self.category.value,
            "target_segment": self.target_segment.value,
            "business_model": self.business_model.value,
            "problem_statement": self.problem_statement,
            "current_solutions": self.current_solutions,
            "pain_intensity": self.pain_intensity,
            "frequency": self.frequency,
            "target_market_description": self.target_market_description,
            "estimated_tam_businesses": self.estimated_tam_businesses,
            "geographic_focus": self.geographic_focus,
            "direct_competitors": self.direct_competitors,
            "competitor_weaknesses": self.competitor_weaknesses,
            "differentiation_angle": self.differentiation_angle,
            "build_complexity": self.build_complexity,
            "estimated_build_weeks": self.estimated_build_weeks,
            "key_technical_components": self.key_technical_components,
            "platform_dependencies": self.platform_dependencies,
            "suggested_price_low": self.suggested_price_low,
            "suggested_price_mid": self.suggested_price_mid,
            "suggested_price_high": self.suggested_price_high,
            "four_u_score": self.four_u_score,
            "solo_viability_score": self.solo_viability_score,
            "acquirability_score": self.acquirability_score,
            "overall_score": self.overall_score,
            "discovered_at": self.discovered_at.isoformat(),
            "sources": self.sources,
        }
