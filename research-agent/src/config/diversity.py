"""Diversity configuration for opportunity discovery.

This module provides query pools, industry lists, and randomization
utilities to ensure diverse opportunity suggestions across runs.
"""

import random
from dataclasses import dataclass, field
from typing import Optional


# =============================================================================
# EXPANDED INDUSTRY POOL
# =============================================================================

INDUSTRIES = [
    # Construction & Trades
    "HVAC", "plumbing", "electrical", "roofing", "flooring",
    "painting contractors", "general contractors", "landscaping",
    "pest control", "pool service", "garage door repair",
    "locksmith", "appliance repair", "septic services",

    # Professional Services
    "accounting firms", "bookkeeping", "tax preparation",
    "law firms", "legal services", "notary services",
    "architecture firms", "engineering consultancies",
    "surveying companies", "court reporting", "translation services",

    # Healthcare & Wellness
    "dental practices", "veterinary clinics", "optometry",
    "chiropractic", "physical therapy", "occupational therapy",
    "mental health practices", "home health agencies",
    "medical billing", "pharmacies", "lab services",
    "senior care facilities", "hospice care",

    # Property & Real Estate
    "property management", "real estate brokerages",
    "home inspection", "appraisal services", "title companies",
    "storage facilities", "parking management",

    # Automotive & Transportation
    "auto repair shops", "auto body shops", "tire shops",
    "car dealerships", "fleet management", "towing companies",
    "moving companies", "freight brokers", "courier services",

    # Hospitality & Events
    "event venues", "catering companies", "wedding planners",
    "party rental", "photography studios", "DJ services",
    "hotels", "bed and breakfasts", "vacation rentals",

    # Education & Training
    "tutoring centers", "music schools", "dance studios",
    "martial arts schools", "driving schools", "trade schools",
    "daycare centers", "after-school programs",

    # Retail & Services
    "dry cleaners", "laundromats", "car washes",
    "printing shops", "sign shops", "trophy shops",
    "pawn shops", "consignment stores", "florists",

    # Food & Beverage
    "restaurants", "food trucks", "bakeries", "catering",
    "coffee shops", "breweries", "wineries", "distilleries",

    # Manufacturing & Industrial
    "machine shops", "fabrication shops", "woodworking",
    "3D printing services", "electronics manufacturing",
    "packaging companies", "warehousing",

    # Agriculture & Outdoor
    "farms", "nurseries", "tree services", "irrigation",
    "agricultural equipment", "feed stores",

    # Fitness & Recreation
    "gyms", "yoga studios", "pilates studios", "crossfit boxes",
    "personal training", "sports facilities", "bowling alleys",
    "golf courses", "marinas",

    # Personal Services
    "salons", "barbershops", "spas", "nail salons",
    "tattoo parlors", "funeral homes", "pet grooming",
    "pet boarding", "dog walking",

    # Professional B2B
    "staffing agencies", "recruiting firms", "HR consultancies",
    "marketing agencies", "PR firms", "web design agencies",
    "IT services", "managed service providers",
    "security companies", "commercial cleaning",
    "janitorial services", "office supply distributors",

    # Specialty Niches
    "medical equipment suppliers", "lab equipment",
    "dental labs", "prosthetics", "orthotics",
    "uniform suppliers", "safety equipment",
    "industrial supplies", "restaurant equipment",
]

# =============================================================================
# PLATFORM/TOOL POOLS FOR UNBUNDLING
# =============================================================================

UNBUNDLING_TARGETS = [
    # Project Management
    ("Asana", ["simple task tracking", "team todos", "personal projects"]),
    ("Monday.com", ["basic workflows", "simple boards", "team tracking"]),
    ("Jira", ["bug tracking", "simple tickets", "small team projects"]),
    ("Notion", ["simple wikis", "basic databases", "team docs"]),
    ("Airtable", ["simple spreadsheets", "basic CRM", "inventory"]),
    ("ClickUp", ["task management", "simple docs", "time tracking"]),

    # CRM & Sales
    ("Salesforce", ["small business CRM", "simple pipeline", "contact management"]),
    ("HubSpot", ["email tracking", "simple CRM", "basic marketing"]),
    ("Pipedrive", ["deal tracking", "simple sales", "contact notes"]),

    # Marketing
    ("Mailchimp", ["simple newsletters", "basic automation", "landing pages"]),
    ("Marketo", ["email campaigns", "lead scoring", "simple nurture"]),
    ("Hootsuite", ["simple scheduling", "basic analytics", "single platform"]),

    # Finance & Accounting
    ("QuickBooks", ["simple invoicing", "expense tracking", "basic reports"]),
    ("Xero", ["invoicing", "bank reconciliation", "simple accounting"]),
    ("NetSuite", ["basic ERP", "simple inventory", "order management"]),

    # HR & Operations
    ("BambooHR", ["simple time off", "employee directory", "basic HR"]),
    ("Workday", ["time tracking", "simple payroll", "basic HR"]),
    ("Gusto", ["simple payroll", "basic benefits", "contractor payments"]),

    # Design & Creative
    ("Adobe Creative Suite", ["simple graphics", "basic video", "social images"]),
    ("Figma", ["simple mockups", "basic wireframes", "quick designs"]),
    ("Canva", ["specific templates", "brand assets", "social graphics"]),

    # Development
    ("GitHub", ["simple repos", "basic CI", "code review"]),
    ("AWS", ["simple hosting", "basic storage", "simple compute"]),
    ("Vercel", ["simple deploys", "basic hosting", "static sites"]),

    # Communication
    ("Slack", ["simple chat", "team updates", "async standups"]),
    ("Zoom", ["simple meetings", "basic webinars", "quick calls"]),
    ("Intercom", ["simple chat", "basic support", "help docs"]),

    # Analytics
    ("Google Analytics", ["simple metrics", "basic dashboards", "privacy-focused"]),
    ("Mixpanel", ["simple events", "basic funnels", "user tracking"]),
    ("Amplitude", ["product analytics", "simple cohorts", "basic retention"]),
]

# =============================================================================
# PRODUCTIZED SERVICE OPPORTUNITIES
# =============================================================================

PRODUCTIZABLE_SERVICES = [
    # Content & Creative
    "logo design", "brand identity", "social media graphics",
    "presentation design", "infographic creation", "video editing",
    "podcast editing", "thumbnail creation", "banner ads",
    "product photography", "headshot retouching", "photo editing",

    # Writing & Copy
    "blog writing", "product descriptions", "email copywriting",
    "resume writing", "press releases", "case studies",
    "technical writing", "grant writing", "proposal writing",

    # Marketing
    "SEO audits", "keyword research", "competitor analysis",
    "social media management", "influencer outreach", "PR outreach",
    "email campaign setup", "landing page optimization",

    # Technical
    "website audits", "security audits", "performance optimization",
    "data entry", "data cleaning", "spreadsheet automation",
    "API integration", "database migration", "code review",

    # Business Operations
    "bookkeeping", "invoice processing", "expense categorization",
    "payroll processing", "tax preparation", "financial modeling",
    "business plan writing", "pitch deck creation",

    # Research & Analysis
    "market research", "competitive intelligence", "user research",
    "survey analysis", "data visualization", "report generation",

    # Administrative
    "virtual assistance", "calendar management", "travel booking",
    "document formatting", "transcription", "translation",
]

# =============================================================================
# INTEGRATION PAIRS
# =============================================================================

INTEGRATION_OPPORTUNITIES = [
    # CRM + Other
    ("HubSpot", "QuickBooks", "sync deals to invoices"),
    ("Salesforce", "Notion", "sync accounts to wiki"),
    ("Pipedrive", "Calendly", "auto-create deals from meetings"),

    # Project Management + Other
    ("Asana", "Harvest", "time tracking sync"),
    ("Monday.com", "Xero", "project billing"),
    ("ClickUp", "Toggl", "time entries to tasks"),
    ("Jira", "Confluence", "ticket documentation"),

    # E-commerce + Other
    ("Shopify", "QuickBooks", "order to invoice sync"),
    ("WooCommerce", "Mailchimp", "customer segmentation"),
    ("Stripe", "Notion", "payment to database"),

    # Communication + Other
    ("Slack", "Linear", "issue updates"),
    ("Discord", "Notion", "community to docs"),
    ("Intercom", "Jira", "support to tickets"),

    # Marketing + Other
    ("Mailchimp", "Airtable", "subscriber management"),
    ("ConvertKit", "Teachable", "student sync"),
    ("ActiveCampaign", "Calendly", "meeting follow-ups"),

    # Development + Other
    ("GitHub", "Linear", "PR to issue sync"),
    ("GitLab", "Slack", "pipeline notifications"),
    ("Vercel", "Notion", "deployment docs"),

    # Finance + Other
    ("Stripe", "Slack", "payment alerts"),
    ("QuickBooks", "Gusto", "payroll sync"),
    ("Xero", "Harvest", "time to invoices"),
]

# =============================================================================
# QUERY TEMPLATES
# =============================================================================

QUERY_TEMPLATES = {
    "trend_signals": [
        "micro saas ideas {year} underserved niches",
        "B2B software gaps small business {year}",
        "saas opportunities solo founders {year}",
        "what software do you wish existed site:reddit.com",
        "annoying manual process at work site:reddit.com",
        "spreadsheet hell at work site:reddit.com",
        "software that should exist but doesn't",
        "why is there no software for site:reddit.com",
        "I'd pay for software that site:reddit.com",
        "business process we still do manually",
        "startup ideas from working in {industry}",
        "problems nobody is solving {year}",
        "underserved B2B markets {year}",
        "boring software business ideas",
        "unsexy saas opportunities",
    ],

    "pain_points": [
        "{industry} software complaints site:reddit.com",
        "{industry} software frustrations site:reddit.com",
        "worst thing about {industry} software",
        "{industry} still using spreadsheets {year}",
        "{industry} manual processes that need automation",
        "{industry} software too expensive",
        "{industry} software missing features",
        "hate my {industry} software site:reddit.com",
        "{industry} workflow inefficiencies",
        "{industry} time wasters",
    ],

    "unbundling": [
        "{platform} too complicated for small business",
        "{platform} overkill for {use_case}",
        "simpler alternative to {platform}",
        "{platform} but just for {use_case}",
        "lightweight {platform} alternative",
        "{platform} features I never use",
        "switching from {platform} to something simpler",
        "{platform} too expensive for what I need",
    ],

    "productized_services": [
        "{service} freelancer rates upwork fiverr",
        "{service} agency pricing too expensive",
        "automate {service} process",
        "{service} takes too long manually",
        "DIY {service} tools for small business",
        "{service} without hiring someone",
    ],

    "integrations": [
        "{tool_a} {tool_b} integration problems",
        "sync {tool_a} with {tool_b}",
        "{tool_a} to {tool_b} zapier limitations",
        "export {tool_a} data to {tool_b}",
        "{tool_a} {tool_b} workflow automation",
    ],

    "developer_tools": [
        "developer tools pain points {year} site:reddit.com",
        "I built a tool to automate site:news.ycombinator.com",
        "developer workflow inefficiencies",
        "repetitive coding tasks that need automation",
        "CLI tool I wish existed",
        "developer productivity gaps {year}",
        "devops manual processes",
        "coding tasks I do every day",
    ],

    "competitor_gaps": [
        "{competitor} missing features site:reddit.com",
        "{competitor} complaints {year}",
        "switching from {competitor} because",
        "{competitor} alternative for {segment}",
        "why I left {competitor}",
        "{competitor} limitations frustrating",
    ],

    "emerging_trends": [
        "new regulations affecting {industry} {year}",
        "AI creating new problems for businesses",
        "remote work software gaps {year}",
        "post-pandemic business process changes",
        "new compliance requirements {industry}",
        "second-order effects of {trend}",
    ],
}

# =============================================================================
# DIVERSITY CONFIGURATION
# =============================================================================

@dataclass
class DiversityConfig:
    """Configuration for controlling discovery diversity."""

    # Framework focus (None = all frameworks)
    focus_frameworks: Optional[list[str]] = None

    # Industry focus (None = random selection)
    focus_industries: Optional[list[str]] = None

    # Categories to exclude
    exclude_categories: list[str] = field(default_factory=list)

    # Number of industries to sample per run
    industries_per_run: int = 8

    # Number of queries per category
    queries_per_category: int = 2

    # Total queries to execute
    total_queries: int = 10

    # Novelty weight (0-1, higher = favor less common ideas)
    novelty_weight: float = 0.5

    # LLM temperature variation range
    temperature_range: tuple[float, float] = (0.7, 1.0)

    # Extended thinking budget range
    thinking_budget_range: tuple[int, int] = (6000, 10000)

    # Past opportunities to exclude (slugs)
    exclude_slugs: list[str] = field(default_factory=list)

    # Past problem statements to avoid (for semantic dedup)
    exclude_problems: list[str] = field(default_factory=list)


def get_current_year() -> str:
    """Get current year for query templates."""
    from datetime import datetime
    return str(datetime.now().year)


def sample_industries(config: DiversityConfig) -> list[str]:
    """Sample industries based on configuration."""
    if config.focus_industries:
        return config.focus_industries
    return random.sample(INDUSTRIES, min(config.industries_per_run, len(INDUSTRIES)))


def sample_unbundling_target() -> tuple[str, str]:
    """Sample a platform and use case for unbundling queries."""
    platform, use_cases = random.choice(UNBUNDLING_TARGETS)
    use_case = random.choice(use_cases)
    return platform, use_case


def sample_integration_pair() -> tuple[str, str, str]:
    """Sample an integration opportunity."""
    return random.choice(INTEGRATION_OPPORTUNITIES)


def sample_productizable_service() -> str:
    """Sample a service that could be productized."""
    return random.choice(PRODUCTIZABLE_SERVICES)


def generate_diverse_queries(config: DiversityConfig) -> list[str]:
    """
    Generate a diverse set of search queries based on configuration.

    Ensures coverage across multiple categories and frameworks.
    """
    year = get_current_year()
    industries = sample_industries(config)
    queries = []

    # Track which categories we've covered
    categories_to_cover = [
        "trend_signals",
        "pain_points",
        "unbundling",
        "productized_services",
        "integrations",
        "developer_tools",
        "emerging_trends",
    ]

    # Filter based on focus frameworks
    if config.focus_frameworks:
        framework_to_category = {
            "unbundling": "unbundling",
            "productized_service": "productized_services",
            "integration": "integrations",
            "boring_business": "pain_points",
            "developer_tools": "developer_tools",
            "automation": "trend_signals",
        }
        categories_to_cover = [
            framework_to_category.get(f, "trend_signals")
            for f in config.focus_frameworks
        ]
        categories_to_cover = list(set(categories_to_cover))

    # Ensure at least one query from each category
    for category in categories_to_cover:
        templates = QUERY_TEMPLATES.get(category, [])
        if not templates:
            continue

        template = random.choice(templates)

        # Fill in template variables
        query = template.format(
            year=year,
            industry=random.choice(industries),
            platform=sample_unbundling_target()[0],
            use_case=sample_unbundling_target()[1],
            service=sample_productizable_service(),
            tool_a=sample_integration_pair()[0],
            tool_b=sample_integration_pair()[1],
            competitor=random.choice([t[0] for t in UNBUNDLING_TARGETS]),
            segment="small business",
            trend="AI automation",
        )
        queries.append(query)

    # Fill remaining slots with random queries
    all_templates = []
    for category, templates in QUERY_TEMPLATES.items():
        all_templates.extend([(category, t) for t in templates])

    while len(queries) < config.total_queries:
        category, template = random.choice(all_templates)
        query = template.format(
            year=year,
            industry=random.choice(industries),
            platform=sample_unbundling_target()[0],
            use_case=sample_unbundling_target()[1],
            service=sample_productizable_service(),
            tool_a=sample_integration_pair()[0],
            tool_b=sample_integration_pair()[1],
            competitor=random.choice([t[0] for t in UNBUNDLING_TARGETS]),
            segment="small business",
            trend="AI automation",
        )
        if query not in queries:
            queries.append(query)

    # Shuffle for good measure
    random.shuffle(queries)

    return queries[:config.total_queries]


def get_llm_parameters(config: DiversityConfig) -> dict:
    """Get randomized LLM parameters for variety."""
    return {
        "temperature": random.uniform(*config.temperature_range),
        "thinking_budget": random.randint(*config.thinking_budget_range),
    }
