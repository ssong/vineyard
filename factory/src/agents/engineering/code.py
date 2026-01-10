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
from src.tools import github, llm
from src.tools.generation_context import GenerationContext


class CodeAgent(BaseAgent):
    """Agent for generating application code."""

    name = "CodeAgent"
    domain = "engineering"

    def run(self, state: FactoryState) -> dict[str, Any]:
        """
        Generate code files from technical specifications.

        Uses GenerationContext to:
        1. Track all generated files to prevent duplicates
        2. Pass folder structure context to each generation step
        3. Provide available components/utilities for imports
        """
        self.log_start()

        opp = state.handoff.opportunity
        prefs = state.handoff.build_preferences
        spec = self.get_previous_output(state, "spec")
        design = self.get_previous_output(state, "design")

        # Initialize generation context for tracking files
        ctx = GenerationContext()

        # Generate in order of dependencies:
        # 1. Project structure (no dependencies)
        # 2. Utilities (no dependencies, but needed by others)
        # 3. Database migrations (no dependencies)
        # 4. API routes (depends on utilities, migrations)
        # 5. Frontend pages (depends on utilities, API routes)
        # 6. Shared components (depends on utilities)

        self.logger.info("Generating project structure...")
        self._generate_project_structure(ctx, opp, prefs)

        self.logger.info("Generating utility files...")
        self._generate_utilities(ctx, prefs, spec)

        self.logger.info("Generating database migrations...")
        self._generate_migrations(ctx, spec)

        self.logger.info("Generating API routes...")
        self._generate_api_routes(ctx, spec, prefs)

        self.logger.info("Generating shared components...")
        self._generate_shared_components(ctx, opp, prefs, design)

        self.logger.info("Generating frontend pages...")
        self._generate_frontend_pages(ctx, opp, prefs, spec, design)

        # Convert context files to GeneratedFile list
        all_files = [
            GeneratedFile(
                path=entry.path,
                content=entry.content,
                language=entry.language,
            )
            for entry in ctx.get_all_files()
        ]

        self.logger.info(f"Generated {len(all_files)} unique files")

        # Create GitHub repository
        repo_url = self._create_github_repo(opp, all_files)

        # Note: Linear task tracking is now handled at the runner level
        # via upfront task creation and status updates

        output = {
            "files": all_files,
            "github_repo_url": repo_url,
            "file_count": len(all_files),
            "folder_structure": ctx.get_folder_structure(),
        }

        self.log_complete()
        return output

    def _generate_project_structure(
        self, ctx: GenerationContext, opp, prefs
    ) -> None:
        """Generate basic project structure files."""
        frontend = prefs.tech_stack.get("frontend", "nextjs")
        backend = prefs.tech_stack.get("backend", "python")

        user_prompt = f"""Generate the project structure files for:

PRODUCT: {opp.name}
DESCRIPTION: {opp.one_liner}
FRONTEND: {frontend}
BACKEND: {backend}
AUTH: {prefs.auth_preference}
PAYMENTS: {prefs.payments_preference}
HOSTING: {prefs.hosting_preference}
DATABASE: {prefs.database_preference}

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

Generate ONLY these configuration files:
- package.json (with appropriate dependencies for {frontend}, {prefs.auth_preference}, {prefs.payments_preference})
- tsconfig.json (if TypeScript)
- .env.example (with placeholder environment variables)
- README.md (setup instructions)
- .gitignore (appropriate for {frontend}/{backend})
- next.config.js or similar framework config

Do NOT generate:
- Source code files (those come later)
- Component files
- API route files
- Utility files
"""

        try:
            result = llm.generate_json(CODE_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "unknown")
                content = f.get("content", "")
                language = f.get("language", "text")

                ctx.add_file(path, content, language, "project")

        except Exception as e:
            self.logger.error(f"Failed to generate project structure: {e}")
            ctx.add_file(
                "README.md",
                f"# {opp.name}\n\n{opp.one_liner}",
                "markdown",
                "project",
            )

    def _generate_migrations(self, ctx: GenerationContext, spec: SpecOutput) -> None:
        """Generate database migrations."""
        if not spec or not spec.database_schema:
            return

        # Build detailed schema information
        schema_details = []
        for table in spec.database_schema:
            columns_info = []
            for col in table.columns:
                col_name = col.get("name", "unknown")
                col_type = col.get("type", "text")
                col_nullable = "NULL" if col.get("nullable", True) else "NOT NULL"
                columns_info.append(f"    - {col_name}: {col_type} {col_nullable}")

            schema_details.append(
                f"TABLE: {table.name}\n"
                f"  Description: {table.description}\n"
                f"  Columns:\n" + "\n".join(columns_info) + "\n"
                f"  Indexes: {', '.join(table.indexes) if table.indexes else 'none'}\n"
                f"  Relationships: {', '.join(table.relationships) if table.relationships else 'none'}"
            )

        schema_text = "\n\n".join(schema_details)

        user_prompt = f"""Generate database migration files for PostgreSQL.

## Database Schema

{schema_text}

## Requirements

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

Include in the migration:
- CREATE TABLE statements with all columns and proper types
- Primary keys (use UUID or SERIAL as appropriate)
- Foreign key constraints matching the relationships
- Indexes for frequently queried columns
- created_at and updated_at timestamps with defaults
- Proper NULL/NOT NULL constraints

Generate a SINGLE comprehensive migration file, not multiple files.
"""

        try:
            result = llm.generate_json(CODE_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "migrations/001_initial.sql")
                content = f.get("content", "")

                # Track table names as exports for context
                exports = ctx._extract_table_names(content)
                ctx.add_file(path, content, "sql", "migration", exports=exports)

        except Exception as e:
            self.logger.error(f"Failed to generate migrations: {e}")

    def _generate_api_routes(
        self, ctx: GenerationContext, spec: SpecOutput, prefs
    ) -> None:
        """Generate API route implementations."""
        if not spec or not spec.api_endpoints:
            return

        backend = prefs.tech_stack.get("backend", "python")
        frontend = prefs.tech_stack.get("frontend", "nextjs")

        # Build detailed endpoint specifications
        endpoints_detail = []
        for endpoint in spec.api_endpoints:
            req_schema = endpoint.request_schema if endpoint.request_schema else "{}"
            res_schema = endpoint.response_schema if endpoint.response_schema else "{}"
            auth = "Required" if endpoint.auth_required else "Public"

            endpoints_detail.append(
                f"### {endpoint.method} {endpoint.path}\n"
                f"Description: {endpoint.description}\n"
                f"Auth: {auth}\n"
                f"Request: {req_schema}\n"
                f"Response: {res_schema}"
            )

        endpoints_text = "\n\n".join(endpoints_detail)

        # Get available utilities for imports
        available_utils = ctx.get_available_components(category="utility")

        # Get database tables from migrations
        migration_files = ctx.get_files_by_category("migration")
        db_tables = []
        for mf in migration_files:
            db_tables.extend(ctx._extract_table_names(mf.content))

        user_prompt = f"""Generate API route implementations.

## Configuration
- FRAMEWORK: {frontend} (use App Router if Next.js)
- BACKEND: {backend}
- AUTH: {prefs.auth_preference}
- DATABASE: {prefs.database_preference}

## Current Project Structure
{ctx.get_folder_structure()}

## Available Utilities (IMPORT THESE, do not recreate)
{available_utils}

## Database Tables Available
{', '.join(db_tables) if db_tables else 'See migrations for schema'}

## API Endpoints to Implement

{endpoints_text}

## Requirements

Generate JSON with route files:
{{
    "files": [
        {{
            "path": "app/api/users/route.ts",
            "language": "typescript",
            "content": "// Full implementation",
            "exports": ["GET", "POST"]
        }}
    ]
}}

IMPORTANT:
1. Import utilities from lib/ - do NOT recreate auth, db, or other utilities
2. Each route file should handle all HTTP methods for that resource
3. Use the database client from lib/db.ts
4. Use auth utilities from lib/auth.ts
5. Follow {frontend} conventions for API routes
6. Include proper error handling and status codes
7. Validate request bodies before processing

{ctx.get_deduplication_instructions()}
"""

        try:
            result = llm.generate_json(CODE_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "app/api/route.ts")
                content = f.get("content", "")
                language = f.get("language", "typescript")

                exports = f.get("exports", [])
                if not exports:
                    exports = ctx.extract_exports_from_typescript(content)

                ctx.add_file(path, content, language, "api", exports=exports)

        except Exception as e:
            self.logger.error(f"Failed to generate API routes: {e}")

    def _generate_shared_components(
        self, ctx: GenerationContext, opp, prefs, design
    ) -> None:
        """Generate shared UI components that pages will use."""
        frontend = prefs.tech_stack.get("frontend", "nextjs")

        # Get features from design phase for context
        features_context = ""
        if design and hasattr(design, "features"):
            feature_names = [f.name for f in design.features[:5]]
            features_context = f"\nMain features: {', '.join(feature_names)}"

        user_prompt = f"""Generate shared UI components for a {frontend} app.

## Product
- NAME: {opp.name}
- DESCRIPTION: {opp.one_liner}
- BUSINESS MODEL: {opp.business_model}
{features_context}

## Current Project Structure
{ctx.get_folder_structure()}

## Available Utilities
{ctx.get_available_components(category="utility")}

## Requirements

Generate JSON with shared component files:
{{
    "files": [
        {{
            "path": "components/ui/Button.tsx",
            "language": "typescript",
            "content": "// Full implementation",
            "exports": ["Button", "ButtonProps"]
        }}
    ]
}}

Generate these shared components:
1. components/ui/Button.tsx - Reusable button with variants
2. components/ui/Input.tsx - Form input with validation display
3. components/ui/Card.tsx - Content card container
4. components/ui/Modal.tsx - Modal dialog component
5. components/layout/Header.tsx - App header with navigation
6. components/layout/Footer.tsx - App footer
7. components/layout/Sidebar.tsx - Dashboard sidebar (if applicable)

Each component MUST:
- Have TypeScript props interface
- Use named exports (not default exports)
- Be self-contained and reusable
- Import utilities from lib/ if needed

{ctx.get_deduplication_instructions()}
"""

        try:
            result = llm.generate_json(CODE_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "components/Component.tsx")
                content = f.get("content", "")
                language = f.get("language", "typescript")

                exports = f.get("exports", [])
                if not exports:
                    exports = ctx.extract_exports_from_typescript(content)

                ctx.add_file(path, content, language, "component", exports=exports)

        except Exception as e:
            self.logger.error(f"Failed to generate shared components: {e}")

    def _generate_frontend_pages(
        self, ctx: GenerationContext, opp, prefs, spec, design
    ) -> None:
        """Generate frontend page components."""
        frontend = prefs.tech_stack.get("frontend", "nextjs")

        # Get available components for imports
        available_components = ctx.get_available_components(for_import_from="app/page.tsx")

        # Get API routes for data fetching context
        api_files = ctx.get_files_by_category("api")
        api_routes = []
        for af in api_files:
            # Extract route path from file path
            route_path = af.path.replace("app/api", "/api").replace("/route.ts", "")
            api_routes.append(route_path)

        # Get features from design
        features_context = ""
        if design and hasattr(design, "features"):
            features_list = []
            for f in design.features[:8]:
                features_list.append(f"- {f.name}: {f.description[:100]}")
            features_context = "\n".join(features_list)

        user_prompt = f"""Generate frontend page components for a {frontend} app.

## Product
- NAME: {opp.name}
- DESCRIPTION: {opp.one_liner}
- BUSINESS MODEL: {opp.business_model}
- TARGET: {opp.target_segment}

## Features to Implement
{features_context if features_context else "Standard SaaS features"}

## Current Project Structure
{ctx.get_folder_structure()}

## Available Components (IMPORT THESE)
{available_components}

## Available API Routes
{chr(10).join('- ' + r for r in api_routes) if api_routes else "See app/api/ for routes"}

## Requirements

Generate JSON with page files:
{{
    "files": [
        {{
            "path": "app/page.tsx",
            "language": "typescript",
            "content": "// Full implementation",
            "exports": ["default"]
        }}
    ]
}}

Generate these pages:
1. app/page.tsx - Landing page (marketing, hero, features, CTA)
2. app/(auth)/login/page.tsx - Sign in page
3. app/(auth)/signup/page.tsx - Sign up page
4. app/dashboard/page.tsx - Main dashboard (protected)
5. app/dashboard/settings/page.tsx - User settings
6. app/pricing/page.tsx - Pricing page with tiers

IMPORTANT:
1. Import shared components from components/ - do NOT recreate them
2. Import utilities from lib/ - do NOT recreate them
3. Use the API routes for data fetching where appropriate
4. Follow {frontend} App Router conventions
5. Include proper TypeScript types
6. Add loading and error states where appropriate

{ctx.get_deduplication_instructions()}
"""

        try:
            result = llm.generate_json(CODE_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "app/page.tsx")
                content = f.get("content", "")
                language = f.get("language", "typescript")

                exports = f.get("exports", [])
                if not exports:
                    exports = ctx.extract_exports_from_typescript(content)

                ctx.add_file(path, content, language, "frontend", exports=exports)

        except Exception as e:
            self.logger.error(f"Failed to generate frontend pages: {e}")

    def _generate_utilities(
        self, ctx: GenerationContext, prefs, spec: SpecOutput
    ) -> None:
        """Generate utility and helper files."""
        # Build database context if available
        db_context = ""
        if spec and spec.database_schema:
            table_names = [t.name for t in spec.database_schema]
            db_context = f"\nDatabase tables: {', '.join(table_names)}"

        user_prompt = f"""Generate utility/library files for a web app.

## Configuration
- AUTH: {prefs.auth_preference}
- PAYMENTS: {prefs.payments_preference}
- DATABASE: {prefs.database_preference}
- FRONTEND: {prefs.tech_stack.get("frontend", "nextjs")}
{db_context}

## Current Project Structure
{ctx.get_folder_structure()}

## Requirements

Generate JSON with utility files that will be IMPORTED by other parts of the app:
{{
    "files": [
        {{
            "path": "lib/auth.ts",
            "language": "typescript",
            "content": "// Full implementation",
            "exports": ["getCurrentUser", "requireAuth", "signOut"]
        }},
        {{
            "path": "lib/db.ts",
            "language": "typescript",
            "content": "// Full implementation",
            "exports": ["db", "query"]
        }}
    ]
}}

Generate these utility files:
1. lib/auth.ts - Auth utilities for {prefs.auth_preference}
   - getCurrentUser(): Get current authenticated user
   - requireAuth(): Middleware/guard for protected routes
   - signOut(): Sign out utility

2. lib/db.ts - Database client for {prefs.database_preference}
   - db: Database client instance
   - query(): Helper for raw queries if needed

3. lib/api.ts - API client wrapper
   - api: Fetch wrapper with error handling
   - Typed request/response helpers

4. lib/env.ts - Environment validation
   - Validate required env vars
   - Typed env object

5. lib/utils.ts - Common utilities
   - formatDate, formatCurrency, cn (classnames), etc.

Each file must have named exports that other files can import.
Do NOT create files that already exist in the project structure above.
"""

        try:
            result = llm.generate_json(CODE_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "lib/util.ts")
                content = f.get("content", "")
                language = f.get("language", "typescript")

                # Extract exports from content or use provided exports
                exports = f.get("exports", [])
                if not exports:
                    exports = ctx.extract_exports_from_typescript(content)

                ctx.add_file(path, content, language, "utility", exports=exports)

        except Exception as e:
            self.logger.error(f"Failed to generate utilities: {e}")

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

