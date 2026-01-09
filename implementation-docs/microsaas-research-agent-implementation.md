# Autonomous Micro-SaaS Research Agent System

## Implementation Document for Claude Code

**Version:** 1.0  
**Target:** Solo operator micro-SaaS ideation with acquisition exit strategy  
**Build Time:** 2 months  
**Operator Profile:** UK-based full-stack engineer, 6 years experience, no existing audience

---

## System Overview

An autonomous agent system that, upon receiving "start new project", completes full market research, opportunity identification, validation framework design, and revenue forecasting—producing an actionable report with go/no-go recommendation.

### Core Objectives

1. **Identify market gaps** in underserved niches (not compete head-on)
2. **Validate opportunities** using proven frameworks with quantifiable confidence
3. **Forecast revenue** with conservative/moderate/optimistic projections
4. **Score acquirability** against known buyer criteria
5. **Minimize risk** while maximizing acquisition potential

### Success Criteria

- Agent produces actionable report within 30-60 minutes of trigger
- Recommendations include specific validation experiments
- Revenue forecasts grounded in industry benchmarks
- Opportunities scored for solo-operator viability
- Output suitable for immediate go/no-go decision

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR AGENT                                   │
│                                                                             │
│  • Manages research pipeline execution                                      │
│  • Coordinates specialist agents                                            │
│  • Synthesizes final report                                                 │
│  • Handles error recovery and retries                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│  DISCOVERY AGENT  │   │ VALIDATION AGENT  │   │  SCORING AGENT    │
│                   │   │                   │   │                   │
│ • Market scanning │   │ • 4U Framework    │   │ • Revenue forecast│
│ • Gap analysis    │   │ • Competitor deep │   │ • Acquirability   │
│ • Trend detection │   │   dive            │   │ • Risk assessment │
│ • Idea generation │   │ • Graveyard check │   │ • Solo viability  │
└───────────────────┘   └───────────────────┘   └───────────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │        FINAL REPORT           │
                    │                               │
                    │ • Executive summary           │
                    │ • Top 3 opportunities         │
                    │ • Revenue projections         │
                    │ • Validation experiments      │
                    │ • Go/No-Go recommendation     │
                    └───────────────────────────────┘
```

---

## Project Structure

```
microsaas-research-agent/
├── src/
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── orchestrator.py          # Main pipeline coordinator
│   │   ├── pipeline.py              # Research pipeline stages
│   │   └── report_generator.py      # Final report synthesis
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py                  # Base agent class
│   │   ├── discovery.py             # Market discovery agent
│   │   ├── validation.py            # Opportunity validation agent
│   │   └── scoring.py               # Scoring and forecasting agent
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── web_search.py            # Web search integration
│   │   ├── review_scraper.py        # G2/Capterra review analysis
│   │   ├── reddit_scanner.py        # Reddit community analysis
│   │   ├── keyword_research.py      # Search volume/intent analysis
│   │   ├── competitor_analyzer.py   # Competitor deep dive
│   │   └── pricing_analyzer.py      # Competitive pricing analysis
│   ├── frameworks/
│   │   ├── __init__.py
│   │   ├── four_u.py                # 4U Framework implementation
│   │   ├── jobs_to_be_done.py       # JTBD extraction
│   │   ├── graveyard_detector.py    # Failed market detection
│   │   ├── tam_calculator.py        # Market size estimation
│   │   └── acquirability.py         # Acquisition criteria scoring
│   ├── models/
│   │   ├── __init__.py
│   │   ├── opportunity.py           # Opportunity data model
│   │   ├── competitor.py            # Competitor data model
│   │   ├── validation_result.py     # Validation output model
│   │   └── report.py                # Final report model
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py              # Configuration management
│   │   ├── prompts.py               # Agent system prompts
│   │   └── benchmarks.py            # Industry benchmarks data
│   └── utils/
│       ├── __init__.py
│       ├── rate_limiter.py          # API rate limiting
│       ├── cache.py                 # Response caching
│       └── logging.py               # Structured logging
├── prompts/
│   ├── discovery_agent.md
│   ├── validation_agent.md
│   ├── scoring_agent.md
│   └── report_synthesis.md
├── data/
│   ├── graveyard_markets.json       # Known failed markets
│   ├── benchmark_data.json          # Conversion/churn benchmarks
│   └── platform_risks.json          # Platform dependency data
├── outputs/
│   └── reports/                     # Generated research reports
├── tests/
│   ├── test_discovery.py
│   ├── test_validation.py
│   ├── test_scoring.py
│   └── test_integration.py
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
└── main.py                          # Entry point
```

---

## Data Models

### Opportunity Model

```python
# src/models/opportunity.py
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from datetime import datetime

class OpportunityCategory(Enum):
    UNBUNDLING = "unbundling"
    PRODUCTIZED_SERVICE = "productized_service"
    INTEGRATION = "integration"
    BORING_BUSINESS = "boring_business"
    SCRATCH_OWN_ITCH = "scratch_own_itch"
    DEV_TOOLS = "developer_tools"
    AUTOMATION = "automation"
    AI_WRAPPER = "ai_wrapper"

class TargetSegment(Enum):
    SMB = "smb"              # <$10M revenue
    MID_MARKET = "mid_market" # $10M-$500M revenue
    PROSUMER = "prosumer"
    DEVELOPER = "developer"
    CREATOR = "creator"
    AGENCY = "agency"

class BusinessModel(Enum):
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
    current_solutions: list[str]  # How target solves today
    pain_intensity: int  # 1-10 scale
    frequency: str  # "daily", "weekly", "monthly", "quarterly", "yearly"
    
    # Market characteristics
    target_market_description: str
    estimated_tam_businesses: int  # Number of potential businesses
    estimated_tam_users: int       # Number of potential users
    geographic_focus: list[str]    # ["global", "us", "uk", "eu"]
    
    # Competitive landscape
    direct_competitors: list[str]
    indirect_competitors: list[str]
    competitor_weaknesses: list[str]
    differentiation_angle: str
    
    # Technical assessment
    build_complexity: str  # "low", "medium", "high"
    estimated_build_weeks: int
    key_technical_components: list[str]
    platform_dependencies: list[str]
    api_dependencies: list[str]
    
    # Pricing
    suggested_price_low: int   # Monthly, in cents
    suggested_price_mid: int
    suggested_price_high: int
    pricing_rationale: str
    
    # Scores (0-100)
    four_u_score: int
    market_gap_confidence: int
    solo_viability_score: int
    acquirability_score: int
    overall_score: int
    
    # Metadata
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    sources: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
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
            "estimated_tam_users": self.estimated_tam_users,
            "geographic_focus": self.geographic_focus,
            "direct_competitors": self.direct_competitors,
            "indirect_competitors": self.indirect_competitors,
            "competitor_weaknesses": self.competitor_weaknesses,
            "differentiation_angle": self.differentiation_angle,
            "build_complexity": self.build_complexity,
            "estimated_build_weeks": self.estimated_build_weeks,
            "key_technical_components": self.key_technical_components,
            "platform_dependencies": self.platform_dependencies,
            "api_dependencies": self.api_dependencies,
            "suggested_price_low": self.suggested_price_low,
            "suggested_price_mid": self.suggested_price_mid,
            "suggested_price_high": self.suggested_price_high,
            "pricing_rationale": self.pricing_rationale,
            "four_u_score": self.four_u_score,
            "market_gap_confidence": self.market_gap_confidence,
            "solo_viability_score": self.solo_viability_score,
            "acquirability_score": self.acquirability_score,
            "overall_score": self.overall_score,
            "discovered_at": self.discovered_at.isoformat(),
            "sources": self.sources,
        }
```

### Validation Result Model

```python
# src/models/validation_result.py
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class ValidationConfidence(Enum):
    HIGH = "high"           # Strong go signal
    MEDIUM = "medium"       # Proceed with caution
    LOW = "low"             # Significant concerns
    REJECT = "reject"       # Do not proceed

@dataclass
class FourUResult:
    """4U Framework evaluation result."""
    unworkable_score: int      # 0-25
    unworkable_evidence: str
    unavoidable_score: int     # 0-25
    unavoidable_evidence: str
    urgent_score: int          # 0-25
    urgent_evidence: str
    underserved_score: int     # 0-25
    underserved_evidence: str
    total_score: int           # 0-100
    
    @property
    def passes_threshold(self) -> bool:
        """Requires 75+ to pass (3 of 4 dimensions strong)."""
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
    historical_incidents: list[str]

@dataclass
class CompetitorAnalysis:
    """Deep competitor analysis."""
    competitor_name: str
    website: str
    estimated_mrr: Optional[int]
    pricing_tiers: list[dict]
    strengths: list[str]
    weaknesses: list[str]
    review_sentiment: str  # "positive", "mixed", "negative"
    key_complaints: list[str]
    feature_gaps: list[str]

@dataclass
class ValidationResult:
    """Complete validation result for an opportunity."""
    opportunity_id: str
    
    # Framework results
    four_u_result: FourUResult
    graveyard_check: GraveyardCheck
    platform_risk: PlatformRiskAssessment
    competitor_analyses: list[CompetitorAnalysis]
    
    # Community validation
    reddit_mentions: int
    reddit_sentiment: str
    twitter_mentions: int
    twitter_sentiment: str
    community_pain_signals: list[str]
    
    # Search validation
    primary_keywords: list[str]
    total_monthly_searches: int
    buying_intent_searches: int
    keyword_difficulty: str  # "low", "medium", "high"
    
    # Overall assessment
    confidence: ValidationConfidence
    proceed_recommendation: bool
    key_risks: list[str]
    key_opportunities: list[str]
    validation_experiments: list[dict]  # Recommended next steps
    
    def to_dict(self) -> dict:
        return {
            "opportunity_id": self.opportunity_id,
            "four_u_result": {
                "unworkable": {"score": self.four_u_result.unworkable_score, "evidence": self.four_u_result.unworkable_evidence},
                "unavoidable": {"score": self.four_u_result.unavoidable_score, "evidence": self.four_u_result.unavoidable_evidence},
                "urgent": {"score": self.four_u_result.urgent_score, "evidence": self.four_u_result.urgent_evidence},
                "underserved": {"score": self.four_u_result.underserved_score, "evidence": self.four_u_result.underserved_evidence},
                "total_score": self.four_u_result.total_score,
                "passes_threshold": self.four_u_result.passes_threshold,
            },
            "graveyard_check": {
                "is_graveyard": self.graveyard_check.is_graveyard,
                "signals": self.graveyard_check.graveyard_signals,
                "failed_competitors": self.graveyard_check.failed_competitors,
                "market_viability": self.graveyard_check.market_viability,
            },
            "platform_risk": {
                "dependencies": self.platform_risk.platform_dependencies,
                "risk_level": self.platform_risk.risk_level,
                "specific_risks": self.platform_risk.specific_risks,
            },
            "competitors": [
                {
                    "name": c.competitor_name,
                    "website": c.website,
                    "estimated_mrr": c.estimated_mrr,
                    "strengths": c.strengths,
                    "weaknesses": c.weaknesses,
                    "key_complaints": c.key_complaints,
                }
                for c in self.competitor_analyses
            ],
            "community_validation": {
                "reddit_mentions": self.reddit_mentions,
                "reddit_sentiment": self.reddit_sentiment,
                "pain_signals": self.community_pain_signals,
            },
            "search_validation": {
                "keywords": self.primary_keywords,
                "monthly_searches": self.total_monthly_searches,
                "buying_intent_searches": self.buying_intent_searches,
                "difficulty": self.keyword_difficulty,
            },
            "assessment": {
                "confidence": self.confidence.value,
                "proceed": self.proceed_recommendation,
                "key_risks": self.key_risks,
                "key_opportunities": self.key_opportunities,
            },
            "validation_experiments": self.validation_experiments,
        }
```

### Revenue Forecast Model

```python
# src/models/forecast.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class ConversionBenchmarks:
    """Industry-specific conversion benchmarks."""
    industry: str
    visitor_to_trial: float      # Percentage
    trial_to_paid: float         # Percentage
    monthly_churn: float         # Percentage
    annual_churn: float          # Percentage
    source: str                  # Data source reference

@dataclass
class RevenueProjection:
    """Monthly revenue projection."""
    month: int
    traffic: int
    signups: int
    trials: int
    conversions: int
    churned: int
    active_customers: int
    mrr: int  # In cents
    cumulative_revenue: int

@dataclass
class RevenueForecast:
    """Complete 24-month revenue forecast."""
    opportunity_id: str
    
    # Assumptions
    assumed_traffic_month_1: int
    assumed_traffic_growth_rate: float  # Monthly percentage
    assumed_arpu: int  # In cents
    
    # Benchmarks used
    benchmarks: ConversionBenchmarks
    
    # Projections by scenario
    conservative_projections: list[RevenueProjection]
    moderate_projections: list[RevenueProjection]
    optimistic_projections: list[RevenueProjection]
    
    # Summary metrics
    conservative_mrr_month_12: int
    conservative_mrr_month_24: int
    moderate_mrr_month_12: int
    moderate_mrr_month_24: int
    optimistic_mrr_month_12: int
    optimistic_mrr_month_24: int
    
    # Break-even analysis
    estimated_build_cost: int        # In cents
    estimated_monthly_opex: int      # In cents
    conservative_break_even_month: Optional[int]
    moderate_break_even_month: Optional[int]
    
    # Exit valuation estimates (at 24 months)
    conservative_exit_value: int     # 3x profit multiple
    moderate_exit_value: int         # 4x profit multiple
    optimistic_exit_value: int       # 5x profit multiple
    
    def to_dict(self) -> dict:
        return {
            "opportunity_id": self.opportunity_id,
            "assumptions": {
                "initial_traffic": self.assumed_traffic_month_1,
                "traffic_growth_rate": self.assumed_traffic_growth_rate,
                "arpu": self.assumed_arpu,
            },
            "benchmarks": {
                "industry": self.benchmarks.industry,
                "visitor_to_trial": self.benchmarks.visitor_to_trial,
                "trial_to_paid": self.benchmarks.trial_to_paid,
                "monthly_churn": self.benchmarks.monthly_churn,
            },
            "mrr_projections": {
                "month_12": {
                    "conservative": self.conservative_mrr_month_12,
                    "moderate": self.moderate_mrr_month_12,
                    "optimistic": self.optimistic_mrr_month_12,
                },
                "month_24": {
                    "conservative": self.conservative_mrr_month_24,
                    "moderate": self.moderate_mrr_month_24,
                    "optimistic": self.optimistic_mrr_month_24,
                },
            },
            "break_even": {
                "build_cost": self.estimated_build_cost,
                "monthly_opex": self.estimated_monthly_opex,
                "conservative_month": self.conservative_break_even_month,
                "moderate_month": self.moderate_break_even_month,
            },
            "exit_valuations": {
                "conservative_24m": self.conservative_exit_value,
                "moderate_24m": self.moderate_exit_value,
                "optimistic_24m": self.optimistic_exit_value,
            },
        }
```

### Final Report Model

```python
# src/models/report.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from .opportunity import Opportunity
from .validation_result import ValidationResult
from .forecast import RevenueForecast

class Recommendation(Enum):
    STRONG_GO = "strong_go"           # High confidence, proceed immediately
    GO = "go"                         # Good opportunity, proceed with validation
    CONDITIONAL_GO = "conditional_go" # Proceed if specific conditions met
    NEEDS_MORE_RESEARCH = "needs_more_research"
    NO_GO = "no_go"                   # Do not pursue

@dataclass
class AcquirabilityAssessment:
    """Assessment of acquisition potential."""
    overall_score: int  # 0-100
    
    # Individual factors
    profit_margin_potential: int      # 0-100
    churn_risk_score: int             # 0-100 (higher = lower risk)
    customer_concentration_risk: int  # 0-100 (higher = lower risk)
    platform_dependency_risk: int     # 0-100 (higher = lower risk)
    solo_operator_score: int          # 0-100
    documentation_ease: int           # 0-100
    
    # Multiple estimates
    estimated_multiple_low: float     # e.g., 2.5x
    estimated_multiple_mid: float     # e.g., 3.5x
    estimated_multiple_high: float    # e.g., 5.0x
    
    # Buyer profile fit
    suitable_buyer_types: list[str]   # ["individual", "micro_pe", "strategic"]
    estimated_sale_timeline_months: int
    
    factors_increasing_multiple: list[str]
    factors_decreasing_multiple: list[str]

@dataclass
class SoloViabilityAssessment:
    """Assessment of solo operator viability."""
    overall_score: int  # 0-100
    
    support_burden_estimate: str      # "low", "medium", "high"
    estimated_weekly_support_hours: int
    automation_potential: str         # "high", "medium", "low"
    
    technical_complexity: str
    ongoing_maintenance_needs: str
    
    scaling_without_hiring: bool
    key_automation_opportunities: list[str]
    potential_bottlenecks: list[str]

@dataclass
class OpportunityReport:
    """Complete analysis report for a single opportunity."""
    opportunity: Opportunity
    validation: ValidationResult
    forecast: RevenueForecast
    acquirability: AcquirabilityAssessment
    solo_viability: SoloViabilityAssessment
    
    recommendation: Recommendation
    recommendation_rationale: str
    
    next_steps: list[dict]  # Ordered validation experiments
    risks_to_monitor: list[str]
    success_criteria: list[str]

@dataclass
class ResearchReport:
    """Final comprehensive research report."""
    
    # Metadata
    report_id: str
    generated_at: datetime
    research_duration_minutes: int
    
    # Executive summary
    executive_summary: str
    market_conditions_summary: str
    
    # Opportunities (ranked by overall score)
    opportunities: list[OpportunityReport]
    
    # Top recommendation
    top_recommendation: Optional[OpportunityReport]
    top_recommendation_rationale: str
    
    # Overall market insights
    trending_categories: list[str]
    saturated_categories: list[str]
    emerging_opportunities: list[str]
    
    # Methodology notes
    data_sources_used: list[str]
    limitations: list[str]
    confidence_notes: str
    
    def to_markdown(self) -> str:
        """Generate markdown report."""
        # Implementation in report_generator.py
        pass
    
    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "research_duration_minutes": self.research_duration_minutes,
            "executive_summary": self.executive_summary,
            "opportunities": [
                {
                    "opportunity": opp.opportunity.to_dict(),
                    "validation": opp.validation.to_dict(),
                    "forecast": opp.forecast.to_dict(),
                    "recommendation": opp.recommendation.value,
                    "recommendation_rationale": opp.recommendation_rationale,
                }
                for opp in self.opportunities
            ],
            "top_recommendation": self.top_recommendation.opportunity.name if self.top_recommendation else None,
            "market_insights": {
                "trending": self.trending_categories,
                "saturated": self.saturated_categories,
                "emerging": self.emerging_opportunities,
            },
        }
```

---

## Agent System Prompts

### Discovery Agent

```markdown
# prompts/discovery_agent.md

You are the Discovery Agent for a micro-SaaS research system. Your job is to identify promising opportunities in underserved markets.

## Your Capabilities
- Scan markets for gaps and underserved segments
- Identify trending technologies and emerging needs
- Apply ideation frameworks systematically
- Generate differentiated product concepts

## Ideation Frameworks to Apply

For each research cycle, systematically explore:

1. **Unbundling**: What features of large platforms could be standalone products?
   - Search: "[platform] alternatives for [specific use case]"
   - Look for: Complex tools where users need only 20% of features

2. **Productized Services**: What freelancer/agency work could be standardized?
   - Search job boards for repetitive manual work
   - Look for: Services priced $500-5000 that could be $50-200/month software

3. **Integration Gaps**: What two tools need better connection?
   - Check Zapier most-requested integrations
   - Look for: Workarounds involving copy-paste or CSV exports

4. **Boring Business Software**: What unglamorous industries lack modern tools?
   - Search: "[industry] software complaints" on Reddit
   - Target: Industries still using spreadsheets or legacy software

5. **Developer Tools**: What repetitive coding tasks need automation?
   - Monitor GitHub trending, Dev.to, Hacker News
   - Look for: Scripts people share that could be products

## Search Strategy

For each framework, conduct searches:
- "[category] software complaints site:reddit.com"
- "[category] alternatives site:g2.com"
- "best [category] tools 2024" (to find competitors)
- "[category] pricing too expensive"
- "I wish [category] software would..."

## Output Format

For each promising opportunity, provide:

```json
{
  "name": "string",
  "one_liner": "string - max 100 chars",
  "category": "unbundling | productized_service | integration | boring_business | dev_tools | automation",
  "problem_statement": "string - clear problem being solved",
  "target_audience": "string - specific buyer persona",
  "current_solutions": ["how target solves today"],
  "why_underserved": "string - evidence of gap",
  "differentiation_angle": "string - unique positioning",
  "initial_evidence": [
    {
      "source": "url",
      "signal": "what this tells us"
    }
  ],
  "estimated_pain_level": 1-10,
  "confidence": "high | medium | low"
}
```

## Quality Standards

- Only surface opportunities with clear differentiation
- Require at least 3 independent sources showing demand
- Reject ideas where free alternatives dominate
- Prefer B2B over B2C (higher WTP, lower churn)
- Prioritize problems that occur frequently (daily/weekly)

## What NOT to Recommend

- Note-taking apps (saturated)
- To-do lists (free alternatives)
- Social media schedulers (API risks)
- Generic CRMs (competing with free HubSpot)
- Habit trackers (B2C, low WTP)
- AI wrappers without defensibility
- Anything requiring large teams to support
```

### Validation Agent

```markdown
# prompts/validation_agent.md

You are the Validation Agent for a micro-SaaS research system. Your job is to rigorously evaluate opportunities using proven frameworks.

## Your Capabilities
- Apply 4U Framework to assess problem severity
- Detect graveyard markets and failure patterns
- Analyze competitor landscapes deeply
- Assess platform dependency risks
- Evaluate community demand signals

## 4U Framework Evaluation

Score each dimension 0-25 points:

### Unworkable (0-25)
The existing process literally breaks or fails.
- 25: Business cannot function without solving this
- 20: Significant revenue/efficiency loss from current state
- 15: Noticeable friction but workarounds exist
- 10: Mild inconvenience
- 0: Works fine, just not optimal

Evidence to seek: Support tickets, error rates, workaround complexity

### Unavoidable (0-25)
External forces mandate a solution.
- 25: Legal/compliance requirement
- 20: Industry standard that affects competitiveness
- 15: Strong customer/stakeholder pressure
- 10: Best practice but optional
- 0: Purely optional improvement

Evidence to seek: Regulations, industry standards, competitive pressure

### Urgent (0-25)
Time-sensitive nature of the problem.
- 25: Must solve today/this week
- 20: Active priority this month
- 15: On the roadmap for this quarter
- 10: Would be nice sometime
- 0: No timeline pressure

Evidence to seek: Hiring urgency, budget allocation, active searches

### Underserved (0-25)
Lack of satisfactory existing solutions.
- 25: No valid solutions exist
- 20: Existing solutions deeply flawed
- 15: Solutions exist but poor UX or pricing
- 10: Decent solutions but room for better
- 0: Well-served market

Evidence to seek: Negative reviews, feature request threads, DIY solutions

**Threshold: Total score must be 75+ to proceed with confidence**

## Graveyard Detection

Check for these failure signals:
- Multiple funded startups failed in this space (search Crunchbase)
- Pivots away from this problem by established players
- Abandoned open-source projects
- Recurring "why did X fail" discussions

## Platform Risk Assessment

For each platform dependency:

| Risk Level | Criteria |
|------------|----------|
| Critical | Single platform, has killed apps before, no alternative APIs |
| High | Primary dependency, platform expanding into space |
| Medium | One of multiple dependencies, stable API history |
| Low | Commodity APIs, multiple providers, no lock-in |

## Competitor Analysis Deep Dive

For each competitor, extract:
- Pricing tiers and positioning
- G2/Capterra reviews (overall score + recent trend)
- Most common complaints (from 1-3 star reviews)
- Feature gaps mentioned repeatedly
- Customer segments they serve vs. ignore

## Output Format

```json
{
  "opportunity_id": "string",
  "four_u_result": {
    "unworkable": {"score": 0-25, "evidence": "string"},
    "unavoidable": {"score": 0-25, "evidence": "string"},
    "urgent": {"score": 0-25, "evidence": "string"},
    "underserved": {"score": 0-25, "evidence": "string"},
    "total": 0-100,
    "passes": true/false
  },
  "graveyard_check": {
    "is_graveyard": true/false,
    "signals": ["list of warning signs"],
    "failed_attempts": ["known failures"],
    "viability": "viable | risky | avoid"
  },
  "platform_risk": {
    "dependencies": ["platforms"],
    "risk_level": "low | medium | high | critical",
    "specific_risks": ["risks"],
    "mitigations": ["possible mitigations"]
  },
  "competitors": [
    {
      "name": "string",
      "pricing": "string",
      "strengths": ["list"],
      "weaknesses": ["list"],
      "key_complaints": ["from reviews"]
    }
  ],
  "community_signals": {
    "demand_evidence": ["sources showing demand"],
    "pain_quotes": ["actual user quotes about pain"]
  },
  "overall_confidence": "high | medium | low | reject",
  "proceed_recommendation": true/false,
  "key_risks": ["top risks to monitor"],
  "validation_experiments": [
    {
      "experiment": "what to test",
      "success_criteria": "how to measure",
      "effort": "hours needed",
      "priority": 1-3
    }
  ]
}
```
```

### Scoring Agent

```markdown
# prompts/scoring_agent.md

You are the Scoring Agent for a micro-SaaS research system. Your job is to quantify opportunity potential with revenue forecasts and acquirability assessments.

## Your Capabilities
- Estimate market size (TAM/SAM/SOM)
- Project revenue using industry benchmarks
- Assess acquisition potential
- Evaluate solo operator viability

## Revenue Forecasting Methodology

### Step 1: Market Sizing

Bottom-up calculation:
- Identify specific customer segments
- Estimate number of potential customers per segment
- Apply realistic penetration rates:
  - Year 1: 0.1-0.5% of addressable market
  - Year 2: 0.5-2% of addressable market

### Step 2: Apply Conversion Benchmarks

Use segment-specific rates:

| Segment | Trial Signup | Trial→Paid | Monthly Churn |
|---------|--------------|------------|---------------|
| SMB SaaS | 5-8% | 15-25% | 3-7% |
| Mid-Market | 3-5% | 25-35% | 1-2% |
| Developer Tools | 8-12% | 10-18% | 2-4% |
| Prosumer | 10-15% | 5-10% | 5-8% |

### Step 3: Three Scenarios

**Conservative:**
- Lower traffic assumptions
- Below-median conversion rates
- Higher churn estimates
- Lower ARPU (entry tier)

**Moderate:**
- Median traffic assumptions
- Median conversion rates
- Median churn
- Mid-tier ARPU

**Optimistic:**
- Strong traffic assumptions
- Above-median conversions
- Lower churn
- Higher ARPU

### Step 4: Calculate Projections

For each month 1-24:
```
new_trials = traffic × signup_rate
new_customers = new_trials × conversion_rate
churned = active_customers × monthly_churn
active_customers = previous + new_customers - churned
mrr = active_customers × arpu
```

## Acquirability Assessment

Score these factors (0-100 each):

### Profit Margin Potential (0-100)
- 90+: >80% gross margins possible
- 70-89: 60-80% margins
- 50-69: 40-60% margins
- <50: Below 40% margins

### Churn Risk (0-100, higher = lower risk)
- 90+: <3% annual churn expected
- 70-89: 3-6% annual churn
- 50-69: 6-10% annual churn
- <50: >10% annual churn

### Customer Concentration Risk (0-100, higher = lower risk)
- 90+: Long-tail, no customer >2% of revenue
- 70-89: Some concentration but manageable
- 50-69: Top 10 customers = 30%+ revenue
- <50: Dangerous concentration

### Solo Operator Viability (0-100)
- 90+: Fully self-serve, minimal support
- 70-89: Low-touch, automated onboarding
- 50-69: Some support needed, manageable
- <50: High-touch required

### Calculate Multiple Estimate

Base multiple: 3.5x annual profit

Adjustments:
- NRR >110%: +1.0x
- Annual churn <5%: +0.5x
- Growth >50% YoY: +1.0x
- Platform risk: -0.5 to -1.5x
- Customer concentration >10%: -0.5x
- Solo operator with docs: +0.3x

## Solo Viability Assessment

Evaluate:
- Expected support tickets per 100 customers/month
- Complexity of onboarding (self-serve possible?)
- Technical maintenance requirements
- Content/data update needs
- Regulatory/compliance overhead

Output support burden estimate:
- Low: <5 hours/week at 100 customers
- Medium: 5-15 hours/week at 100 customers
- High: >15 hours/week at 100 customers

## Output Format

```json
{
  "opportunity_id": "string",
  "market_sizing": {
    "tam_businesses": number,
    "sam_businesses": number,
    "som_year1": number,
    "som_year2": number,
    "methodology": "string explaining calculation"
  },
  "revenue_forecast": {
    "assumptions": {
      "traffic_month_1": number,
      "traffic_growth_rate": percentage,
      "arpu_low": cents,
      "arpu_mid": cents,
      "arpu_high": cents
    },
    "projections": {
      "month_12_mrr": {
        "conservative": cents,
        "moderate": cents,
        "optimistic": cents
      },
      "month_24_mrr": {
        "conservative": cents,
        "moderate": cents,
        "optimistic": cents
      }
    },
    "break_even_month": {
      "conservative": number or null,
      "moderate": number or null
    }
  },
  "acquirability": {
    "overall_score": 0-100,
    "profit_margin_potential": 0-100,
    "churn_risk_score": 0-100,
    "concentration_risk_score": 0-100,
    "solo_operator_score": 0-100,
    "estimated_multiple": {
      "low": float,
      "mid": float,
      "high": float
    },
    "exit_value_24m": {
      "conservative": cents,
      "moderate": cents,
      "optimistic": cents
    },
    "suitable_buyers": ["individual", "micro_pe", "strategic"],
    "factors_increasing": ["list"],
    "factors_decreasing": ["list"]
  },
  "solo_viability": {
    "overall_score": 0-100,
    "support_burden": "low | medium | high",
    "weekly_hours_at_100_customers": number,
    "automation_opportunities": ["list"],
    "bottleneck_risks": ["list"]
  }
}
```
```

### Report Synthesis Prompt

```markdown
# prompts/report_synthesis.md

You are synthesizing a comprehensive research report for micro-SaaS opportunity evaluation. Your output will inform a go/no-go decision.

## Report Structure

Generate a markdown report with these sections:

### 1. Executive Summary (200-300 words)
- Number of opportunities evaluated
- Top recommendation with one-line rationale
- Key market insight
- Recommended immediate next step

### 2. Market Conditions Overview
- Current trends favoring micro-SaaS
- Categories to avoid
- Emerging opportunities

### 3. Opportunity Analysis (for each, ranked by score)

#### [Opportunity Name]
**Overall Score: X/100** | **Recommendation: [STRONG GO / GO / CONDITIONAL / NO-GO]**

**One-liner:** [100 char description]

**The Problem:**
[2-3 sentences on the problem and who has it]

**Why Now:**
[Why this opportunity exists today]

**Market Size:**
- TAM: X businesses
- Year 1 Target: X customers
- ARPU: $X/month

**Validation Summary:**
| Factor | Score | Notes |
|--------|-------|-------|
| 4U Total | X/100 | [key insight] |
| Market Gap | X/100 | [key insight] |
| Solo Viability | X/100 | [key insight] |
| Acquirability | X/100 | [key insight] |

**Revenue Forecast:**
| Scenario | Month 12 MRR | Month 24 MRR | Exit Value (24m) |
|----------|--------------|--------------|------------------|
| Conservative | $X | $X | $X |
| Moderate | $X | $X | $X |
| Optimistic | $X | $X | $X |

**Key Risks:**
1. [Risk 1]
2. [Risk 2]
3. [Risk 3]

**Validation Experiments:**
1. [Experiment] - [Success criteria] - [Effort]
2. [Experiment] - [Success criteria] - [Effort]

---

### 4. Top Recommendation Deep Dive

If proceeding with [Opportunity]:

**Week 1-2: Validation Phase**
- [ ] Task 1
- [ ] Task 2

**Week 3-4: MVP Definition**
- [ ] Task 1
- [ ] Task 2

**Success Criteria Before Building:**
- Criterion 1
- Criterion 2

### 5. Appendix

**Data Sources Used:**
- [Source 1]
- [Source 2]

**Methodology Notes:**
- [Any caveats or limitations]

**Benchmarks Reference:**
| Metric | Industry Average | Source |
|--------|------------------|--------|
| Trial→Paid | X% | [Source] |
| Monthly Churn | X% | [Source] |
```

---

## Configuration and Benchmarks

### Benchmark Data

```python
# src/config/benchmarks.py

CONVERSION_BENCHMARKS = {
    "smb_saas": {
        "visitor_to_trial": 0.05,
        "trial_to_paid": 0.20,
        "monthly_churn": 0.05,
        "annual_churn": 0.46,  # Compounded
        "source": "First Page Sage 2025, Pacific Crest Survey"
    },
    "mid_market": {
        "visitor_to_trial": 0.03,
        "trial_to_paid": 0.30,
        "monthly_churn": 0.015,
        "annual_churn": 0.16,
        "source": "SaaS Capital, Bessemer"
    },
    "developer_tools": {
        "visitor_to_trial": 0.10,
        "trial_to_paid": 0.15,
        "monthly_churn": 0.03,
        "annual_churn": 0.31,
        "source": "Stripe Atlas Data"
    },
    "prosumer": {
        "visitor_to_trial": 0.12,
        "trial_to_paid": 0.08,
        "monthly_churn": 0.06,
        "annual_churn": 0.52,
        "source": "Industry aggregates"
    },
}

VALUATION_MULTIPLES = {
    "base_profit_multiple": 3.5,
    "adjustments": {
        "nrr_above_110": 1.0,
        "annual_churn_below_5": 0.5,
        "growth_above_50": 1.0,
        "platform_risk_medium": -0.5,
        "platform_risk_high": -1.0,
        "platform_risk_critical": -1.5,
        "customer_concentration_above_10": -0.5,
        "solo_with_docs": 0.3,
    },
    "source": "Acquire.com 2024, Flippa 2025"
}

SUPPORT_BURDEN_THRESHOLDS = {
    "low": {
        "tickets_per_100_customers": 5,
        "hours_per_week": 5,
    },
    "medium": {
        "tickets_per_100_customers": 15,
        "hours_per_week": 15,
    },
    "high": {
        "tickets_per_100_customers": 30,
        "hours_per_week": 30,
    },
}

GRAVEYARD_MARKETS = [
    {
        "category": "note_taking",
        "reason": "Saturated, free alternatives dominate",
        "examples": ["Notion free tier", "Obsidian", "Apple Notes"]
    },
    {
        "category": "todo_lists",
        "reason": "Commoditized, switching cost near zero",
        "examples": ["Todoist free", "Apple Reminders", "Google Tasks"]
    },
    {
        "category": "social_media_scheduling",
        "reason": "API dependency risks, platform hostility",
        "examples": ["Twitter API pricing killed many", "Buffer, Hootsuite race to bottom"]
    },
    {
        "category": "generic_crm",
        "reason": "HubSpot free tier captures market",
        "examples": ["HubSpot CRM", "Zoho free"]
    },
    {
        "category": "habit_trackers",
        "reason": "B2C, low WTP, high churn",
        "examples": ["Free apps dominate"]
    },
    {
        "category": "ai_wrappers",
        "reason": "No defensibility, margins compress",
        "examples": ["ChatGPT wrapper sites"]
    },
]

PLATFORM_RISK_HISTORY = [
    {
        "platform": "twitter",
        "incident": "API pricing to $42K/month (2023)",
        "impact": "Killed multiple social media tools overnight",
        "risk_level": "critical"
    },
    {
        "platform": "shopify",
        "incident": "Native checkout features",
        "impact": "CartHook forced to pivot",
        "risk_level": "high"
    },
    {
        "platform": "facebook",
        "incident": "Algorithm changes (2012+)",
        "impact": "Zynga growth stalled",
        "risk_level": "high"
    },
    {
        "platform": "instagram",
        "incident": "API restrictions",
        "impact": "Multiple SaaS products killed",
        "risk_level": "high"
    },
]
```

---

## Tool Implementations

### Web Search Tool

```python
# src/tools/web_search.py
import os
from typing import Optional
import httpx
from dataclasses import dataclass

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    
@dataclass
class SearchResponse:
    query: str
    results: list[SearchResult]

class WebSearchTool:
    """Web search using Tavily API (or alternative)."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY")
        self.base_url = "https://api.tavily.com"
    
    async def search(
        self,
        query: str,
        max_results: int = 10,
        search_depth: str = "advanced",
        include_domains: Optional[list[str]] = None,
        exclude_domains: Optional[list[str]] = None,
    ) -> SearchResponse:
        """Execute web search."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/search",
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": search_depth,
                    "include_domains": include_domains or [],
                    "exclude_domains": exclude_domains or [],
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
        
        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", ""),
            )
            for r in data.get("results", [])
        ]
        
        return SearchResponse(query=query, results=results)
    
    async def search_reddit(self, query: str, subreddits: Optional[list[str]] = None) -> SearchResponse:
        """Search Reddit specifically."""
        reddit_query = f"{query} site:reddit.com"
        if subreddits:
            subreddit_filter = " OR ".join([f"site:reddit.com/r/{s}" for s in subreddits])
            reddit_query = f"{query} ({subreddit_filter})"
        
        return await self.search(
            query=reddit_query,
            max_results=20,
            include_domains=["reddit.com"],
        )
    
    async def search_reviews(self, product_category: str) -> SearchResponse:
        """Search G2 and Capterra for reviews."""
        query = f"{product_category} software reviews complaints"
        return await self.search(
            query=query,
            max_results=15,
            include_domains=["g2.com", "capterra.com", "trustradius.com"],
        )
```

### Competitor Analyzer Tool

```python
# src/tools/competitor_analyzer.py
import re
from dataclasses import dataclass
from typing import Optional
from .web_search import WebSearchTool

@dataclass
class CompetitorProfile:
    name: str
    website: str
    description: str
    pricing_info: str
    estimated_customers: Optional[int]
    review_score: Optional[float]
    key_features: list[str]
    common_complaints: list[str]
    target_segment: str

class CompetitorAnalyzer:
    """Analyze competitors in a market segment."""
    
    def __init__(self, search_tool: WebSearchTool):
        self.search = search_tool
    
    async def find_competitors(
        self,
        category: str,
        problem_statement: str,
    ) -> list[str]:
        """Find competitors in category."""
        queries = [
            f"best {category} software 2024",
            f"{category} tools alternatives",
            f"top {category} solutions for small business",
        ]
        
        competitors = set()
        for query in queries:
            results = await self.search.search(query, max_results=10)
            for r in results.results:
                # Extract company names from titles
                competitors.add(r.title.split(" - ")[0].split(" | ")[0].strip())
        
        return list(competitors)[:10]
    
    async def analyze_competitor(
        self,
        competitor_name: str,
        category: str,
    ) -> CompetitorProfile:
        """Deep analysis of single competitor."""
        
        # Search for pricing
        pricing_results = await self.search.search(
            f"{competitor_name} pricing plans",
            max_results=3,
        )
        
        # Search for reviews
        review_results = await self.search.search(
            f"{competitor_name} reviews site:g2.com OR site:capterra.com",
            max_results=5,
        )
        
        # Search for complaints
        complaint_results = await self.search.search(
            f"{competitor_name} complaints problems issues site:reddit.com",
            max_results=5,
        )
        
        # Extract insights (simplified - actual implementation would parse more deeply)
        return CompetitorProfile(
            name=competitor_name,
            website=self._extract_website(competitor_name),
            description=self._extract_description(pricing_results),
            pricing_info=self._extract_pricing(pricing_results),
            estimated_customers=None,
            review_score=self._extract_review_score(review_results),
            key_features=self._extract_features(pricing_results),
            common_complaints=self._extract_complaints(complaint_results),
            target_segment=self._infer_segment(pricing_results),
        )
    
    def _extract_website(self, name: str) -> str:
        # Simplified - would need actual lookup
        return f"https://{name.lower().replace(' ', '')}.com"
    
    def _extract_description(self, results) -> str:
        if results.results:
            return results.results[0].snippet[:200]
        return ""
    
    def _extract_pricing(self, results) -> str:
        for r in results.results:
            if "pricing" in r.title.lower() or "$" in r.snippet:
                return r.snippet[:300]
        return "Pricing not found"
    
    def _extract_review_score(self, results) -> Optional[float]:
        for r in results.results:
            # Look for patterns like "4.5/5" or "4.5 out of 5"
            match = re.search(r'(\d\.\d)\s*(?:/|out of)\s*5', r.snippet)
            if match:
                return float(match.group(1))
        return None
    
    def _extract_features(self, results) -> list[str]:
        features = []
        for r in results.results:
            # Simple extraction - look for bullet-point-like patterns
            if "•" in r.snippet or "-" in r.snippet:
                parts = re.split(r'[•\-]', r.snippet)
                features.extend([p.strip()[:50] for p in parts if len(p.strip()) > 5])
        return features[:5]
    
    def _extract_complaints(self, results) -> list[str]:
        complaints = []
        for r in results.results:
            if any(word in r.snippet.lower() for word in ["problem", "issue", "hate", "terrible", "worst", "frustrat"]):
                complaints.append(r.snippet[:150])
        return complaints[:5]
    
    def _infer_segment(self, results) -> str:
        all_text = " ".join([r.snippet for r in results.results]).lower()
        if "enterprise" in all_text:
            return "enterprise"
        elif "small business" in all_text or "smb" in all_text:
            return "smb"
        elif "startup" in all_text:
            return "startup"
        elif "freelancer" in all_text or "individual" in all_text:
            return "prosumer"
        return "unknown"
```

---

## Orchestrator Implementation

```python
# src/orchestrator/orchestrator.py
import uuid
import asyncio
from datetime import datetime
from typing import Optional
import anthropic

from ..agents.discovery import DiscoveryAgent
from ..agents.validation import ValidationAgent
from ..agents.scoring import ScoringAgent
from ..models.opportunity import Opportunity
from ..models.validation_result import ValidationResult
from ..models.forecast import RevenueForecast
from ..models.report import ResearchReport, OpportunityReport, Recommendation
from .report_generator import ReportGenerator

class ResearchOrchestrator:
    """Orchestrates the complete research pipeline."""
    
    def __init__(
        self,
        anthropic_api_key: str,
        tavily_api_key: str,
        model: str = "claude-sonnet-4-20250514",
    ):
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)
        self.model = model
        
        # Initialize agents
        self.discovery_agent = DiscoveryAgent(
            client=self.client,
            model=model,
            tavily_api_key=tavily_api_key,
        )
        self.validation_agent = ValidationAgent(
            client=self.client,
            model=model,
            tavily_api_key=tavily_api_key,
        )
        self.scoring_agent = ScoringAgent(
            client=self.client,
            model=model,
        )
        
        self.report_generator = ReportGenerator()
    
    async def run_research(
        self,
        focus_areas: Optional[list[str]] = None,
        exclude_categories: Optional[list[str]] = None,
        max_opportunities: int = 5,
    ) -> ResearchReport:
        """Execute complete research pipeline."""
        
        start_time = datetime.utcnow()
        report_id = str(uuid.uuid4())[:8]
        
        print(f"[{report_id}] Starting research pipeline...")
        
        # Phase 1: Discovery
        print(f"[{report_id}] Phase 1: Discovery")
        opportunities = await self.discovery_agent.discover_opportunities(
            focus_areas=focus_areas,
            exclude_categories=exclude_categories,
            max_opportunities=max_opportunities * 2,  # Discover more, filter later
        )
        print(f"[{report_id}] Discovered {len(opportunities)} initial opportunities")
        
        # Phase 2: Validation (parallel)
        print(f"[{report_id}] Phase 2: Validation")
        validation_tasks = [
            self.validation_agent.validate_opportunity(opp)
            for opp in opportunities
        ]
        validation_results = await asyncio.gather(*validation_tasks)
        
        # Filter to passing opportunities
        passing_opportunities = [
            (opp, val) for opp, val in zip(opportunities, validation_results)
            if val.proceed_recommendation
        ]
        print(f"[{report_id}] {len(passing_opportunities)} opportunities passed validation")
        
        # Phase 3: Scoring (parallel)
        print(f"[{report_id}] Phase 3: Scoring")
        scoring_tasks = [
            self.scoring_agent.score_opportunity(opp, val)
            for opp, val in passing_opportunities
        ]
        scored_results = await asyncio.gather(*scoring_tasks)
        
        # Build opportunity reports
        opportunity_reports = []
        for (opp, val), (forecast, acquirability, solo_viability) in zip(
            passing_opportunities, scored_results
        ):
            # Update opportunity scores
            opp.overall_score = self._calculate_overall_score(
                val, forecast, acquirability, solo_viability
            )
            
            recommendation = self._determine_recommendation(
                val, forecast, acquirability, solo_viability
            )
            
            opportunity_reports.append(OpportunityReport(
                opportunity=opp,
                validation=val,
                forecast=forecast,
                acquirability=acquirability,
                solo_viability=solo_viability,
                recommendation=recommendation,
                recommendation_rationale=self._generate_rationale(
                    opp, val, recommendation
                ),
                next_steps=val.validation_experiments[:3],
                risks_to_monitor=val.key_risks[:3],
                success_criteria=self._generate_success_criteria(opp, val),
            ))
        
        # Sort by overall score
        opportunity_reports.sort(key=lambda x: x.opportunity.overall_score, reverse=True)
        
        # Limit to max_opportunities
        opportunity_reports = opportunity_reports[:max_opportunities]
        
        # Generate final report
        end_time = datetime.utcnow()
        duration_minutes = int((end_time - start_time).total_seconds() / 60)
        
        top_recommendation = opportunity_reports[0] if opportunity_reports else None
        
        report = ResearchReport(
            report_id=report_id,
            generated_at=end_time,
            research_duration_minutes=duration_minutes,
            executive_summary=self._generate_executive_summary(opportunity_reports),
            market_conditions_summary=self._generate_market_summary(),
            opportunities=opportunity_reports,
            top_recommendation=top_recommendation,
            top_recommendation_rationale=self._generate_top_rationale(top_recommendation),
            trending_categories=self._extract_trending_categories(opportunities),
            saturated_categories=self._extract_saturated_categories(validation_results),
            emerging_opportunities=self._extract_emerging(opportunities),
            data_sources_used=self._collect_data_sources(),
            limitations=self._note_limitations(),
            confidence_notes=self._generate_confidence_notes(opportunity_reports),
        )
        
        print(f"[{report_id}] Research complete in {duration_minutes} minutes")
        
        return report
    
    def _calculate_overall_score(
        self,
        validation: ValidationResult,
        forecast: RevenueForecast,
        acquirability,
        solo_viability,
    ) -> int:
        """Calculate weighted overall score."""
        weights = {
            "four_u": 0.25,
            "market_gap": 0.20,
            "solo_viability": 0.20,
            "acquirability": 0.20,
            "revenue_potential": 0.15,
        }
        
        # Normalize revenue potential to 0-100
        # Moderate month 24 MRR > $10K = 100, linear scale below
        revenue_score = min(100, (forecast.moderate_mrr_month_24 / 100) / 100)
        
        score = (
            validation.four_u_result.total_score * weights["four_u"] +
            validation.market_gap_confidence * weights["market_gap"] +
            solo_viability.overall_score * weights["solo_viability"] +
            acquirability.overall_score * weights["acquirability"] +
            revenue_score * weights["revenue_potential"]
        )
        
        return int(score)
    
    def _determine_recommendation(
        self,
        validation: ValidationResult,
        forecast: RevenueForecast,
        acquirability,
        solo_viability,
    ) -> Recommendation:
        """Determine recommendation based on scores."""
        overall = self._calculate_overall_score(
            validation, forecast, acquirability, solo_viability
        )
        
        if overall >= 80 and validation.four_u_result.passes_threshold:
            return Recommendation.STRONG_GO
        elif overall >= 65 and not validation.graveyard_check.is_graveyard:
            return Recommendation.GO
        elif overall >= 50:
            return Recommendation.CONDITIONAL_GO
        elif overall >= 35:
            return Recommendation.NEEDS_MORE_RESEARCH
        else:
            return Recommendation.NO_GO
    
    def _generate_rationale(
        self,
        opportunity: Opportunity,
        validation: ValidationResult,
        recommendation: Recommendation,
    ) -> str:
        """Generate human-readable recommendation rationale."""
        if recommendation == Recommendation.STRONG_GO:
            return (
                f"Strong opportunity: 4U score of {validation.four_u_result.total_score}/100 "
                f"indicates genuine market need. {opportunity.differentiation_angle} provides "
                f"clear positioning. Low platform risk and high solo viability."
            )
        elif recommendation == Recommendation.GO:
            return (
                f"Good opportunity with manageable risks. "
                f"Validation experiments should confirm demand before building."
            )
        elif recommendation == Recommendation.CONDITIONAL_GO:
            return (
                f"Proceed only if: {', '.join(validation.key_risks[:2])} are addressed. "
                f"Consider reduced scope MVP."
            )
        else:
            return (
                f"Concerns: {', '.join(validation.key_risks[:2])}. "
                f"Market may not support sustainable business."
            )
    
    def _generate_success_criteria(
        self,
        opportunity: Opportunity,
        validation: ValidationResult,
    ) -> list[str]:
        """Generate success criteria before building."""
        return [
            f"10+ interviews confirming {opportunity.problem_statement}",
            "Landing page with 3%+ conversion to waitlist (pricing visible)",
            "3+ pre-orders or design partner commitments",
            f"Confirmed willingness to pay ${opportunity.suggested_price_mid // 100}/month",
        ]
    
    def _generate_executive_summary(
        self,
        opportunity_reports: list[OpportunityReport],
    ) -> str:
        """Generate executive summary."""
        if not opportunity_reports:
            return "No viable opportunities identified in this research cycle."
        
        top = opportunity_reports[0]
        strong_go_count = sum(
            1 for o in opportunity_reports
            if o.recommendation in [Recommendation.STRONG_GO, Recommendation.GO]
        )
        
        return (
            f"Evaluated {len(opportunity_reports)} opportunities. "
            f"{strong_go_count} show strong potential. "
            f"Top recommendation: **{top.opportunity.name}** - "
            f"{top.opportunity.one_liner}. "
            f"Projected moderate-case MRR at 24 months: "
            f"${top.forecast.moderate_mrr_month_24 // 100:,}. "
            f"Recommended next step: {top.next_steps[0]['experiment'] if top.next_steps else 'Begin validation'}."
        )
    
    def _generate_market_summary(self) -> str:
        return (
            "Current market favors AI-enhanced productivity tools, "
            "developer infrastructure, and boring B2B automation. "
            "Avoid: generic AI wrappers, social media tools (API risk), "
            "consumer habit apps. Look for: unbundling opportunities from "
            "bloated platforms, automation of manual agency work."
        )
    
    def _generate_top_rationale(
        self,
        top: Optional[OpportunityReport],
    ) -> str:
        if not top:
            return "No opportunities met minimum criteria."
        
        return (
            f"{top.opportunity.name} ranks highest due to: "
            f"strong 4U score ({top.validation.four_u_result.total_score}/100), "
            f"viable solo operation (score: {top.solo_viability.overall_score}/100), "
            f"and attractive acquisition profile (est. {top.acquirability.estimated_multiple_mid}x multiple). "
            f"Key differentiator: {top.opportunity.differentiation_angle}."
        )
    
    def _extract_trending_categories(self, opportunities: list[Opportunity]) -> list[str]:
        # Simplified - would analyze across all discovered opportunities
        return ["AI-enhanced workflows", "Developer tooling", "Automation APIs"]
    
    def _extract_saturated_categories(self, validations: list[ValidationResult]) -> list[str]:
        saturated = []
        for v in validations:
            if v.graveyard_check.is_graveyard:
                saturated.extend(v.graveyard_check.graveyard_signals)
        return list(set(saturated))[:5]
    
    def _extract_emerging(self, opportunities: list[Opportunity]) -> list[str]:
        return ["Vertical AI agents", "Compliance automation", "API aggregation"]
    
    def _collect_data_sources(self) -> list[str]:
        return [
            "G2 Crowd reviews",
            "Capterra reviews", 
            "Reddit (r/SaaS, r/Entrepreneur, r/startups)",
            "Indie Hackers",
            "Product Hunt",
            "Acquire.com listings",
            "SEMrush keyword data",
            "Industry benchmark reports",
        ]
    
    def _note_limitations(self) -> list[str]:
        return [
            "Revenue forecasts based on industry averages - actual results vary",
            "Competitor data from public sources only",
            "Market size estimates are approximations",
            "Validation scores are directional, not precise predictions",
        ]
    
    def _generate_confidence_notes(
        self,
        opportunity_reports: list[OpportunityReport],
    ) -> str:
        high_conf = sum(
            1 for o in opportunity_reports
            if o.validation.confidence.value == "high"
        )
        return (
            f"{high_conf}/{len(opportunity_reports)} opportunities have high-confidence validation. "
            f"All recommendations should be verified with direct customer interviews."
        )
```

---

## Entry Point

```python
# main.py
import asyncio
import os
import argparse
from datetime import datetime
from pathlib import Path

from src.orchestrator.orchestrator import ResearchOrchestrator
from src.orchestrator.report_generator import ReportGenerator

async def main():
    parser = argparse.ArgumentParser(
        description="Autonomous Micro-SaaS Research Agent"
    )
    parser.add_argument(
        "--focus",
        nargs="*",
        help="Focus areas (e.g., 'developer tools' 'automation')",
    )
    parser.add_argument(
        "--exclude",
        nargs="*", 
        help="Categories to exclude (e.g., 'social media' 'consumer')",
    )
    parser.add_argument(
        "--max-opportunities",
        type=int,
        default=5,
        help="Maximum opportunities to return (default: 5)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs/reports",
        help="Output directory for reports",
    )
    
    args = parser.parse_args()
    
    # Initialize orchestrator
    orchestrator = ResearchOrchestrator(
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        tavily_api_key=os.environ["TAVILY_API_KEY"],
    )
    
    print("=" * 60)
    print("AUTONOMOUS MICRO-SAAS RESEARCH AGENT")
    print("=" * 60)
    print(f"Focus areas: {args.focus or 'All categories'}")
    print(f"Excluding: {args.exclude or 'None'}")
    print(f"Max opportunities: {args.max_opportunities}")
    print("=" * 60)
    print()
    
    # Run research
    report = await orchestrator.run_research(
        focus_areas=args.focus,
        exclude_categories=args.exclude,
        max_opportunities=args.max_opportunities,
    )
    
    # Save report
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    # Save markdown
    md_path = output_dir / f"research_report_{timestamp}.md"
    generator = ReportGenerator()
    md_content = generator.to_markdown(report)
    md_path.write_text(md_content)
    print(f"Markdown report saved: {md_path}")
    
    # Save JSON
    json_path = output_dir / f"research_report_{timestamp}.json"
    import json
    json_path.write_text(json.dumps(report.to_dict(), indent=2))
    print(f"JSON report saved: {json_path}")
    
    # Print summary
    print()
    print("=" * 60)
    print("RESEARCH COMPLETE")
    print("=" * 60)
    print(report.executive_summary)
    print()
    
    if report.top_recommendation:
        top = report.top_recommendation
        print("TOP RECOMMENDATION:")
        print(f"  {top.opportunity.name}")
        print(f"  {top.opportunity.one_liner}")
        print(f"  Overall Score: {top.opportunity.overall_score}/100")
        print(f"  Recommendation: {top.recommendation.value.upper()}")
        print()
        print("NEXT STEPS:")
        for i, step in enumerate(top.next_steps[:3], 1):
            print(f"  {i}. {step['experiment']}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Docker Configuration

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p outputs/reports data

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "main.py"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  research-agent:
    build: .
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - TAVILY_API_KEY=${TAVILY_API_KEY}
    volumes:
      - ./outputs:/app/outputs
      - ./data:/app/data
    command: ["--max-opportunities", "5"]
```

```text
# requirements.txt
anthropic>=0.40.0
httpx>=0.27.0
pydantic>=2.0.0
python-dotenv>=1.0.0
```

---

## Environment Variables

```bash
# .env.example
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
```

---

## Usage

```bash
# Basic usage - research all categories
python main.py

# Focus on specific areas
python main.py --focus "developer tools" "automation"

# Exclude categories
python main.py --exclude "social media" "consumer apps"

# Limit results
python main.py --max-opportunities 3

# Full example
python main.py \
  --focus "boring b2b" "developer tools" \
  --exclude "ai wrapper" "social media" \
  --max-opportunities 5
```

---

## Expected Output

The system produces:

1. **Markdown Report** - Human-readable research report with:
   - Executive summary
   - Top 3-5 opportunities ranked by score
   - Revenue projections for each
   - Validation experiments to run
   - Go/no-go recommendations

2. **JSON Report** - Machine-readable data for further processing

3. **Console Summary** - Quick view of top recommendation and next steps

---

## Success Metrics

The agent system succeeds when:

- [ ] Produces actionable report in <60 minutes
- [ ] Top recommendation has 4U score ≥75
- [ ] Revenue forecasts include conservative/moderate/optimistic scenarios
- [ ] Validation experiments are specific and prioritized
- [ ] No graveyard markets in top recommendations
- [ ] All opportunities scored for solo operator viability
- [ ] Acquirability assessment includes multiple estimate

---

## Future Enhancements

1. **Slack Integration** - Push reports to Slack channel
2. **Scheduled Runs** - Weekly automated research cycles
3. **Trend Tracking** - Monitor opportunities over time
4. **Interview Scheduler** - Automate validation interview booking
5. **Landing Page Generator** - Create test landing pages from opportunities
6. **Competitor Monitoring** - Track competitor changes post-research
