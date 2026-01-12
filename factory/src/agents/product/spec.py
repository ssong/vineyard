"""Spec Agent - Technical specifications and task breakdown."""

from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import SPEC_AGENT_PROMPT
from src.models import (
    APIEndpoint,
    DatabaseTable,
    DesignOutput,
    EngineeringTask,
    FactoryState,
    SpecOutput,
)
from src.tools import llm, miro


class SpecAgent(BaseAgent):
    """Agent for creating technical specifications."""

    name = "SpecAgent"
    domain = "product"

    def run(self, state: FactoryState) -> SpecOutput:
        """
        Generate technical spec, API contracts, database schema, and task breakdown.
        """
        self.log_start()

        opp = state.handoff.opportunity
        design = self.get_previous_output(state, "design")
        prefs = state.handoff.build_preferences

        # Generate technical spec
        tech_spec = self._generate_tech_spec(opp, design, prefs)

        # Generate API endpoints
        api_endpoints = self._generate_api_endpoints(opp, design)

        # Generate database schema
        db_schema = self._generate_database_schema(opp, design)

        # Create architecture Miro board
        miro_url = self._create_architecture_board(opp, api_endpoints, db_schema)

        # Generate task breakdown
        tasks = self._generate_task_breakdown(opp, design, api_endpoints, db_schema)
        # Note: Linear task tracking is now handled at the runner level

        output = SpecOutput(
            technical_spec_markdown=tech_spec,
            api_endpoints=api_endpoints,
            database_schema=db_schema,
            task_breakdown=tasks,
            architecture_miro_url=miro_url,
        )

        self.log_complete()
        return output

    def _generate_tech_spec(self, opp, design: DesignOutput, prefs) -> str:
        """Generate comprehensive technical specification."""
        features_text = ""
        if design and design.features:
            features_text = "\n".join(
                [f"- {f.name} ({f.priority}): {f.description}" for f in design.features[:10]]
            )

        user_prompt = f"""Write a technical specification for this product:

PRODUCT: {opp.name}
DESCRIPTION: {opp.detailed_description}
BUILD COMPLEXITY: {opp.build_complexity}
BUILD TIME: {opp.estimated_build_weeks} weeks

TECH STACK:
- Frontend: {prefs.tech_stack.get('frontend', 'rails')}
- Backend: {prefs.tech_stack.get('backend', 'ruby')}
- Database: {prefs.tech_stack.get('database', 'postgresql')}
- Hosting: {prefs.hosting_preference}
- Auth: {prefs.auth_preference}
- Payments: {prefs.payments_preference}

FEATURES:
{features_text}

Write a technical spec in markdown with:
1. System Architecture Overview
2. Technology Stack Details
3. API Design Principles
4. Database Design Principles
5. Authentication & Authorization
6. Third-party Integrations
7. Performance Requirements
8. Security Considerations
9. Deployment Strategy
10. Monitoring & Logging
"""

        try:
            # Use extended thinking for architecture decisions
            return llm.generate(
                SPEC_AGENT_PROMPT,
                user_prompt,
                model=llm.MODEL_OPUS,
                use_extended_thinking=True,
                thinking_budget=10000,
            )
        except Exception as e:
            self.logger.error(f"Failed to generate tech spec: {e}")
            return f"# {opp.name} Technical Specification\n\n[Generation failed]"

    def _generate_api_endpoints(self, opp, design: DesignOutput) -> list[APIEndpoint]:
        """Generate API endpoint specifications."""
        features_text = ""
        if design and design.features:
            features_text = "\n".join(
                [f"- {f.name}: {f.description}" for f in design.features if f.priority == "P0"]
            )

        user_prompt = f"""Design API endpoints for this product:

PRODUCT: {opp.name}
BUSINESS MODEL: {opp.business_model}

P0 FEATURES:
{features_text}

Generate JSON with API endpoints:
{{
    "endpoints": [
        {{
            "method": "POST",
            "path": "/api/v1/resource",
            "description": "Create a new resource",
            "request_schema": {{
                "field1": "string",
                "field2": "number"
            }},
            "response_schema": {{
                "id": "string",
                "field1": "string",
                "created_at": "datetime"
            }},
            "auth_required": true
        }}
    ]
}}

Include:
- Authentication endpoints (signup, login, logout)
- Core resource CRUD
- Subscription/billing endpoints
- Webhook handlers if needed
"""

        try:
            # Use extended thinking for API design decisions
            result = llm.generate_json(
                SPEC_AGENT_PROMPT,
                user_prompt,
                model=llm.MODEL_OPUS,
                use_extended_thinking=True,
                thinking_budget=6000,
            )
            endpoints = []

            for e in result.get("endpoints", []):
                endpoint = APIEndpoint(
                    method=e.get("method", "GET"),
                    path=e.get("path", "/api/unknown"),
                    description=e.get("description", ""),
                    request_schema=e.get("request_schema", {}),
                    response_schema=e.get("response_schema", {}),
                    auth_required=e.get("auth_required", True),
                )
                endpoints.append(endpoint)

            return endpoints

        except Exception as e:
            self.logger.error(f"Failed to generate API endpoints: {e}")
            return []

    def _generate_database_schema(self, opp, design: DesignOutput) -> list[DatabaseTable]:
        """Generate database schema design."""
        user_prompt = f"""Design database schema for this product:

PRODUCT: {opp.name}
BUSINESS MODEL: {opp.business_model}
TARGET: {opp.target_segment}

Generate JSON with database tables:
{{
    "tables": [
        {{
            "name": "users",
            "description": "User accounts",
            "columns": [
                {{"name": "id", "type": "uuid", "primary": true}},
                {{"name": "email", "type": "varchar(255)", "unique": true}},
                {{"name": "created_at", "type": "timestamp", "default": "now()"}}
            ],
            "indexes": ["idx_users_email"],
            "relationships": ["has_many subscriptions"]
        }}
    ]
}}

Include tables for:
- Users
- Core domain entities
- Subscriptions/billing
- Audit/activity logs
"""

        try:
            # Use extended thinking for database schema design
            result = llm.generate_json(
                SPEC_AGENT_PROMPT,
                user_prompt,
                model=llm.MODEL_OPUS,
                use_extended_thinking=True,
                thinking_budget=6000,
            )
            tables = []

            for t in result.get("tables", []):
                table = DatabaseTable(
                    name=t.get("name", "unknown"),
                    description=t.get("description", ""),
                    columns=t.get("columns", []),
                    indexes=t.get("indexes", []),
                    relationships=t.get("relationships", []),
                )
                tables.append(table)

            return tables

        except Exception as e:
            self.logger.error(f"Failed to generate database schema: {e}")
            return []

    def _create_architecture_board(
        self, opp, endpoints: list[APIEndpoint], tables: list[DatabaseTable]
    ) -> str:
        """Create Miro architecture diagram."""
        try:
            board = miro.create_board(
                f"Architecture: {opp.name}",
                "System architecture diagram",
            )
            board_id = board.get("id", "mock-id")

            # Create main components
            miro.create_shape(board_id, "Frontend\n(Hotwire)", "rectangle", 0, 0, 150, 80, "#bfdbfe")
            miro.create_shape(board_id, "API\n(Rails)", "rectangle", 250, 0, 150, 80, "#bbf7d0")
            miro.create_shape(board_id, "Database\n(PostgreSQL)", "rectangle", 500, 0, 150, 80, "#fed7aa")
            miro.create_shape(board_id, "Auth\n(Devise)", "rectangle", 250, 150, 150, 80, "#fecaca")
            miro.create_shape(board_id, "Payments\n(Stripe)", "rectangle", 250, 300, 150, 80, "#e9d5ff")

            return board.get("viewLink", "")

        except Exception as e:
            self.logger.error(f"Failed to create Miro board: {e}")
            return ""

    def _generate_task_breakdown(
        self,
        opp,
        design: DesignOutput,
        endpoints: list[APIEndpoint],
        tables: list[DatabaseTable],
    ) -> list[EngineeringTask]:
        """Generate engineering task breakdown."""
        features = design.features if design else []
        p0_features = [f for f in features if f.priority == "P0"]

        user_prompt = f"""Create engineering task breakdown for this product:

PRODUCT: {opp.name}
BUILD TIME: {opp.estimated_build_weeks} weeks
COMPLEXITY: {opp.build_complexity}

P0 FEATURES:
{chr(10).join([f"- {f.name}: {f.description}" for f in p0_features])}

API ENDPOINTS: {len(endpoints)} endpoints
DATABASE TABLES: {len(tables)} tables

Generate JSON with engineering tasks:
{{
    "tasks": [
        {{
            "title": "Setup project scaffold",
            "description": "Initialize Rails project with RuboCop, configure linting",
            "acceptance_criteria": [
                "Project builds successfully",
                "RuboCop passes"
            ],
            "story_points": 2,
            "labels": ["setup", "frontend"],
            "dependencies": []
        }}
    ]
}}

Include tasks for:
- Project setup
- Database setup and migrations
- Authentication integration
- Core API endpoints
- Frontend pages/components
- Payment integration
- Testing
- Deployment setup
"""

        try:
            # Use extended thinking for task breakdown and estimation
            result = llm.generate_json(
                SPEC_AGENT_PROMPT,
                user_prompt,
                model=llm.MODEL_OPUS,
                use_extended_thinking=True,
                thinking_budget=8000,
            )
            tasks = []

            for t in result.get("tasks", []):
                task = EngineeringTask(
                    title=t.get("title", "Untitled Task"),
                    description=t.get("description", ""),
                    acceptance_criteria=t.get("acceptance_criteria", []),
                    story_points=t.get("story_points", 1),
                    labels=t.get("labels", []),
                    dependencies=t.get("dependencies", []),
                )
                tasks.append(task)

            return tasks

        except Exception as e:
            self.logger.error(f"Failed to generate task breakdown: {e}")
            return []

