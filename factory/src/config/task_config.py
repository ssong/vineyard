"""Task configuration for factory phases.

Defines the meaningful tasks for each phase with approach descriptions
that allow operator review before execution.
"""

from typing import TypedDict


class TaskConfig(TypedDict):
    """Configuration for a single task."""
    key: str  # Unique identifier for the task
    title: str  # Display title for the Linear issue
    objective: str  # What this task accomplishes
    approach: str  # How the agent will execute this task
    inputs: list[str]  # What inputs will be used
    expected_output: str  # What will be produced


# Task definitions for each phase
PHASE_TASKS: dict[str, list[TaskConfig]] = {
    "research_enrichment": [
        {
            "key": "market_analysis",
            "title": "Analyze market size and trends",
            "objective": "Determine the total addressable market (TAM), serviceable addressable market (SAM), and serviceable obtainable market (SOM) for this opportunity.",
            "approach": "Will analyze market size using: (1) target market description from opportunity, (2) pricing assumptions, (3) competitor revenue estimates where available. Will apply conservative, moderate, and optimistic assumptions.",
            "inputs": [
                "Opportunity target market description",
                "Suggested pricing tiers",
                "Category and segment info",
            ],
            "expected_output": "Market analysis with TAM/SAM/SOM estimates and growth projections.",
        },
        {
            "key": "competitor_research",
            "title": "Research competitor landscape",
            "objective": "Map the competitive landscape with feature comparisons and positioning analysis.",
            "approach": "Will identify top 5 competitors by: (1) analyzing direct competitors from opportunity, (2) feature-by-feature comparison matrix, (3) pricing analysis, (4) strengths and weaknesses assessment.",
            "inputs": [
                "Direct competitors list from opportunity",
                "Competitor weaknesses from initial research",
                "Differentiation angle",
            ],
            "expected_output": "Competitor feature matrix with pricing, strengths, and weaknesses for each.",
        },
        {
            "key": "persona_development",
            "title": "Develop target user personas",
            "objective": "Create detailed user personas representing the target audience segments.",
            "approach": "Will create 2-4 user personas based on: (1) target market description, (2) problem statement and pain points, (3) business model. Each persona includes demographics, role, pain points, goals, and jobs-to-be-done.",
            "inputs": [
                "Target market description",
                "Problem statement",
                "Business model",
                "Target segment",
            ],
            "expected_output": "2-4 detailed user personas with demographics, pain points, and JTBD.",
        },
        {
            "key": "seo_strategy",
            "title": "Define SEO and content strategy",
            "objective": "Identify target keywords and content opportunities for organic growth.",
            "approach": "Will analyze: (1) primary keywords from product name and category, (2) long-tail keyword opportunities, (3) competitor keyword gaps, (4) content type recommendations (blog, guides, comparisons).",
            "inputs": [
                "Product name and one-liner",
                "Category and target segment",
                "Competitor names",
            ],
            "expected_output": "SEO strategy with keyword targets, content recommendations, and priority ranking.",
        },
    ],
    
    "design": [
        {
            "key": "prd",
            "title": "Write Product Requirements Document",
            "objective": "Create a comprehensive PRD that defines the product vision, goals, and requirements.",
            "approach": "Will generate PRD with: (1) problem statement and goals, (2) target users from personas, (3) core features (P0/P1/P2), (4) user stories, (5) success metrics. Format follows standard SaaS PRD template.",
            "inputs": [
                "Research enrichment output (personas, market analysis)",
                "Opportunity description and problem statement",
                "Pricing tiers",
            ],
            "expected_output": "Complete PRD in markdown with problem statement, features, user stories, and metrics.",
        },
        {
            "key": "user_flows",
            "title": "Create user flow diagrams",
            "objective": "Map the key user journeys through the product.",
            "approach": "Will design user flows for: (1) signup to activation, (2) core value loop, (3) upgrade/payment flow, (4) key error/edge cases. Each flow includes screens, actions, and decision points.",
            "inputs": [
                "PRD features and user stories",
                "Business model (payment flows)",
                "Target personas",
            ],
            "expected_output": "User flow definitions with steps, screens, and success metrics for each flow.",
        },
        {
            "key": "features",
            "title": "Define feature specifications",
            "objective": "Create detailed specifications for each feature with acceptance criteria.",
            "approach": "Will generate feature specs with: (1) feature name and description, (2) priority (P0/P1/P2), (3) user stories, (4) acceptance criteria (Given/When/Then), (5) technical notes.",
            "inputs": [
                "PRD feature list",
                "Technical components from opportunity",
                "Build complexity estimate",
            ],
            "expected_output": "Feature specifications with user stories and acceptance criteria for each.",
        },
        {
            "key": "ui_copy",
            "title": "Generate UI copy and messaging",
            "objective": "Create the key UI text and messaging for the application.",
            "approach": "Will generate: (1) landing page headlines and CTAs, (2) onboarding messages, (3) success/error states, (4) empty states, (5) email notification copy. Voice should match target audience.",
            "inputs": [
                "Product one-liner and description",
                "Target market description",
                "Personas",
            ],
            "expected_output": "UI copy dictionary with headlines, CTAs, messages, and notification templates.",
        },
    ],
    
    "spec": [
        {
            "key": "architecture",
            "title": "Design system architecture",
            "objective": "Define the technical architecture and infrastructure design.",
            "approach": "Will design: (1) frontend/backend architecture based on tech stack preferences, (2) database structure, (3) external service integrations, (4) scalability considerations.",
            "inputs": [
                "Tech stack preferences (frontend, backend, database)",
                "Auth and payment preferences",
                "Hosting preference",
            ],
            "expected_output": "Architecture overview with component diagram and technology decisions.",
        },
        {
            "key": "api_design",
            "title": "Design API endpoints",
            "objective": "Define the REST/GraphQL API structure with request/response schemas.",
            "approach": "Will design: (1) RESTful endpoints for each resource, (2) request/response JSON schemas, (3) authentication requirements per endpoint, (4) rate limiting recommendations.",
            "inputs": [
                "Feature specifications",
                "Auth preference",
                "Database schema (if available)",
            ],
            "expected_output": "API endpoint definitions with paths, methods, schemas, and auth requirements.",
        },
        {
            "key": "database_schema",
            "title": "Create database schema",
            "objective": "Design the database tables, relationships, and indexes.",
            "approach": "Will create: (1) tables for each domain entity, (2) column definitions with types, (3) relationships and foreign keys, (4) indexes for query optimization.",
            "inputs": [
                "Feature specifications",
                "API endpoint requirements",
                "Database preference (PostgreSQL, etc.)",
            ],
            "expected_output": "Database schema with tables, columns, relationships, and indexes.",
        },
        {
            "key": "engineering_tasks",
            "title": "Break down engineering tasks",
            "objective": "Create a detailed task breakdown for implementation.",
            "approach": "Will generate: (1) implementation tasks grouped by component, (2) effort estimates, (3) dependencies, (4) priority ordering for MVP.",
            "inputs": [
                "Architecture design",
                "API endpoints",
                "Feature specifications",
                "Build complexity estimate",
            ],
            "expected_output": "Engineering task list with descriptions, estimates, and dependencies.",
        },
    ],
    
    "build": [
        {
            "key": "code_generation",
            "title": "Generate application code",
            "objective": "Generate the core application code including frontend, backend, and utilities.",
            "approach": "Will generate in dependency order: (1) project structure and config, (2) utility libraries (auth, db, api client), (3) database migrations, (4) API routes, (5) shared components, (6) frontend pages.",
            "inputs": [
                "Technical specification (architecture, API, schema)",
                "Tech stack preferences",
                "Feature specifications",
            ],
            "expected_output": "Generated codebase pushed to GitHub repository.",
        },
        {
            "key": "test_generation",
            "title": "Generate test suite",
            "objective": "Create comprehensive tests for the application.",
            "approach": "Will generate: (1) test configuration (Jest/Vitest, Playwright), (2) test fixtures and mocks, (3) unit tests for utilities and components, (4) integration tests for API routes, (5) E2E tests for core user flows.",
            "inputs": [
                "Generated source code",
                "API endpoint specifications",
                "User flows from design",
            ],
            "expected_output": "Test files pushed to repository covering unit, integration, and E2E tests.",
        },
        {
            "key": "security_review",
            "title": "Perform security review",
            "objective": "Analyze code for security vulnerabilities and generate recommendations.",
            "approach": "Will check: (1) OWASP Top 10 coverage, (2) authentication implementation, (3) input validation, (4) secrets handling, (5) dependency security.",
            "inputs": [
                "Generated source code",
                "Auth and payment preferences",
            ],
            "expected_output": "Security report with findings, risk levels, and remediation recommendations.",
        },
        {
            "key": "devops_setup",
            "title": "Configure deployment infrastructure",
            "objective": "Generate deployment configuration and CI/CD pipelines.",
            "approach": "Will generate: (1) Dockerfile, (2) docker-compose for local dev, (3) GitHub Actions CI/CD workflows, (4) deployment config for hosting platform, (5) environment documentation.",
            "inputs": [
                "Hosting preference",
                "Database preference",
                "Tech stack",
            ],
            "expected_output": "Infrastructure files pushed to repository, ready for deployment.",
        },
    ],
    
    "launch_prep": [
        {
            "key": "marketing_content",
            "title": "Create marketing content",
            "objective": "Generate marketing copy, landing page content, and launch materials.",
            "approach": "Will create: (1) landing page sections (hero, features, pricing, testimonials), (2) email sequences (welcome, onboarding), (3) social media content for launch.",
            "inputs": [
                "Product description and one-liner",
                "Feature specifications",
                "Pricing tiers",
                "Target personas",
            ],
            "expected_output": "Marketing content package with landing page copy, emails, and social posts.",
        },
        {
            "key": "support_setup",
            "title": "Set up customer support infrastructure",
            "objective": "Create support documentation and help desk configuration.",
            "approach": "Will generate: (1) FAQ document, (2) troubleshooting guides, (3) knowledge base structure, (4) support email templates.",
            "inputs": [
                "Feature specifications",
                "Common user flows",
                "Known edge cases",
            ],
            "expected_output": "Support documentation package with FAQ, guides, and templates.",
        },
    ],
    
    "launch": [
        {
            "key": "deployment",
            "title": "Deploy to production",
            "objective": "Execute production deployment and verify the application is live.",
            "approach": "Will: (1) trigger production deployment via CI/CD, (2) verify health checks pass, (3) confirm core functionality works, (4) document the live URLs.",
            "inputs": [
                "Deployment configuration",
                "Environment secrets (configured externally)",
            ],
            "expected_output": "Live production URLs and deployment confirmation.",
        },
        {
            "key": "launch_announcement",
            "title": "Execute launch announcement",
            "objective": "Publish launch announcements across configured channels.",
            "approach": "Will: (1) prepare Product Hunt listing if configured, (2) schedule social media posts, (3) send launch email to waitlist.",
            "inputs": [
                "Marketing content from launch prep",
                "Social channel configurations",
            ],
            "expected_output": "Launch announcement URLs and scheduled post confirmations.",
        },
    ],
    
    "growth": [
        {
            "key": "growth_experiments",
            "title": "Design growth experiments",
            "objective": "Create a prioritized list of growth experiments to run.",
            "approach": "Will design: (1) acquisition experiments (SEO, content, ads), (2) activation experiments (onboarding optimization), (3) retention experiments (engagement features).",
            "inputs": [
                "Launch metrics baseline",
                "User personas",
                "Business model",
            ],
            "expected_output": "Growth experiment backlog with hypotheses, metrics, and priority ranking.",
        },
        {
            "key": "iteration_roadmap",
            "title": "Plan iteration roadmap",
            "objective": "Define the next iteration of features based on launch learnings.",
            "approach": "Will plan: (1) quick wins and bug fixes, (2) P1 features from spec, (3) user feedback integration points.",
            "inputs": [
                "P1/P2 features from spec",
                "Initial user feedback (when available)",
            ],
            "expected_output": "Next iteration roadmap with prioritized features and timeline.",
        },
    ],
}


def get_phase_tasks(phase_name: str) -> list[TaskConfig]:
    """Get the task configurations for a phase."""
    return PHASE_TASKS.get(phase_name, [])


def get_task_by_key(phase_name: str, task_key: str) -> TaskConfig | None:
    """Get a specific task configuration by key."""
    tasks = PHASE_TASKS.get(phase_name, [])
    for task in tasks:
        if task["key"] == task_key:
            return task
    return None
