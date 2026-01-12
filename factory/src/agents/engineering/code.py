"""Code Agent - Rails code generation from specs."""

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
    """Agent for generating Ruby on Rails application code."""

    name = "CodeAgent"
    domain = "engineering"

    def run(self, state: FactoryState) -> dict[str, Any]:
        """
        Generate Rails code files from technical specifications.

        Uses GenerationContext to:
        1. Track all generated files to prevent duplicates
        2. Pass folder structure context to each generation step
        3. Provide available components/utilities for imports
        """
        self.log_start()

        # Initialize subtask tracking
        self.init_subtask_tracking(state, parent_phase="build")

        opp = state.handoff.opportunity
        prefs = state.handoff.build_preferences
        spec = self.get_previous_output(state, "spec")
        design = self.get_previous_output(state, "design")

        # Initialize generation context for tracking files
        ctx = GenerationContext()

        try:
            # Generate in order of dependencies with subtask tracking
            self.run_step(
                "project_structure",
                "Generate project structure",
                lambda: self._generate_project_structure(ctx, opp, prefs),
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
                lambda: self._generate_view_components(ctx, opp, prefs, design),
                "Reusable UI components",
            )

            self.run_step(
                "views",
                "Generate views and layouts",
                lambda: self._generate_views(ctx, opp, prefs, spec, design),
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
                lambda: self._create_github_repo(opp, all_files),
                "Push code to GitHub",
            )

            output = {
                "files": all_files,
                "github_repo_url": repo_info.get("url", ""),
                "github_owner": repo_info.get("owner", ""),
                "github_repo_name": repo_info.get("name", ""),
                "file_count": len(all_files),
                "folder_structure": ctx.get_folder_structure(),
            }

            # Complete agent task
            self.complete_agent_task(
                f"Generated {len(all_files)} files for {opp.name}",
                [repo_info.get("url", "")] if repo_info.get("url") else None,
            )

            self.log_complete()
            return output

        except Exception as e:
            self.fail_agent_task(str(e))
            raise

    def _generate_project_structure(
        self, ctx: GenerationContext, opp, prefs
    ) -> None:
        """Generate Rails project structure files."""
        user_prompt = f"""Generate the Rails project structure files for:

PRODUCT: {opp.name}
DESCRIPTION: {opp.one_liner}
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
                f"# {opp.name}\n\n{opp.one_liner}",
                "markdown",
                "project",
            )

    def _generate_models_and_migrations(
        self, ctx: GenerationContext, spec: SpecOutput, prefs
    ) -> None:
        """Generate ActiveRecord models and migrations."""
        if not spec or not spec.database_schema:
            return

        # Build detailed schema information
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
2. A model file in app/models/ with:
   - belongs_to/has_many associations matching relationships
   - validates statements for required fields
   - scopes for common queries
   - Any computed methods

Migration requirements:
- Use Rails 7.1 migration syntax
- Include proper indexes for foreign keys and commonly queried columns
- Use t.timestamps for created_at/updated_at
- Use t.references for foreign keys with foreign_key: true

Model requirements:
- User model should include Devise modules if auth is devise
- Include association declarations (belongs_to, has_many, has_one)
- Add presence validations for NOT NULL columns
- Add useful scopes

Generate migrations in dependency order (referenced tables first).
"""

        try:
            result = llm.generate_json(CODE_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "db/migrate/migration.rb")
                content = f.get("content", "")
                language = f.get("language", "ruby")

                # Determine category based on path
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

        # Get available models for controller context
        model_files = ctx.get_files_by_category("model")
        model_names = []
        for mf in model_files:
            model_names.extend(mf.exports)

        # Get available services
        service_files = ctx.get_files_by_category("service")
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
        }},
        {{
            "path": "app/controllers/api/v1/resources_controller.rb",
            "language": "ruby",
            "content": "module Api\\n  module V1...",
            "exports": ["Api::V1::ResourcesController"]
        }}
    ]
}}

Generate these controllers:

1. ApplicationController - base controller with:
   - Devise authentication helpers
   - Common before_actions
   - Error handling

2. PagesController - static marketing pages (home, pricing, about)

3. DashboardController - authenticated dashboard

4. SettingsController - user settings

5. API::V1::BaseController - API base with:
   - Skip CSRF for API
   - Token authentication
   - JSON responses

6. Resource controllers for each main model with:
   - Full CRUD actions
   - Strong parameters
   - Turbo Stream responses for HTML
   - JSON responses for API

7. Webhooks::StripeController - Stripe webhook handler

Controller requirements:
- Use before_action :authenticate_user! for protected routes
- Use respond_to blocks for Turbo/HTML/JSON
- Include proper strong parameters
- Use service objects for complex business logic
- Handle errors gracefully

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

                # Categorize as api or controller
                if "api/" in path:
                    category = "api"
                else:
                    category = "controller"

                ctx.add_file(path, content, language, category, exports=exports)

        except Exception as e:
            self.logger.error(f"Failed to generate controllers: {e}")

    def _generate_view_components(
        self, ctx: GenerationContext, opp, prefs, design
    ) -> None:
        """Generate ViewComponent classes for reusable UI."""
        # Get features from design phase for context
        features_context = ""
        if design and hasattr(design, "features"):
            feature_names = [f.name for f in design.features[:5]]
            features_context = f"\nMain features: {', '.join(feature_names)}"

        user_prompt = f"""Generate ViewComponent classes for a Rails 7.1 app with Tailwind CSS.

## Product
- NAME: {opp.name}
- DESCRIPTION: {opp.one_liner}
- BUSINESS MODEL: {opp.business_model}
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
5. AlertComponent - flash message display with variants: info, success, warning, error
6. AvatarComponent - user avatar with initials fallback
7. BadgeComponent - status badges with color variants
8. NavLinkComponent - navigation link with active state
9. DropdownComponent - dropdown menu with Stimulus controller
10. PaginationComponent - Pagy-compatible pagination

Each component MUST:
- Inherit from ViewComponent::Base
- Use Tailwind CSS classes
- Accept configuration via initialize parameters
- Use slots for flexible content areas where appropriate
- Be fully self-contained

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
        self, ctx: GenerationContext, opp, prefs, spec, design
    ) -> None:
        """Generate Rails views and layouts."""
        # Get available components for imports
        component_files = ctx.get_files_by_category("component")
        component_names = []
        for cf in component_files:
            component_names.extend(cf.exports)

        # Get controllers for view structure context
        controller_files = ctx.get_files_by_category("controller")

        # Get features from design
        features_context = ""
        if design and hasattr(design, "features"):
            features_list = []
            for f in design.features[:8]:
                features_list.append(f"- {f.name}: {f.description[:100]}")
            features_context = "\n".join(features_list)

        user_prompt = f"""Generate Rails views and layouts with Hotwire (Turbo + Stimulus).

## Product
- NAME: {opp.name}
- DESCRIPTION: {opp.one_liner}
- BUSINESS MODEL: {opp.business_model}
- TARGET: {opp.target_segment}

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
        }},
        {{
            "path": "app/views/pages/home.html.erb",
            "language": "erb",
            "content": "..."
        }}
    ]
}}

Generate these views:

LAYOUTS:
1. app/views/layouts/application.html.erb - Main app layout with Turbo/Stimulus
2. app/views/layouts/marketing.html.erb - Public pages layout
3. app/views/layouts/_navbar.html.erb - Navigation partial
4. app/views/layouts/_footer.html.erb - Footer partial
5. app/views/layouts/_flash.html.erb - Flash messages partial

MARKETING PAGES:
6. app/views/pages/home.html.erb - Landing page with hero, features, CTA
7. app/views/pages/pricing.html.erb - Pricing tiers
8. app/views/pages/about.html.erb - About page

AUTH VIEWS (Devise):
9. app/views/devise/sessions/new.html.erb - Login
10. app/views/devise/registrations/new.html.erb - Signup
11. app/views/devise/registrations/edit.html.erb - Edit profile

APP VIEWS:
12. app/views/dashboard/show.html.erb - Main dashboard
13. app/views/settings/show.html.erb - User settings

STIMULUS CONTROLLERS:
14. app/javascript/controllers/form_controller.js - Form validation/submission
15. app/javascript/controllers/modal_controller.js - Modal open/close
16. app/javascript/controllers/dropdown_controller.js - Dropdown toggle
17. app/javascript/controllers/flash_controller.js - Auto-dismiss flash

View requirements:
- Use ViewComponents instead of raw HTML where available
- Use Turbo Frames for dynamic content areas
- Use Turbo Streams for real-time updates
- Connect Stimulus controllers with data-controller attributes
- Use Tailwind CSS for all styling
- Include proper meta tags for SEO
- Add data-turbo-frame attributes for navigation

{ctx.get_deduplication_instructions()}
"""

        try:
            result = llm.generate_json(CODE_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "app/views/view.html.erb")
                content = f.get("content", "")
                language = f.get("language", "erb")

                # Categorize based on path
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
        # Build database context if available
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
        }},
        {{
            "path": "app/services/stripe/checkout_service.rb",
            "language": "ruby",
            "content": "module Stripe\\n  class CheckoutService...",
            "exports": ["Stripe::CheckoutService"]
        }}
    ]
}}

Generate these service objects:

1. app/services/base_service.rb - Base class with:
   - call class method pattern
   - Result object (success/failure)
   - Error handling

2. app/services/stripe/checkout_service.rb - Create Stripe checkout session
3. app/services/stripe/webhook_handler.rb - Handle Stripe webhooks
4. app/services/stripe/subscription_service.rb - Manage subscriptions

5. app/services/users/onboarding_service.rb - New user setup
6. app/services/users/settings_service.rb - Update user settings

7. app/jobs/application_job.rb - Base job class
8. app/jobs/send_email_job.rb - Async email sending

9. app/mailers/application_mailer.rb - Base mailer
10. app/mailers/user_mailer.rb - User-related emails

Service object pattern:
```ruby
class SomeService < BaseService
  def initialize(user:, params:)
    @user = user
    @params = params
  end

  def call
    # Business logic here
    success(result)
  rescue StandardError => e
    failure(e.message)
  end
end
```

Each service MUST:
- Inherit from BaseService
- Use dependency injection via initialize
- Return Result objects (not raise exceptions for business errors)
- Be testable in isolation
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

                # Categorize based on path
                if "jobs" in path:
                    category = "job"
                elif "mailers" in path:
                    category = "mailer"
                else:
                    category = "service"

                ctx.add_file(path, content, language, category, exports=exports)

        except Exception as e:
            self.logger.error(f"Failed to generate services: {e}")

    def _create_github_repo(self, opp, files: list[GeneratedFile]) -> dict[str, str]:
        """Create GitHub repository with generated files.

        Returns:
            Dict with owner, name, and url keys.
        """
        try:
            repo = github.create_repository(
                name=opp.slug,
                description=opp.one_liner,
                private=True,
            )

            if not repo:
                return {"owner": "", "name": "", "url": ""}

            owner = repo.get("owner", {}).get("login", "")
            repo_name = repo.get("name", opp.slug)

            # Create files in batches
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
