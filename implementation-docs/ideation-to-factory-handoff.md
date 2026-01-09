# Ideation to Factory Handoff Specification

## Overview

This document defines the integration between the **Micro-SaaS Research Agent** (ideation) and the **Multi-Agent SaaS Factory** (execution). The handoff occurs when a human operator selects an opportunity from the research report and triggers factory execution.

---

## Trigger Conditions

The factory handoff is triggered when:

1. Research Agent has completed and produced a `ResearchReport`
2. Human operator has reviewed the top opportunities
3. Human selects one `OpportunityReport` to proceed with
4. Research Agent has created the Linear project for tracking

---

## Handoff Data Model

### FactoryHandoff

The handoff payload passed from ideation to factory:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class FactoryHandoff:
    """Handoff payload from Research Agent to SaaS Factory."""
    
    # Trigger metadata
    handoff_id: str                    # Unique ID for this handoff
    triggered_at: datetime
    triggered_by: str                  # Operator ID
    
    # Source reference
    research_report_id: str            # Parent research report
    opportunity_id: str                # Selected opportunity ID
    
    # Linear project (already created by Research Agent)
    linear_project_id: str
    linear_project_url: str
    linear_team_ids: dict[str, str]    # {"product": "id", "engineering": "id", "marketing": "id"}
    
    # Opportunity context (denormalized for factory consumption)
    opportunity: OpportunitySummary
    validation: ValidationSummary
    forecast: ForecastSummary
    
    # Operator preferences
    build_preferences: BuildPreferences
    launch_preferences: LaunchPreferences
    
    # Approval chain
    approval_checkpoints: list[str]    # ["design", "build", "launch"] - where to pause


@dataclass
class OpportunitySummary:
    """Condensed opportunity data for factory agents."""
    
    name: str
    slug: str
    one_liner: str
    detailed_description: str
    
    # Classification
    category: str                      # OpportunityCategory value
    target_segment: str                # TargetSegment value
    business_model: str                # BusinessModel value
    
    # Problem
    problem_statement: str
    current_solutions: list[str]
    pain_intensity: int
    frequency: str
    
    # Market
    target_market_description: str
    geographic_focus: list[str]
    
    # Competitive positioning
    direct_competitors: list[str]
    competitor_weaknesses: list[str]
    differentiation_angle: str
    
    # Technical scope
    build_complexity: str
    estimated_build_weeks: int
    key_technical_components: list[str]
    platform_dependencies: list[str]
    api_dependencies: list[str]
    
    # Pricing
    suggested_price_low: int           # Monthly, in cents
    suggested_price_mid: int
    suggested_price_high: int


@dataclass
class ValidationSummary:
    """Key validation signals for factory context."""
    
    four_u_score: int                  # 0-100
    four_u_breakdown: dict[str, int]   # {"unworkable": 23, "unavoidable": 20, ...}
    
    is_graveyard_market: bool
    graveyard_signals: list[str]
    
    platform_risk_level: str
    platform_risks: list[str]
    
    top_competitor: str
    competitor_key_weakness: str
    
    community_pain_signals: list[str]
    total_monthly_searches: int
    buying_intent_keywords: list[str]
    
    proceed_recommendation: bool
    key_risks: list[str]
    key_opportunities: list[str]


@dataclass
class ForecastSummary:
    """Revenue projections for factory context."""
    
    assumed_arpu: int                  # In cents
    
    # 12-month MRR projections
    mrr_month_12_conservative: int
    mrr_month_12_moderate: int
    mrr_month_12_optimistic: int
    
    # 24-month MRR projections
    mrr_month_24_conservative: int
    mrr_month_24_moderate: int
    mrr_month_24_optimistic: int
    
    # Break-even
    estimated_build_cost: int
    break_even_month_moderate: Optional[int]
    
    # Exit valuations at 24 months
    exit_value_moderate: int


@dataclass
class BuildPreferences:
    """Operator preferences for build phase."""
    
    tech_stack: dict[str, str]         # {"frontend": "nextjs", "backend": "python", ...}
    hosting_preference: str            # "vercel", "fly", "railway"
    database_preference: str           # "neon", "supabase", "planetscale"
    auth_preference: str               # "clerk", "auth0", "supabase"
    payments_preference: str           # "stripe", "lemonsqueezy"
    
    include_analytics: bool
    analytics_preference: str          # "posthog", "plausible"
    
    deploy_staging_first: bool
    require_security_scan: bool


@dataclass
class LaunchPreferences:
    """Operator preferences for launch phase."""
    
    target_launch_date: Optional[datetime]
    
    # Channels
    launch_on_product_hunt: bool
    launch_on_twitter: bool
    launch_on_linkedin: bool
    launch_on_hacker_news: bool
    
    # Email
    setup_email_marketing: bool
    email_provider: str                # "resend", "loops", "mailchimp"
    
    # Domain
    domain_name: Optional[str]
    
    # Pricing strategy
    launch_pricing_tier: str           # "low", "mid", "high" from opportunity
    offer_annual_discount: bool
    annual_discount_percent: int
```

---

## Linear Project Structure (Pre-Created)

The Research Agent creates this structure before handoff:

```
Project: [Opportunity Name]
├── Labels:
│   ├── research (green)
│   ├── design (purple)
│   ├── engineering (blue)
│   ├── marketing (orange)
│   ├── launch (red)
│   ├── needs-review (yellow)
│   └── blocked (gray)
│
├── Issue: [Research] Market Analysis ✅
│   └── Contains: competitive landscape, validation data
│
├── Issue: [Research] Opportunity Selected
│   └── Contains: link to full research report, selection rationale
│
└── (Factory creates remaining issues from this point)
```

---

## Factory Entry Point

### Trigger Command

```python
async def trigger_factory(handoff: FactoryHandoff) -> str:
    """
    Entry point for SaaS Factory.
    Called when operator selects opportunity to build.
    
    Returns: Factory execution ID for tracking
    """
    
    # Validate handoff
    validate_handoff(handoff)
    
    # Initialize factory state
    factory_state = FactoryState(
        execution_id=generate_id(),
        handoff=handoff,
        current_phase="research_enrichment",  # Start with enrichment (discovery done, deep dive needed)
        phase_status={},
        checkpoints_cleared=[],
    )
    
    # Persist state for recovery
    await save_factory_state(factory_state)
    
    # Notify Slack
    await slack.send(
        channel="#factory-runs",
        text=f"🏭 Factory triggered for *{handoff.opportunity.name}*",
        blocks=build_factory_start_blocks(handoff)
    )
    
    # Start factory orchestrator
    await factory_orchestrator.start(factory_state)
    
    return factory_state.execution_id
```

### Factory State

```python
@dataclass
class FactoryState:
    """Persisted state for factory execution."""
    
    execution_id: str
    handoff: FactoryHandoff
    
    current_phase: str                 # "research_enrichment" | "design" | "spec" | "build" | "launch_prep" | "launch" | "growth"
    phase_status: dict[str, str]       # {"research_enrichment": "complete", "design": "in_progress", ...}
    
    checkpoints_cleared: list[str]     # Human-approved phases
    
    # Accumulated outputs
    outputs: dict[str, Any]            # {"design": DesignOutput, "spec": SpecOutput, ...}
    
    # Linear issue IDs created
    linear_issues: dict[str, list[str]]
    
    # Error tracking
    errors: list[dict]
    retries: int
    
    # Timestamps
    started_at: datetime
    last_updated_at: datetime
    completed_at: Optional[datetime]
```

---

## Phase Execution Flow

```
                    ┌──────────────────────────────────────┐
                    │         FACTORY HANDOFF              │
                    │  (OpportunitySummary + Validation    │
                    │   + Forecast + Preferences)          │
                    └──────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 0: RESEARCH ENRICHMENT                                                │
│                                                                             │
│ Purpose: Enrich ideation output with deeper analysis (not repeat discovery) │
│                                                                             │
│ Input:   OpportunitySummary, ValidationSummary                              │
│ Agents:  Research Agent                                                     │
│                                                                             │
│ What's SKIPPED (already done by Ideation):                                  │
│   ✓ Competitor discovery                                                    │
│   ✓ Market size estimation                                                  │
│   ✓ Problem validation (4U Framework)                                       │
│   ✓ Go/No-Go recommendation                                                 │
│                                                                             │
│ What's ENRICHED:                                                            │
│   • Deeper competitor feature matrix (pricing tiers, feature gaps)          │
│   • Full user personas (3-5 detailed personas with JTBD)                    │
│   • SEO/Keyword strategy (target keywords, content opportunities)           │
│   • Miro competitive landscape board                                        │
│                                                                             │
│ Output:  ResearchEnrichmentOutput                                           │
│ Linear:  Creates [Research] Enrichment Complete issue                       │
│                                                                             │
│ → Flows directly to Design (no checkpoint by default)                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: DESIGN                                                             │
│                                                                             │
│ Input:   ResearchEnrichmentOutput, OpportunitySummary                       │
│ Agents:  Design Agent                                                       │
│ Output:  PRD, User Flows (Miro), Feature List                               │
│ Linear:  Creates [Design] PRD, [Design] User Flows issues                   │
│                                                                             │
│ → Human Checkpoint (if "design" in approval_checkpoints)                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: SPEC                                                               │
│                                                                             │
│ Input:   DesignOutput, BuildPreferences                                     │
│ Agents:  Spec Agent                                                         │
│ Output:  Technical Spec, API Contracts, DB Schema, Task Breakdown           │
│ Linear:  Creates [Feature] parent issues + engineering sub-tasks            │
│                                                                             │
│ → Flows directly to build (no checkpoint by default)                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: BUILD                                                              │
│                                                                             │
│ Input:   SpecOutput, BuildPreferences                                       │
│ Agents:  Code Agent, Test Agent, Security Agent, DevOps Agent               │
│ Output:  Working codebase, deployed to staging                              │
│ Linear:  Updates task status, creates PR links                              │
│                                                                             │
│ → Human Checkpoint (if "build" in approval_checkpoints)                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: LAUNCH PREP                                                        │
│                                                                             │
│ Input:   BuildOutput, LaunchPreferences, ForecastSummary                    │
│ Agents:  Marketing Agent, Launch Agent                                      │
│ Output:  Landing page copy, email sequences, social content, PH listing     │
│ Linear:  Creates marketing tasks, launch checklist                          │
│                                                                             │
│ → Human Checkpoint (if "launch" in approval_checkpoints)                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 5: LAUNCH                                                             │
│                                                                             │
│ Input:   LaunchPrepOutput, LaunchPreferences                                │
│ Agents:  Launch Agent                                                       │
│ Output:  Scheduled posts, email broadcasts queued, deploy to production     │
│ Linear:  Updates launch checklist items                                     │
│                                                                             │
│ → Notifies human for manual PH submission                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 6: GROWTH (Ongoing)                                                   │
│                                                                             │
│ Input:   All previous outputs, live metrics                                 │
│ Agents:  Growth Agent, Support Agent                                        │
│ Output:  Weekly reports, experiment hypotheses, support triage              │
│ Linear:  Creates growth experiments, bug reports                            │
│                                                                             │
│ → Runs on schedule until manually stopped                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Context Passing Between Phases

Each phase produces output consumed by subsequent phases:

```python
@dataclass
class UserPersona:
    """Detailed user persona with Jobs-to-be-Done."""
    name: str                          # "Startup Sarah"
    role: str                          # "Indie Hacker / Solo Founder"
    demographics: str                  # Brief demographic context
    goals: list[str]                   # What they're trying to achieve
    frustrations: list[str]            # Current pain points
    jobs_to_be_done: list[str]         # JTBD format statements
    willingness_to_pay: str            # "$X-$Y/month"
    acquisition_channels: list[str]   # Where to reach them


@dataclass
class CompetitorFeatureMatrix:
    """Detailed competitor comparison."""
    competitor_name: str
    pricing_tiers: list[dict]          # [{"name": "Free", "price": 0, "features": [...]}]
    feature_comparison: dict[str, bool] # {"Feature A": True, "Feature B": False}
    key_strengths: list[str]
    key_gaps: list[str]                # Opportunities for differentiation
    review_summary: str                # Aggregated review sentiment


@dataclass
class SEOStrategy:
    """Keyword and content strategy."""
    primary_keywords: list[dict]       # [{"keyword": "...", "volume": 1200, "difficulty": "low"}]
    long_tail_keywords: list[str]
    content_opportunities: list[str]   # Blog post ideas, landing page angles
    competitor_ranking_gaps: list[str] # Keywords competitors rank for that we can target
    estimated_organic_potential: str   # "X-Y visitors/month in 6 months"


@dataclass
class ResearchEnrichmentOutput:
    """Output from Research Enrichment phase."""
    
    # Personas
    personas: list[UserPersona]        # 3-5 detailed personas
    primary_persona: str               # Name of primary target
    
    # Competitor deep dive
    competitor_matrix: list[CompetitorFeatureMatrix]
    competitive_landscape_miro_url: str
    positioning_statement: str         # How we differentiate
    
    # SEO/Content strategy
    seo_strategy: SEOStrategy
    
    # Linear tracking
    linear_issues: list[str]


@dataclass
class DesignOutput:
    prd_markdown: str
    user_flow_miro_url: str
    features: list[FeatureSpec]
    ui_copy: dict[str, str]
    linear_issues: list[str]


@dataclass
class SpecOutput:
    technical_spec_markdown: str
    api_contracts: list[APIContract]
    db_schema: str
    task_breakdown: list[EngineeringTask]
    architecture_miro_url: str
    linear_issues: list[str]


@dataclass
class BuildOutput:
    github_repo_url: str
    staging_url: str
    test_results: TestResults
    security_scan_results: SecurityResults
    deploy_config: dict
    linear_issues: list[str]


@dataclass
class LaunchPrepOutput:
    landing_page_copy: dict
    email_sequences: list[EmailSequence]
    social_content: SocialContent
    product_hunt_listing: PHListing
    launch_checklist_url: str
    linear_issues: list[str]


@dataclass
class LaunchOutput:
    production_url: str
    scheduled_posts: list[str]
    email_broadcast_ids: list[str]
    launch_metrics_dashboard_url: str
```

---

## Slack Notifications

### Handoff Trigger
```
🏭 Factory triggered for *WaitlistPro*

📋 *Opportunity*
> Simple waitlist tool for indie hackers

📊 *Validation Score*: 82/100
💰 *Projected MRR* (12mo): $2,400 - $8,500
⏱️ *Build Estimate*: 2 weeks

🔗 Linear Project: [View Project](linear-url)

*Approval Checkpoints*: Design, Build, Launch
```

### Phase Completion
```
✅ Phase Complete: *Design*

📝 *Deliverables*:
• PRD: [View Document](link)
• User Flows: [Miro Board](link)
• 4 features defined

📋 Created 6 Linear issues

⏸️ *Awaiting Approval*
React with ✅ to proceed to Spec phase
```

---

## Error Handling

```python
class FactoryError(Exception):
    phase: str
    recoverable: bool
    context: dict

async def handle_factory_error(state: FactoryState, error: FactoryError):
    """Handle errors during factory execution."""
    
    # Log error
    state.errors.append({
        "phase": error.phase,
        "message": str(error),
        "timestamp": datetime.utcnow(),
        "context": error.context,
    })
    
    # Notify Slack
    await slack.send(
        channel="#factory-alerts",
        text=f"⚠️ Factory error in *{error.phase}* for *{state.handoff.opportunity.name}*",
    )
    
    if error.recoverable and state.retries < 3:
        state.retries += 1
        await retry_phase(state, error.phase)
    else:
        # Pause for human intervention
        await linear.issue_create({
            "project_id": state.handoff.linear_project_id,
            "title": f"[Factory Error] {error.phase} phase failed",
            "description": f"Error: {error}\n\nContext: {error.context}",
            "label_ids": ["blocked"],
            "priority": 1,
        })
```

---

## Implementation Checklist

- [ ] Define `FactoryHandoff` model in `src/models/handoff.py`
- [ ] Implement `trigger_factory()` entry point
- [ ] Create Slack notification templates for handoff
- [ ] Add Linear project validation (ensure structure exists)
- [ ] Implement phase output data models
- [ ] Wire context passing between phases in orchestrator
- [ ] Add checkpoint pause/resume logic
- [ ] Implement error handling and retry logic
- [ ] Create integration tests for handoff flow
