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
    "prd_analysis": [
        {
            "key": "gap_analysis",
            "title": "Analyze PRD for gaps and ambiguities",
            "objective": "Identify missing sections, unclear requirements, and areas needing clarification in the submitted PRD.",
            "approach": "Will analyze the PRD for: (1) missing user personas or unclear target audience, (2) vague scope or undefined MVP boundaries, (3) absent success metrics, (4) missing edge cases, (5) unclear technical constraints.",
            "inputs": [
                "Raw PRD text from user submission",
                "Additional context if provided",
            ],
            "expected_output": "List of identified gaps and clarifying questions.",
        },
        {
            "key": "qa_session",
            "title": "Clarification Q&A with submitter",
            "objective": "Get answers to critical questions from the PRD submitter to fill gaps.",
            "approach": "Will post clarifying questions to Slack thread, wait for user responses (up to 30 min timeout), and collect answers.",
            "inputs": [
                "Identified gaps from analysis",
                "Slack channel and thread info",
            ],
            "expected_output": "Q&A pairs with user responses.",
        },
        {
            "key": "prd_enrichment",
            "title": "Enrich PRD with structured content",
            "objective": "Produce a comprehensive, structured PRD incorporating user answers and filling remaining gaps.",
            "approach": "Will take the original PRD and Q&A answers to produce: (1) structured problem statement, (2) target user definitions, (3) MVP scope, (4) success metrics, (5) feature list with priorities.",
            "inputs": [
                "Original PRD text",
                "Q&A pairs",
                "Gap analysis results",
            ],
            "expected_output": "Enriched PRD in markdown with all sections filled.",
        },
    ],

    "design": [
        {
            "key": "prd_enhancement",
            "title": "Enhance PRD with design specifications",
            "objective": "Add structured design sections to the enriched PRD including feature priorities and acceptance criteria.",
            "approach": "Will enhance PRD with: (1) feature priority matrix (P0/P1/P2), (2) detailed user stories in Given/When/Then format, (3) success metrics with targets, (4) edge cases.",
            "inputs": [
                "Enriched PRD from PRD Analysis phase",
                "Target users and core problem",
            ],
            "expected_output": "Complete enhanced PRD with design specifications.",
        },
        {
            "key": "user_flows",
            "title": "Create user flow diagrams",
            "objective": "Map the key user journeys through the product.",
            "approach": "Will design user flows for: (1) signup to activation, (2) core value loop, (3) upgrade/payment flow, (4) key error/edge cases.",
            "inputs": [
                "Enhanced PRD features and user stories",
                "Target user definitions",
            ],
            "expected_output": "User flow definitions with steps, screens, and success metrics.",
        },
        {
            "key": "features",
            "title": "Define feature specifications",
            "objective": "Create detailed specifications for each feature with acceptance criteria.",
            "approach": "Will generate feature specs with: (1) name and description, (2) priority (P0/P1/P2), (3) user stories, (4) acceptance criteria (Given/When/Then), (5) technical notes.",
            "inputs": [
                "Enhanced PRD feature list",
                "Tech stack preference",
            ],
            "expected_output": "Feature specifications with user stories and acceptance criteria.",
        },
        {
            "key": "ui_copy",
            "title": "Generate UI copy and messaging",
            "objective": "Create the key UI text and messaging for the application.",
            "approach": "Will generate: (1) landing page headlines and CTAs, (2) onboarding messages, (3) success/error states, (4) empty states.",
            "inputs": [
                "Product name and summary",
                "Target users",
            ],
            "expected_output": "UI copy dictionary with headlines, CTAs, messages.",
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
            "approach": "Will create: (1) landing page sections (hero, features, pricing, testimonials), (2) launch checklist with key milestones.",
            "inputs": [
                "Product name and summary",
                "Feature specifications",
                "Target users",
            ],
            "expected_output": "Marketing content package with landing page copy and launch checklist.",
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
