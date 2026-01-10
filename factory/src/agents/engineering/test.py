"""Test Agent - Test generation for code."""

from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import TEST_AGENT_PROMPT
from src.models import FactoryState, GeneratedFile
from src.tools import github, linear, llm


class TestAgent(BaseAgent):
    """Agent for generating tests."""

    name = "TestAgent"
    domain = "engineering"

    def run(self, state: FactoryState) -> dict[str, Any]:
        """
        Generate unit and integration tests.
        """
        self.log_start()

        opp = state.handoff.opportunity
        prefs = state.handoff.build_preferences
        spec = self.get_previous_output(state, "spec")
        build = self.get_previous_output(state, "build")

        files = build.get("files", []) if build else []

        # Generate unit tests
        unit_tests = self._generate_unit_tests(files, prefs)

        # Generate integration tests
        integration_tests = self._generate_integration_tests(spec, prefs)

        # Generate E2E test scenarios
        e2e_tests = self._generate_e2e_tests(opp, prefs)

        # Generate test fixtures
        fixtures = self._generate_test_fixtures(spec)

        # Combine all test files
        all_tests = unit_tests + integration_tests + e2e_tests + fixtures

        # Push to GitHub
        self._push_tests_to_github(opp, all_tests)

        # Create Linear issues
        linear_issues = self._create_linear_issues(state, all_tests)

        output = {
            "test_files": all_tests,
            "unit_test_count": len(unit_tests),
            "integration_test_count": len(integration_tests),
            "e2e_test_count": len(e2e_tests),
            "linear_issues": linear_issues,
        }

        self.log_complete()
        return output

    def _generate_unit_tests(
        self, source_files: list[GeneratedFile], prefs
    ) -> list[GeneratedFile]:
        """Generate unit tests for source files."""
        files_text = "\n".join(
            [f"- {f.path}" for f in source_files if f.language in ["typescript", "python"]][:10]
        )

        user_prompt = f"""Generate unit tests for these source files:

FILES:
{files_text}

TECH STACK: {prefs.tech_stack}

Generate JSON with test files:
{{
    "files": [
        {{
            "path": "__tests__/api/users.test.ts",
            "language": "typescript",
            "content": "// Unit tests with mocks"
        }}
    ]
}}

Use:
- Jest/Vitest for TypeScript
- Pytest for Python
- Proper mocking of dependencies
- Edge case coverage
- Descriptive test names
"""

        try:
            result = llm.generate_json(TEST_AGENT_PROMPT, user_prompt)
            files = []

            for f in result.get("files", []):
                files.append(
                    GeneratedFile(
                        path=f.get("path", "__tests__/test.ts"),
                        content=f.get("content", ""),
                        language=f.get("language", "typescript"),
                    )
                )

            return files

        except Exception as e:
            self.logger.error(f"Failed to generate unit tests: {e}")
            return []

    def _generate_integration_tests(self, spec, prefs) -> list[GeneratedFile]:
        """Generate integration tests for API endpoints."""
        if not spec or not spec.api_endpoints:
            return []

        endpoints_text = "\n".join(
            [f"- {e.method} {e.path}: {e.description}" for e in spec.api_endpoints[:10]]
        )

        user_prompt = f"""Generate integration tests for these API endpoints:

ENDPOINTS:
{endpoints_text}

DATABASE: {prefs.database_preference}
AUTH: {prefs.auth_preference}

Generate JSON with test files:
{{
    "files": [
        {{
            "path": "__tests__/integration/api.test.ts",
            "language": "typescript",
            "content": "// Integration tests with real DB"
        }}
    ]
}}

Include:
- Database setup/teardown
- Authentication testing
- Happy path and error cases
- Request/response validation
"""

        try:
            result = llm.generate_json(TEST_AGENT_PROMPT, user_prompt)
            files = []

            for f in result.get("files", []):
                files.append(
                    GeneratedFile(
                        path=f.get("path", "__tests__/integration/test.ts"),
                        content=f.get("content", ""),
                        language=f.get("language", "typescript"),
                    )
                )

            return files

        except Exception as e:
            self.logger.error(f"Failed to generate integration tests: {e}")
            return []

    def _generate_e2e_tests(self, opp, prefs) -> list[GeneratedFile]:
        """Generate end-to-end test scenarios."""
        user_prompt = f"""Generate E2E tests for this product:

PRODUCT: {opp.name}
DESCRIPTION: {opp.detailed_description}
BUSINESS MODEL: {opp.business_model}

Generate JSON with E2E test files (Playwright):
{{
    "files": [
        {{
            "path": "e2e/signup.spec.ts",
            "language": "typescript",
            "content": "// Playwright E2E test"
        }}
    ]
}}

Include E2E tests for:
- User signup flow
- User login flow
- Core feature usage
- Payment/upgrade flow
- Settings update
"""

        try:
            result = llm.generate_json(TEST_AGENT_PROMPT, user_prompt)
            files = []

            for f in result.get("files", []):
                files.append(
                    GeneratedFile(
                        path=f.get("path", "e2e/test.spec.ts"),
                        content=f.get("content", ""),
                        language=f.get("language", "typescript"),
                    )
                )

            return files

        except Exception as e:
            self.logger.error(f"Failed to generate E2E tests: {e}")
            return []

    def _generate_test_fixtures(self, spec) -> list[GeneratedFile]:
        """Generate test fixtures and mock data."""
        user_prompt = f"""Generate test fixtures and mock data.

DATABASE TABLES: {len(spec.database_schema) if spec else 0} tables

Generate JSON with fixture files:
{{
    "files": [
        {{
            "path": "__tests__/fixtures/users.ts",
            "language": "typescript",
            "content": "// Mock user data"
        }},
        {{
            "path": "__tests__/mocks/api.ts",
            "language": "typescript",
            "content": "// API mocks"
        }}
    ]
}}

Include:
- Sample user data
- Sample domain entities
- API response mocks
- Test utilities
"""

        try:
            result = llm.generate_json(TEST_AGENT_PROMPT, user_prompt)
            files = []

            for f in result.get("files", []):
                files.append(
                    GeneratedFile(
                        path=f.get("path", "__tests__/fixtures/data.ts"),
                        content=f.get("content", ""),
                        language=f.get("language", "typescript"),
                    )
                )

            return files

        except Exception as e:
            self.logger.error(f"Failed to generate fixtures: {e}")
            return []

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
