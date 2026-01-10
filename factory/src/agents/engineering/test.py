"""Test Agent - Test generation for code."""

from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import TEST_AGENT_PROMPT
from src.models import FactoryState, GeneratedFile
from src.tools import github, linear, llm
from src.tools.generation_context import GenerationContext


class TestAgent(BaseAgent):
    """Agent for generating tests."""

    name = "TestAgent"
    domain = "engineering"

    def run(self, state: FactoryState) -> dict[str, Any]:
        """
        Generate unit and integration tests.

        Uses GenerationContext to:
        1. Build context from existing source files
        2. Track generated test files to prevent duplicates
        3. Ensure tests match actual source file structure
        """
        self.log_start()

        opp = state.handoff.opportunity
        prefs = state.handoff.build_preferences
        spec = self.get_previous_output(state, "spec")
        build = self.get_previous_output(state, "build")

        # Initialize context with existing source files from build phase
        ctx = GenerationContext()
        source_files = build.get("files", []) if build else []

        # Add source files to context for reference
        for f in source_files:
            exports = ctx.extract_exports_from_typescript(f.content)
            category = self._categorize_source_file(f.path)
            ctx.add_file(f.path, f.content, f.language, category, exports=exports)

        self.logger.info(f"Building tests for {len(source_files)} source files")

        # Generate test configuration first
        self._generate_test_config(ctx, prefs)

        # Generate test fixtures (needed by other tests)
        self._generate_test_fixtures(ctx, spec, source_files)

        # Generate unit tests
        self._generate_unit_tests(ctx, source_files, prefs)

        # Generate integration tests
        self._generate_integration_tests(ctx, spec, prefs)

        # Generate E2E test scenarios
        self._generate_e2e_tests(ctx, opp, prefs)

        # Get only test files (not source files)
        test_files = [
            GeneratedFile(path=e.path, content=e.content, language=e.language)
            for e in ctx.get_all_files()
            if e.category in ["test", "test_config", "fixture"]
        ]

        self.logger.info(f"Generated {len(test_files)} test files")

        # Push to GitHub
        self._push_tests_to_github(opp, test_files)

        # Create Linear issues
        linear_issues = self._create_linear_issues(state, test_files)

        # Count by type
        unit_count = len([f for f in test_files if "unit" in f.path or "__tests__" in f.path])
        integration_count = len([f for f in test_files if "integration" in f.path])
        e2e_count = len([f for f in test_files if "e2e" in f.path])

        output = {
            "test_files": test_files,
            "unit_test_count": unit_count,
            "integration_test_count": integration_count,
            "e2e_test_count": e2e_count,
            "linear_issues": linear_issues,
        }

        self.log_complete()
        return output

    def _categorize_source_file(self, path: str) -> str:
        """Categorize a source file for context tracking."""
        if "api" in path:
            return "api"
        elif "components" in path:
            return "component"
        elif "lib" in path or "utils" in path:
            return "utility"
        elif "app" in path and "page" in path:
            return "frontend"
        else:
            return "source"

    def _generate_test_config(self, ctx: GenerationContext, prefs) -> None:
        """Generate test configuration files."""
        frontend = prefs.tech_stack.get("frontend", "nextjs")

        user_prompt = f"""Generate test configuration files for a {frontend} project.

## Requirements

Generate JSON with configuration files:
{{
    "files": [
        {{
            "path": "jest.config.js",
            "language": "javascript",
            "content": "// Jest configuration"
        }},
        {{
            "path": "playwright.config.ts",
            "language": "typescript",
            "content": "// Playwright configuration"
        }}
    ]
}}

Generate:
1. jest.config.js or vitest.config.ts - Unit/integration test config
2. playwright.config.ts - E2E test config
3. __tests__/setup.ts - Test setup with mocks

These configs should work with {frontend} and TypeScript.
"""

        try:
            result = llm.generate_json(TEST_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                ctx.add_file(
                    f.get("path", "jest.config.js"),
                    f.get("content", ""),
                    f.get("language", "javascript"),
                    "test_config",
                )

        except Exception as e:
            self.logger.error(f"Failed to generate test config: {e}")

    def _generate_unit_tests(
        self, ctx: GenerationContext, source_files: list, prefs
    ) -> None:
        """Generate unit tests for source files."""
        # Group files by category for targeted test generation
        api_files = ctx.get_files_by_category("api")
        util_files = ctx.get_files_by_category("utility")
        component_files = ctx.get_files_by_category("component")

        # Build detailed file info with exports
        files_detail = []
        for entry in api_files + util_files:
            exports_str = ", ".join(entry.exports[:5]) if entry.exports else "default export"
            files_detail.append(f"- {entry.path}: exports {{ {exports_str} }}")

        files_text = "\n".join(files_detail[:15])

        user_prompt = f"""Generate unit tests for these source files.

## Source Files to Test
{files_text}

## Current Project Structure
{ctx.get_folder_structure()}

## Available Test Fixtures
{ctx.get_available_components(category="fixture")}

## Tech Stack
{prefs.tech_stack}

## Requirements

Generate JSON with test files:
{{
    "files": [
        {{
            "path": "__tests__/lib/auth.test.ts",
            "language": "typescript",
            "content": "// Full test implementation"
        }}
    ]
}}

For each source file, generate a corresponding test file that:
1. Imports the actual exports from the source file
2. Uses fixtures from __tests__/fixtures/ if available
3. Mocks external dependencies (database, API calls)
4. Tests happy path and error cases
5. Uses descriptive test names (describe/it blocks)

Test file naming: __tests__/[path]/[filename].test.ts

IMPORTANT:
- Import the ACTUAL exports from source files
- Use fixtures instead of inline mock data
- One test file per source file being tested
- Do NOT duplicate test files that already exist

{ctx.get_deduplication_instructions()}
"""

        try:
            result = llm.generate_json(TEST_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "__tests__/test.ts")
                content = f.get("content", "")
                ctx.add_file(path, content, f.get("language", "typescript"), "test")

        except Exception as e:
            self.logger.error(f"Failed to generate unit tests: {e}")

    def _generate_integration_tests(
        self, ctx: GenerationContext, spec, prefs
    ) -> None:
        """Generate integration tests for API endpoints."""
        if not spec or not spec.api_endpoints:
            return

        # Build detailed endpoint info
        endpoints_detail = []
        for e in spec.api_endpoints:
            auth = "Auth required" if e.auth_required else "Public"
            endpoints_detail.append(
                f"- {e.method} {e.path}: {e.description} ({auth})"
            )

        endpoints_text = "\n".join(endpoints_detail)

        # Get API route files for import context
        api_files = ctx.get_files_by_category("api")
        api_imports = "\n".join([f"- {f.path}" for f in api_files])

        user_prompt = f"""Generate integration tests for API endpoints.

## API Endpoints
{endpoints_text}

## API Route Files
{api_imports}

## Available Fixtures
{ctx.get_available_components(category="fixture")}

## Configuration
- DATABASE: {prefs.database_preference}
- AUTH: {prefs.auth_preference}

## Requirements

Generate JSON with integration test files:
{{
    "files": [
        {{
            "path": "__tests__/integration/users.test.ts",
            "language": "typescript",
            "content": "// Full integration test"
        }}
    ]
}}

Each integration test should:
1. Use fixtures for test data
2. Set up test database state before tests
3. Clean up after tests
4. Test authentication flows
5. Test happy path and error responses
6. Validate response schemas

Group related endpoints in the same test file.

{ctx.get_deduplication_instructions()}
"""

        try:
            result = llm.generate_json(TEST_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "__tests__/integration/test.ts")
                content = f.get("content", "")
                ctx.add_file(path, content, f.get("language", "typescript"), "test")

        except Exception as e:
            self.logger.error(f"Failed to generate integration tests: {e}")

    def _generate_e2e_tests(self, ctx: GenerationContext, opp, prefs) -> None:
        """Generate end-to-end test scenarios."""
        # Get frontend pages for test coverage
        frontend_files = ctx.get_files_by_category("frontend")
        pages_list = "\n".join([f"- {f.path}" for f in frontend_files])

        user_prompt = f"""Generate E2E tests using Playwright.

## Product
- NAME: {opp.name}
- DESCRIPTION: {opp.detailed_description}
- BUSINESS MODEL: {opp.business_model}

## Frontend Pages to Test
{pages_list if pages_list else "Standard SaaS pages (landing, auth, dashboard)"}

## Requirements

Generate JSON with E2E test files:
{{
    "files": [
        {{
            "path": "e2e/auth.spec.ts",
            "language": "typescript",
            "content": "// Playwright E2E test"
        }}
    ]
}}

Generate E2E tests for:
1. e2e/auth.spec.ts - Signup and login flows
2. e2e/dashboard.spec.ts - Main app functionality
3. e2e/settings.spec.ts - User settings
4. e2e/navigation.spec.ts - Site navigation and links

Each test should:
- Use Playwright best practices
- Include proper selectors (data-testid preferred)
- Handle loading states
- Take screenshots on failure
- Be independent (no test dependencies)

{ctx.get_deduplication_instructions()}
"""

        try:
            result = llm.generate_json(TEST_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "e2e/test.spec.ts")
                content = f.get("content", "")
                ctx.add_file(path, content, f.get("language", "typescript"), "test")

        except Exception as e:
            self.logger.error(f"Failed to generate E2E tests: {e}")

    def _generate_test_fixtures(
        self, ctx: GenerationContext, spec, source_files: list
    ) -> None:
        """Generate test fixtures and mock data."""
        # Build database table info
        tables_info = ""
        if spec and spec.database_schema:
            table_details = []
            for t in spec.database_schema:
                cols = [c.get("name", "?") for c in t.columns[:5]]
                table_details.append(f"- {t.name}: {', '.join(cols)}")
            tables_info = "\n".join(table_details)

        user_prompt = f"""Generate test fixtures and mock data.

## Database Tables
{tables_info if tables_info else "See migrations for schema"}

## Source Files Structure
{ctx.get_folder_structure()}

## Requirements

Generate JSON with fixture files:
{{
    "files": [
        {{
            "path": "__tests__/fixtures/users.ts",
            "language": "typescript",
            "content": "// Typed mock user data",
            "exports": ["mockUser", "mockUsers", "createMockUser"]
        }},
        {{
            "path": "__tests__/mocks/db.ts",
            "language": "typescript",
            "content": "// Database mocks",
            "exports": ["mockDb", "mockQuery"]
        }}
    ]
}}

Generate:
1. __tests__/fixtures/users.ts - Mock user data matching schema
2. __tests__/fixtures/[entity].ts - For each main database entity
3. __tests__/mocks/db.ts - Database client mock
4. __tests__/mocks/api.ts - External API mocks
5. __tests__/helpers.ts - Test helper utilities

Each fixture should:
- Have TypeScript types matching the actual schema
- Export factory functions for creating test data
- Include both single and list variants
- Be importable by unit and integration tests
"""

        try:
            result = llm.generate_json(TEST_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "__tests__/fixtures/data.ts")
                content = f.get("content", "")
                exports = f.get("exports", [])
                if not exports:
                    exports = ctx.extract_exports_from_typescript(content)

                ctx.add_file(path, content, f.get("language", "typescript"), "fixture", exports=exports)

        except Exception as e:
            self.logger.error(f"Failed to generate fixtures: {e}")

    def _push_tests_to_github(self, opp, tests: list[GeneratedFile]):
        """Push test files to GitHub repository."""
        try:
            file_data = [
                {"path": f.path, "content": f.content, "message": f"Add {f.path}"}
                for f in tests
            ]

            # Assume repo was created by CodeAgent
            github.create_files_batch("", opp.slug, file_data)

        except Exception as e:
            self.logger.error(f"Failed to push tests to GitHub: {e}")

    def _create_linear_issues(
        self, state: FactoryState, tests: list[GeneratedFile]
    ) -> list[str]:
        """Create Linear issues for test generation."""
        try:
            project = linear.get_project(state.handoff.linear_project_id)
            team_id = project.get("teams", {}).get("nodes", [{}])[0].get("id", "")

            if not team_id:
                return []

            issues = [
                {
                    "title": "[Build] Test Suite Generated",
                    "description": f"Generated {len(tests)} test files:\n\n"
                    + "\n".join([f"- `{t.path}`" for t in tests[:15]]),
                },
            ]

            return linear.create_issues_batch(
                state.handoff.linear_project_id, team_id, issues
            )

        except Exception as e:
            self.logger.error(f"Failed to create Linear issues: {e}")
            return []
