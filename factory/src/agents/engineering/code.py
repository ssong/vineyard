"""Code Agent - Code generation from specs."""

from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import CODE_AGENT_PROMPT
from src.models import (
    BuildOutput,
    FactoryState,
    GeneratedFile,
    SpecOutput,
)
from src.tools import github, linear, llm


class CodeAgent(BaseAgent):
    """Agent for generating application code."""

    name = "CodeAgent"
    domain = "engineering"

    def run(self, state: FactoryState) -> dict[str, Any]:
        """
        Generate code files from technical specifications.
        """
        self.log_start()

        opp = state.handoff.opportunity
        prefs = state.handoff.build_preferences
        spec = self.get_previous_output(state, "spec")

        # Generate project structure
        project_files = self._generate_project_structure(opp, prefs)

        # Generate database migrations
        migration_files = self._generate_migrations(spec)

        # Generate API routes
        api_files = self._generate_api_routes(spec, prefs)

        # Generate frontend pages
        frontend_files = self._generate_frontend_pages(opp, prefs)

        # Generate utility files
        util_files = self._generate_utilities(prefs)

        # Combine all files
        all_files = project_files + migration_files + api_files + frontend_files + util_files

        # Create GitHub repository
        repo_url = self._create_github_repo(opp, all_files)

        # Create Linear issues
        linear_issues = self._create_linear_issues(state, all_files)

        output = {
            "files": all_files,
            "github_repo_url": repo_url,
            "file_count": len(all_files),
            "linear_issues": linear_issues,
        }

        self.log_complete()
        return output

    def _generate_project_structure(self, opp, prefs) -> list[GeneratedFile]:
        """Generate basic project structure files."""
        frontend = prefs.tech_stack.get("frontend", "nextjs")
        backend = prefs.tech_stack.get("backend", "python")

        user_prompt = f"""Generate the project structure files for:

PRODUCT: {opp.name}
FRONTEND: {frontend}
BACKEND: {backend}
AUTH: {prefs.auth_preference}
PAYMENTS: {prefs.payments_preference}

Generate JSON with files:
{{
    "files": [
        {{
            "path": "package.json",
            "language": "json",
            "content": "..."
        }},
        {{
            "path": "tsconfig.json",
            "language": "json",
            "content": "..."
        }}
    ]
}}

Include:
- package.json or pyproject.toml
- TypeScript/linting config
- Environment example file
- README with setup instructions
- .gitignore
"""

        try:
            result = llm.generate_json(CODE_AGENT_PROMPT, user_prompt)
            files = []

            for f in result.get("files", []):
                files.append(
                    GeneratedFile(
                        path=f.get("path", "unknown"),
                        content=f.get("content", ""),
                        language=f.get("language", "text"),
                    )
                )

            return files

        except Exception as e:
            self.logger.error(f"Failed to generate project structure: {e}")
            return [
                GeneratedFile(
                    path="README.md",
                    content=f"# {opp.name}\n\n{opp.one_liner}",
                    language="markdown",
                )
            ]

    def _generate_migrations(self, spec: SpecOutput) -> list[GeneratedFile]:
        """Generate database migrations."""
        if not spec or not spec.database_schema:
            return []

        tables_text = "\n".join(
            [
                f"- {t.name}: {t.description} ({len(t.columns)} columns)"
                for t in spec.database_schema
            ]
        )

        user_prompt = f"""Generate database migration files for:

TABLES:
{tables_text}

SCHEMA DETAILS:
{spec.database_schema}

Generate JSON with migration files:
{{
    "files": [
        {{
            "path": "migrations/001_initial.sql",
            "language": "sql",
            "content": "-- Migration SQL here"
        }}
    ]
}}

Use PostgreSQL syntax. Include:
- Table creation with all columns
- Indexes
- Foreign key constraints
- Created_at/updated_at timestamps
"""

        try:
            result = llm.generate_json(CODE_AGENT_PROMPT, user_prompt)
            files = []

            for f in result.get("files", []):
                files.append(
                    GeneratedFile(
                        path=f.get("path", "migrations/001_migration.sql"),
                        content=f.get("content", ""),
                        language=f.get("language", "sql"),
                    )
                )

            return files

        except Exception as e:
            self.logger.error(f"Failed to generate migrations: {e}")
            return []

    def _generate_api_routes(self, spec: SpecOutput, prefs) -> list[GeneratedFile]:
        """Generate API route implementations."""
        if not spec or not spec.api_endpoints:
            return []

        endpoints_text = "\n".join(
            [
                f"- {e.method} {e.path}: {e.description}"
                for e in spec.api_endpoints[:10]
            ]
        )

        backend = prefs.tech_stack.get("backend", "python")

        user_prompt = f"""Generate API route implementations for:

BACKEND: {backend}
AUTH: {prefs.auth_preference}
ENDPOINTS:
{endpoints_text}

Generate JSON with route files:
{{
    "files": [
        {{
            "path": "app/api/users/route.ts",
            "language": "typescript",
            "content": "// Full implementation here"
        }}
    ]
}}

For each endpoint include:
- Request validation
- Authentication check
- Business logic
- Error handling
- Response formatting
"""

        try:
            result = llm.generate_json(CODE_AGENT_PROMPT, user_prompt)
            files = []

            for f in result.get("files", []):
                files.append(
                    GeneratedFile(
                        path=f.get("path", "api/route.ts"),
                        content=f.get("content", ""),
                        language=f.get("language", "typescript"),
                    )
                )

            return files

        except Exception as e:
            self.logger.error(f"Failed to generate API routes: {e}")
            return []

    def _generate_frontend_pages(self, opp, prefs) -> list[GeneratedFile]:
        """Generate frontend page components."""
        frontend = prefs.tech_stack.get("frontend", "nextjs")

        user_prompt = f"""Generate frontend pages for:

PRODUCT: {opp.name}
FRONTEND: {frontend}
AUTH: {prefs.auth_preference}
BUSINESS MODEL: {opp.business_model}

Generate JSON with page files:
{{
    "files": [
        {{
            "path": "app/page.tsx",
            "language": "typescript",
            "content": "// Landing page component"
        }},
        {{
            "path": "app/dashboard/page.tsx",
            "language": "typescript",
            "content": "// Dashboard component"
        }}
    ]
}}

Include pages for:
- Landing page (marketing)
- Sign up / Sign in
- Dashboard (main app)
- Settings
- Pricing page
"""

        try:
            result = llm.generate_json(CODE_AGENT_PROMPT, user_prompt)
            files = []

            for f in result.get("files", []):
                files.append(
                    GeneratedFile(
                        path=f.get("path", "app/page.tsx"),
                        content=f.get("content", ""),
                        language=f.get("language", "typescript"),
                    )
                )

            return files

        except Exception as e:
            self.logger.error(f"Failed to generate frontend pages: {e}")
            return []

    def _generate_utilities(self, prefs) -> list[GeneratedFile]:
        """Generate utility and helper files."""
        user_prompt = f"""Generate utility files for a web app:

AUTH: {prefs.auth_preference}
PAYMENTS: {prefs.payments_preference}
DATABASE: {prefs.database_preference}

Generate JSON with utility files:
{{
    "files": [
        {{
            "path": "lib/auth.ts",
            "language": "typescript",
            "content": "// Auth utility functions"
        }},
        {{
            "path": "lib/db.ts",
            "language": "typescript",
            "content": "// Database client setup"
        }}
    ]
}}

Include:
- Auth helper (session, user)
- Database client
- API client wrapper
- Environment validation
- Type definitions
"""

        try:
            result = llm.generate_json(CODE_AGENT_PROMPT, user_prompt)
            files = []

            for f in result.get("files", []):
                files.append(
                    GeneratedFile(
                        path=f.get("path", "lib/util.ts"),
                        content=f.get("content", ""),
                        language=f.get("language", "typescript"),
                    )
                )

            return files

        except Exception as e:
            self.logger.error(f"Failed to generate utilities: {e}")
            return []

    def _create_github_repo(self, opp, files: list[GeneratedFile]) -> str:
        """Create GitHub repository with generated files."""
        try:
            repo = github.create_repository(
                name=opp.slug,
                description=opp.one_liner,
                private=True,
            )

            if not repo:
                return ""

            owner = repo.get("owner", {}).get("login", "")
            repo_name = repo.get("name", opp.slug)

            # Create files in batches
            file_data = [
                {"path": f.path, "content": f.content, "message": f"Add {f.path}"}
                for f in files
            ]

            github.create_files_batch(owner, repo_name, file_data)

            return repo.get("html_url", "")

        except Exception as e:
            self.logger.error(f"Failed to create GitHub repo: {e}")
            return ""

    def _create_linear_issues(
        self, state: FactoryState, files: list[GeneratedFile]
    ) -> list[str]:
        """Create Linear issues for code generation."""
        try:
            project = linear.get_project(state.handoff.linear_project_id)
            team_id = project.get("teams", {}).get("nodes", [{}])[0].get("id", "")

            if not team_id:
                return []

            issues = [
                {
                    "title": "[Build] Code Generation Complete",
                    "description": f"Generated {len(files)} files:\n\n"
                    + "\n".join([f"- `{f.path}`" for f in files[:20]]),
                },
            ]

            return linear.create_issues_batch(
                state.handoff.linear_project_id, team_id, issues
            )

        except Exception as e:
            self.logger.error(f"Failed to create Linear issues: {e}")
            return []
