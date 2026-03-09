"""Code Agent - Rails code generation from specs.

Supports two modes:
1. Agent SDK mode: Claude autonomously generates files using tools (higher quality)
2. Direct API mode: Sequential generate_json calls (fallback)
"""

import logging
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

logger = logging.getLogger(__name__)


class CodeAgent(BaseAgent):
    """Agent for generating Ruby on Rails application code."""

    name = "CodeAgent"
    domain = "engineering"

    def run(self, state: FactoryState) -> dict[str, Any]:
        """
        Generate Rails code files from technical specifications.

        Uses Agent SDK when available for iterative, self-reviewing code generation.
        Falls back to sequential generate_json calls otherwise.
        """
        self.log_start()

        # Initialize subtask tracking
        self.init_subtask_tracking(state, parent_phase="build")

        prd_input = state.handoff.prd_input
        prefs = state.handoff.build_preferences
        spec = self.get_previous_output(state, "spec")
        design = self.get_previous_output(state, "design")

        try:
            # Try Agent SDK mode first
            from src.tools.agent_runner import is_sdk_available
            if is_sdk_available():
                self.logger.info("Using Agent SDK for code generation")
                output = self._run_with_agent_sdk(state, prd_input, prefs, spec, design)
            else:
                self.logger.info("Using direct API for code generation")
                output = self._run_direct(state, prd_input, prefs, spec, design)

            # Complete agent task
            file_count = output.get("file_count", 0)
            self.complete_agent_task(
                f"Generated {file_count} files for {prd_input.name}",
                [output.get("github_repo_url", "")] if output.get("github_repo_url") else None,
            )

            self.log_complete()
            return output

        except Exception as e:
            self.fail_agent_task(str(e))
            raise

    # =========================================================================
    # Agent SDK Mode
    # =========================================================================

    def _run_with_agent_sdk(self, state, prd_input, prefs, spec, design) -> dict[str, Any]:
        """Generate code using the Agent SDK with custom tools.

        Claude gets tools to write files, read specs, and review its own output.
        This produces higher quality code because Claude can:
        - See the full spec and design before generating
        - Review previously generated files for consistency
        - Iterate on files that reference each other
        """
        from src.tools import agent_tools
        from src.tools.agent_runner import run_agent

        # Reset tool state and set context
        agent_tools.reset_state()
        agent_tools.set_context(
            spec=spec,
            design=design,
            prd_input=prd_input,
            build_prefs=prefs,
        )

        # Get custom tools
        tools = agent_tools.get_code_gen_tools()

        # Build the generation prompt
        prompt = self._build_agent_prompt(prd_input, prefs, spec, design)

        # Run the agent
        result = run_agent(
            prompt=prompt,
            system_prompt=CODE_AGENT_PROMPT,
            tools=tools,
            model="sonnet",
            max_turns=30,
            max_budget_usd=2.0,
        )

        self.logger.info(f"Agent SDK completed in {result.turns} turns, cost: ${result.cost_usd:.4f}")

        # Collect generated files
        files_dict = agent_tools.get_generated_files()
        all_files = [
            GeneratedFile(
                path=path,
                content=info["content"],
                language=info["language"],
            )
            for path, info in files_dict.items()
        ]

        self.logger.info(f"Agent generated {len(all_files)} unique files")

        # Create GitHub repository
        repo_info = self._create_github_repo(prd_input, all_files)

        return {
            "files": all_files,
            "github_repo_url": repo_info.get("url", ""),
            "github_owner": repo_info.get("owner", ""),
            "github_repo_name": repo_info.get("name", ""),
            "file_count": len(all_files),
            "generation_mode": "agent_sdk",
            "agent_turns": result.turns,
            "agent_cost_usd": result.cost_usd,
        }

    def _build_agent_prompt(self, prd_input, prefs, spec, design) -> str:
        """Build the prompt for the Agent SDK code generation."""
        spec_summary = ""
        if spec:
            if hasattr(spec, "api_endpoints") and spec.api_endpoints:
                endpoints = [f"  - {e.method} {e.path}: {e.description}" for e in spec.api_endpoints[:10]]
                spec_summary += "API Endpoints:\n" + "\n".join(endpoints) + "\n\n"
            if hasattr(spec, "database_schema") and spec.database_schema:
                tables = [f"  - {t.name}: {t.description}" for t in spec.database_schema[:10]]
                spec_summary += "Database Tables:\n" + "\n".join(tables) + "\n\n"

        design_summary = ""
        if design and hasattr(design, "features"):
            features = [f"  - {f.name} ({f.priority}): {f.description[:80]}" for f in design.features[:8]]
            design_summary = "Features:\n" + "\n".join(features) + "\n\n"

        return f"""Generate a complete Ruby on Rails 7.1 application for the following product.

## Product
- **Name**: {prd_input.name}
- **Description**: {prd_input.prd_text[:1000]}

## Tech Stack
- **Framework**: Ruby on Rails 7.1
- **Auth**: {prefs.auth_preference}
- **Payments**: {prefs.payments_preference}
- **Hosting**: {prefs.hosting_preference}
- **Database**: {prefs.database_preference}

## Specification Summary
{spec_summary if spec_summary else "(Use get_spec tool for full specification)"}

## Design Summary
{design_summary if design_summary else "(Use get_design tool for full design)"}

## Instructions

1. First, use `get_spec` and `get_design` to read the full technical specification and design
2. Generate files in dependency order:
   a. Project config (Gemfile, database.yml, routes.rb, initializers)
   b. Models and migrations (based on database schema)
   c. Service objects and jobs
   d. Controllers (based on API endpoints)
   e. ViewComponents (reusable UI components with Tailwind)
   f. Views and layouts (using Hotwire, Turbo, Stimulus)
3. After generating each batch, use `list_generated_files` to review what you've created
4. Use `read_generated_file` to verify consistency between related files (e.g., model associations match migration foreign keys)
5. Use `write_file` for every file you generate

Generate production-ready, complete files. Include:
- Proper ActiveRecord associations and validations
- Strong parameters in controllers
- Turbo Frame/Stream responses
- Stimulus controllers for interactivity
- ViewComponent classes with Tailwind styling
- RSpec-ready structure

Generate ALL files needed for a working Rails application. Be thorough."""

    # =========================================================================
    # Direct API Mode (fallback)
    # =========================================================================

    def _run_direct(self, state, prd_input, prefs, spec, design) -> dict[str, Any]:
        """Generate code using direct API calls (original approach)."""
        ctx = GenerationContext()

        # Generate in order of dependencies with subtask tracking
        self.run_step(
            "project_structure",
            "Generate project structure",
            lambda: self._generate_project_structure(ctx, prd_input, prefs),
            "Gemfile, configs, initializers",
        )

        self.run_step(
            "models_migrations",
            "Generate models and migrations",
            lambda: self._generate_models_and_migrations(ctx, spec, prefs),
            "ActiveRecord models, database migrations",
        )

        self.run_step(
            "services",
            "Generate service objects",
            lambda: self._generate_services(ctx, prefs, spec),
            "Business logic, jobs, mailers",
        )

        self.run_step(
            "controllers",
            "Generate controllers",
            lambda: self._generate_controllers(ctx, spec, prefs),
            "Application and API controllers",
        )

        self.run_step(
            "view_components",
            "Generate ViewComponents",
            lambda: self._generate_view_components(ctx, prd_input, prefs, design),
            "Reusable UI components",
        )

        self.run_step(
            "views",
            "Generate views and layouts",
            lambda: self._generate_views(ctx, prd_input, prefs, spec, design),
            "ERB templates, Stimulus controllers",
        )

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
        repo_info = self.run_step(
            "github_repo",
            "Create GitHub repository",
            lambda: self._create_github_repo(prd_input, all_files),
            "Push code to GitHub",
        )

        return {
            "files": all_files,
            "github_repo_url": repo_info.get("url", ""),
            "github_owner": repo_info.get("owner", ""),
            "github_repo_name": repo_info.get("name", ""),
            "file_count": len(all_files),
            "folder_structure": ctx.get_folder_structure(),
            "generation_mode": "direct_api",
        }

    # =========================================================================
    # Direct API generation methods (unchanged from original)
    # =========================================================================

    def _generate_project_structure(
        self, ctx: GenerationContext, prd_input, prefs
    ) -> None:
        """Generate Rails project structure files."""
        user_prompt = f"""Generate the Rails project structure files for:

PRODUCT: {prd_input.name}
DESCRIPTION: {prd_input.prd_text[:500]}
FRAMEWORK: Ruby on Rails 7.1
AUTH: {prefs.auth_preference}
PAYMENTS: {prefs.payments_preference}
HOSTING: {prefs.hosting_preference}
DATABASE: {prefs.database_preference}

Generate JSON with files:
{{
    "files": [
        {{
            "path": "Gemfile",
            "language": "ruby",
            "content": "..."
        }},
        {{
            "path": "config/database.yml",
            "language": "yaml",
            "content": "..."
        }}
    ]
}}

Generate ONLY these configuration files:
1. Gemfile - with gems for Rails 7.1, {prefs.auth_preference}, {prefs.payments_preference}, Hotwire, ViewComponent, Sidekiq, RSpec
2. config/database.yml - PostgreSQL configuration for development/test/production
3. config/routes.rb - Basic route structure with health check, devise, and namespaced API
4. config/application.rb - Rails application config
5. config/environments/production.rb - Production settings
6. config/initializers/devise.rb - Devise configuration (if using devise)
7. config/initializers/stripe.rb - Stripe/pay configuration
8. config/initializers/sidekiq.rb - Sidekiq configuration
9. .env.example - Environment variable template
10. Procfile - Railway/Heroku process configuration
11. railway.json - Railway deployment config
12. README.md - Setup instructions
13. .gitignore - Rails gitignore
14. .rubocop.yml - RuboCop configuration

Do NOT generate:
- Model files (those come in migrations phase)
- Controller files (those come later)
- View files (those come later)
- Service files (those come later)
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
                f"# {prd_input.name}\n\n{prd_input.prd_text[:200]}",
                "markdown",
                "project",
            )

    def _generate_models_and_migrations(
        self, ctx: GenerationContext, spec: SpecOutput, prefs
    ) -> None:
        """Generate ActiveRecord models and migrations."""
        if not spec or not spec.database_schema:
            return

        schema_details = []
        for table in spec.database_schema:
            columns_info = []
            for col in table.columns:
                col_name = col.get("name", "unknown")
                col_type = col.get("type", "string")
                col_nullable = "optional" if col.get("nullable", True) else "required"
                columns_info.append(f"    - {col_name}: {col_type} ({col_nullable})")

            schema_details.append(
                f"TABLE: {table.name}\n"
                f"  Description: {table.description}\n"
                f"  Columns:\n" + "\n".join(columns_info) + "\n"
                f"  Indexes: {', '.join(table.indexes) if table.indexes else 'none'}\n"
                f"  Relationships: {', '.join(table.relationships) if table.relationships else 'none'}"
            )

        schema_text = "\n\n".join(schema_details)

        user_prompt = f"""Generate ActiveRecord models and migrations for Rails 7.1.

## Database Schema

{schema_text}

## Auth Configuration
AUTH: {prefs.auth_preference}

## Requirements

Generate JSON with model and migration files:
{{
    "files": [
        {{
            "path": "db/migrate/20240101000001_create_users.rb",
            "language": "ruby",
            "content": "class CreateUsers < ActiveRecord::Migration[7.1]..."
        }},
        {{
            "path": "app/models/user.rb",
            "language": "ruby",
            "content": "class User < ApplicationRecord..."
        }}
    ]
}}

For each table, generate:
1. A migration file in db/migrate/ with proper timestamp prefix
2. A model file in app/models/ with associations, validations, and scopes

Generate migrations in dependency order (referenced tables first).
"""

        try:
            result = llm.generate_json(CODE_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "db/migrate/migration.rb")
                content = f.get("content", "")
                language = f.get("language", "ruby")

                if "migrate" in path:
                    category = "migration"
                    exports = ctx._extract_table_names(content)
                else:
                    category = "model"
                    exports = ctx.extract_exports_from_ruby(content)

                ctx.add_file(path, content, language, category, exports=exports)

        except Exception as e:
            self.logger.error(f"Failed to generate models/migrations: {e}")

    def _generate_controllers(
        self, ctx: GenerationContext, spec: SpecOutput, prefs
    ) -> None:
        """Generate Rails controllers."""
        if not spec or not spec.api_endpoints:
            return

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

        model_files = ctx.get_files_by_category("model")
        model_names = []
        for mf in model_files:
            model_names.extend(mf.exports)

        service_exports = ctx.get_available_components(category="service")

        user_prompt = f"""Generate Rails controllers for the API endpoints.

## Configuration
- FRAMEWORK: Rails 7.1
- AUTH: {prefs.auth_preference}
- DATABASE: PostgreSQL with ActiveRecord

## Current Project Structure
{ctx.get_folder_structure()}

## Available Models
{', '.join(model_names) if model_names else 'See app/models/ for available models'}

## Available Services
{service_exports}

## API Endpoints to Implement

{endpoints_text}

## Requirements

Generate JSON with controller files:
{{
    "files": [
        {{
            "path": "app/controllers/resources_controller.rb",
            "language": "ruby",
            "content": "class ResourcesController < ApplicationController...",
            "exports": ["ResourcesController"]
        }}
    ]
}}

Generate controllers with full CRUD, strong parameters, Turbo Stream responses, and error handling.

{ctx.get_deduplication_instructions()}
"""

        try:
            result = llm.generate_json(CODE_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "app/controllers/application_controller.rb")
                content = f.get("content", "")
                language = f.get("language", "ruby")

                exports = f.get("exports", [])
                if not exports:
                    exports = ctx.extract_exports_from_ruby(content)

                if "api/" in path:
                    category = "api"
                else:
                    category = "controller"

                ctx.add_file(path, content, language, category, exports=exports)

        except Exception as e:
            self.logger.error(f"Failed to generate controllers: {e}")

    def _generate_view_components(
        self, ctx: GenerationContext, prd_input, prefs, design
    ) -> None:
        """Generate ViewComponent classes for reusable UI."""
        features_context = ""
        if design and hasattr(design, "features"):
            feature_names = [f.name for f in design.features[:5]]
            features_context = f"\nMain features: {', '.join(feature_names)}"

        user_prompt = f"""Generate ViewComponent classes for a Rails 7.1 app with Tailwind CSS.

## Product
- NAME: {prd_input.name}
- PRD: {prd_input.prd_text[:500]}
{features_context}

## Current Project Structure
{ctx.get_folder_structure()}

## Requirements

Generate JSON with ViewComponent files (Ruby class + ERB template):
{{
    "files": [
        {{
            "path": "app/components/button_component.rb",
            "language": "ruby",
            "content": "class ButtonComponent < ViewComponent::Base...",
            "exports": ["ButtonComponent"]
        }},
        {{
            "path": "app/components/button_component.html.erb",
            "language": "erb",
            "content": "<button class=\\"...\\">..."
        }}
    ]
}}

Generate these ViewComponents (each has .rb + .html.erb):
1. ButtonComponent - variants: primary, secondary, danger; sizes: sm, md, lg
2. CardComponent - container with optional header, body, footer slots
3. ModalComponent - dialog with Stimulus controller integration
4. FormFieldComponent - input wrapper with label and error display
5. AlertComponent - flash message display with variants
6. AvatarComponent - user avatar with initials fallback
7. BadgeComponent - status badges with color variants
8. NavLinkComponent - navigation link with active state
9. DropdownComponent - dropdown menu with Stimulus controller
10. PaginationComponent - Pagy-compatible pagination

{ctx.get_deduplication_instructions()}
"""

        try:
            result = llm.generate_json(CODE_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "app/components/component.rb")
                content = f.get("content", "")
                language = f.get("language", "ruby")

                exports = f.get("exports", [])
                if not exports and language == "ruby":
                    exports = ctx.extract_exports_from_ruby(content)

                ctx.add_file(path, content, language, "component", exports=exports)

        except Exception as e:
            self.logger.error(f"Failed to generate ViewComponents: {e}")

    def _generate_views(
        self, ctx: GenerationContext, prd_input, prefs, spec, design
    ) -> None:
        """Generate Rails views and layouts."""
        component_files = ctx.get_files_by_category("component")
        component_names = []
        for cf in component_files:
            component_names.extend(cf.exports)

        features_context = ""
        if design and hasattr(design, "features"):
            features_list = []
            for f in design.features[:8]:
                features_list.append(f"- {f.name}: {f.description[:100]}")
            features_context = "\n".join(features_list)

        user_prompt = f"""Generate Rails views and layouts with Hotwire (Turbo + Stimulus).

## Product
- NAME: {prd_input.name}
- PRD: {prd_input.prd_text[:500]}

## Features to Implement
{features_context if features_context else "Standard SaaS features"}

## Current Project Structure
{ctx.get_folder_structure()}

## Available ViewComponents (use these!)
{', '.join(component_names) if component_names else 'See app/components/'}

## Requirements

Generate JSON with view files:
{{
    "files": [
        {{
            "path": "app/views/layouts/application.html.erb",
            "language": "erb",
            "content": "<!DOCTYPE html>..."
        }}
    ]
}}

Generate layouts, marketing pages, auth views, app views, and Stimulus controllers.
Use ViewComponents, Turbo Frames/Streams, and Tailwind CSS.

{ctx.get_deduplication_instructions()}
"""

        try:
            result = llm.generate_json(CODE_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "app/views/view.html.erb")
                content = f.get("content", "")
                language = f.get("language", "erb")

                if "layouts" in path:
                    category = "layout"
                elif "javascript/controllers" in path:
                    category = "stimulus"
                else:
                    category = "view"

                ctx.add_file(path, content, language, category)

        except Exception as e:
            self.logger.error(f"Failed to generate views: {e}")

    def _generate_services(
        self, ctx: GenerationContext, prefs, spec: SpecOutput
    ) -> None:
        """Generate service objects for business logic."""
        db_context = ""
        if spec and spec.database_schema:
            table_names = [t.name for t in spec.database_schema]
            db_context = f"\nDatabase tables: {', '.join(table_names)}"

        user_prompt = f"""Generate service objects for a Rails 7.1 app.

## Configuration
- AUTH: {prefs.auth_preference}
- PAYMENTS: {prefs.payments_preference}
- DATABASE: PostgreSQL
{db_context}

## Current Project Structure
{ctx.get_folder_structure()}

## Requirements

Generate JSON with service files:
{{
    "files": [
        {{
            "path": "app/services/base_service.rb",
            "language": "ruby",
            "content": "class BaseService...",
            "exports": ["BaseService"]
        }}
    ]
}}

Generate: BaseService, Stripe services, user services, jobs, and mailers.
Use service object pattern with call class method and Result objects.
"""

        try:
            result = llm.generate_json(CODE_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "app/services/service.rb")
                content = f.get("content", "")
                language = f.get("language", "ruby")

                exports = f.get("exports", [])
                if not exports:
                    exports = ctx.extract_exports_from_ruby(content)

                if "jobs" in path:
                    category = "job"
                elif "mailers" in path:
                    category = "mailer"
                else:
                    category = "service"

                ctx.add_file(path, content, language, category, exports=exports)

        except Exception as e:
            self.logger.error(f"Failed to generate services: {e}")

    # =========================================================================
    # Shared methods
    # =========================================================================

    def _create_github_repo(self, prd_input, files: list[GeneratedFile]) -> dict[str, str]:
        """Create GitHub repository with generated files."""
        try:
            repo = github.create_repository(
                name=prd_input.slug,
                description=prd_input.prd_text[:200],
                private=True,
            )

            if not repo:
                return {"owner": "", "name": "", "url": ""}

            owner = repo.get("owner", {}).get("login", "")
            repo_name = repo.get("name", prd_input.slug)

            file_data = [
                {"path": f.path, "content": f.content, "message": f"Add {f.path}"}
                for f in files
            ]

            github.create_files_batch(owner, repo_name, file_data)

            return {
                "owner": owner,
                "name": repo_name,
                "url": repo.get("html_url", ""),
            }

        except Exception as e:
            self.logger.error(f"Failed to create GitHub repo: {e}")
            return {"owner": "", "name": "", "url": ""}
