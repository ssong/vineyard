"""DevOps Agent - Rails deployment infrastructure generation."""

from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import DEVOPS_AGENT_PROMPT
from src.models import FactoryState, GeneratedFile
from src.tools import github, llm


class DevOpsAgent(BaseAgent):
    """Agent for generating Rails deployment infrastructure."""

    name = "DevOpsAgent"
    domain = "engineering"

    def run(self, state: FactoryState) -> dict[str, Any]:
        """
        Generate deployment configs, CI/CD, and monitoring setup for Rails.
        """
        self.log_start()

        # Initialize subtask tracking
        self.init_subtask_tracking(state, parent_phase="build")

        opp = state.handoff.opportunity
        prefs = state.handoff.build_preferences

        try:
            # Generate Dockerfile for Rails
            dockerfile = self.run_step(
                "dockerfile",
                "Generate Dockerfile",
                lambda: self._generate_dockerfile(prefs),
                "Multi-stage Docker build for Rails",
            )

            # Generate docker-compose for local development
            compose = self.run_step(
                "docker_compose",
                "Generate docker-compose",
                lambda: self._generate_docker_compose(opp, prefs),
                "Local development environment",
            )

            # Generate CI/CD workflow (GitHub Actions)
            ci_cd = self.run_step(
                "ci_cd",
                "Generate CI/CD workflows",
                lambda: self._generate_ci_cd(opp, prefs),
                "GitHub Actions for test and deploy",
            )

            # Generate Railway deployment config
            deploy_config = self.run_step(
                "deploy_config",
                "Generate deployment config",
                lambda: self._generate_deploy_config(opp, prefs),
                "Railway config, Procfile, Puma",
            )

            # Generate environment setup
            env_setup = self.run_step(
                "env_setup",
                "Generate environment setup",
                lambda: self._generate_env_setup(prefs),
                "Environment variables documentation",
            )

            # Generate monitoring config
            monitoring = self.run_step(
                "monitoring",
                "Generate monitoring config",
                lambda: self._generate_monitoring_config(opp),
                "Sentry, health checks, logging",
            )

            # Combine all files
            all_files = dockerfile + compose + ci_cd + deploy_config + env_setup + monitoring

            # Push to GitHub
            self.run_step(
                "push_infra",
                "Push infrastructure to GitHub",
                lambda: self._push_to_github(state, all_files),
                "Push DevOps files to repository",
            )

            output = {
                "infrastructure_files": all_files,
                "hosting": prefs.hosting_preference,
                "database": prefs.database_preference,
            }

            # Complete agent task
            self.complete_agent_task(
                f"Generated {len(all_files)} infrastructure files for {prefs.hosting_preference}"
            )

            self.log_complete()
            return output

        except Exception as e:
            self.fail_agent_task(str(e))
            raise

    def _generate_dockerfile(self, prefs) -> list[GeneratedFile]:
        """Generate Dockerfile for Rails application."""
        user_prompt = f"""Generate a production Dockerfile for a Ruby on Rails 7.1 application:

DATABASE: {prefs.database_preference}
BACKGROUND_JOBS: Sidekiq

Generate JSON with Dockerfile:
{{
    "files": [
        {{
            "path": "Dockerfile",
            "language": "dockerfile",
            "content": "# Multi-stage Dockerfile..."
        }},
        {{
            "path": ".dockerignore",
            "language": "text",
            "content": "..."
        }}
    ]
}}

Include in the Dockerfile:
- Multi-stage build (builder + production)
- Ruby 3.2 base image
- Node.js for asset compilation
- Install dependencies with bundler
- Precompile assets
- Non-root user (rails)
- Health check endpoint (/health)
- Proper ENTRYPOINT and CMD
- Security best practices
- Optimized layer caching

The Dockerfile should:
1. Use official ruby:3.2-slim as base
2. Install system dependencies (libpq-dev, nodejs, yarn)
3. Copy Gemfile and run bundle install with --deployment
4. Copy app code
5. Precompile assets with SECRET_KEY_BASE_DUMMY=1
6. Create non-root user
7. Set proper permissions
8. Expose port 3000
9. Use exec form for CMD
"""

        try:
            result = llm.generate_json(DEVOPS_AGENT_PROMPT, user_prompt)
            return [
                GeneratedFile(
                    path=f.get("path", "Dockerfile"),
                    content=f.get("content", ""),
                    language=f.get("language", "dockerfile"),
                )
                for f in result.get("files", [])
            ]
        except Exception as e:
            self.logger.error(f"Failed to generate Dockerfile: {e}")
            return []

    def _generate_docker_compose(self, opp, prefs) -> list[GeneratedFile]:
        """Generate docker-compose for local development."""
        user_prompt = f"""Generate docker-compose.yml for Rails local development:

PRODUCT: {opp.name}
DATABASE: {prefs.database_preference}

Generate JSON with docker-compose:
{{
    "files": [
        {{
            "path": "docker-compose.yml",
            "language": "yaml",
            "content": "version: '3.8'..."
        }},
        {{
            "path": "docker-compose.override.yml",
            "language": "yaml",
            "content": "..."
        }}
    ]
}}

Include services for:
1. web - Rails application
   - Build from Dockerfile
   - Volume mount for live reload
   - Port 3000
   - Depends on db, redis

2. db - PostgreSQL 15
   - Volume for data persistence
   - Health check
   - Default credentials for dev

3. redis - Redis 7
   - Volume for persistence
   - Used by Sidekiq and caching

4. sidekiq - Background job processor
   - Same image as web
   - Different command (bundle exec sidekiq)
   - Depends on db, redis

5. mailcatcher (optional) - Email testing
   - Port 1080 for web UI

Include:
- Named volumes for db and redis data
- Network for service communication
- Environment variables from .env
- Health checks for all services
"""

        try:
            result = llm.generate_json(DEVOPS_AGENT_PROMPT, user_prompt)
            return [
                GeneratedFile(
                    path=f.get("path", "docker-compose.yml"),
                    content=f.get("content", ""),
                    language=f.get("language", "yaml"),
                )
                for f in result.get("files", [])
            ]
        except Exception as e:
            self.logger.error(f"Failed to generate docker-compose: {e}")
            return []

    def _generate_ci_cd(self, opp, prefs) -> list[GeneratedFile]:
        """Generate GitHub Actions CI/CD workflow for Rails."""
        user_prompt = f"""Generate GitHub Actions CI/CD workflow for Rails:

PRODUCT: {opp.name}
HOSTING: {prefs.hosting_preference}
DATABASE: {prefs.database_preference}

Generate JSON with workflow files:
{{
    "files": [
        {{
            "path": ".github/workflows/ci.yml",
            "language": "yaml",
            "content": "name: CI..."
        }},
        {{
            "path": ".github/workflows/deploy.yml",
            "language": "yaml",
            "content": "name: Deploy..."
        }}
    ]
}}

CI workflow (.github/workflows/ci.yml) should:
- Trigger on push to any branch and PRs to main
- Use Ruby 3.2
- Set up PostgreSQL service
- Set up Redis service
- Cache bundler dependencies
- Run: bundle install
- Run: bundle exec rubocop (linting)
- Run: bundle exec rspec (tests)
- Run: bundle exec rails assets:precompile (build check)
- Run: bundle exec brakeman -q (security scan)
- Upload test coverage to Codecov (optional)

Deploy workflow (.github/workflows/deploy.yml) should:
- Trigger on push to main (after CI passes)
- Deploy to Railway using railway CLI
- Use RAILWAY_TOKEN secret
- Run database migrations
- Notify on success/failure

Include proper environment variables:
- RAILS_ENV=test for CI
- DATABASE_URL for PostgreSQL service
- REDIS_URL for Redis service
- RAILS_MASTER_KEY for credentials
"""

        try:
            result = llm.generate_json(DEVOPS_AGENT_PROMPT, user_prompt)
            return [
                GeneratedFile(
                    path=f.get("path", ".github/workflows/workflow.yml"),
                    content=f.get("content", ""),
                    language=f.get("language", "yaml"),
                )
                for f in result.get("files", [])
            ]
        except Exception as e:
            self.logger.error(f"Failed to generate CI/CD: {e}")
            return []

    def _generate_deploy_config(self, opp, prefs) -> list[GeneratedFile]:
        """Generate Railway deployment configuration."""
        hosting = prefs.hosting_preference

        user_prompt = f"""Generate deployment config for {hosting}:

PRODUCT: {opp.name}
HOSTING: {hosting}
DATABASE: {prefs.database_preference}

Generate JSON with config files:
{{
    "files": [
        {{
            "path": "railway.json",
            "language": "json",
            "content": "..."
        }},
        {{
            "path": "Procfile",
            "language": "text",
            "content": "..."
        }},
        {{
            "path": "config/puma.rb",
            "language": "ruby",
            "content": "..."
        }}
    ]
}}

railway.json should include:
{{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {{
    "builder": "NIXPACKS"
  }},
  "deploy": {{
    "startCommand": "bundle exec puma -C config/puma.rb",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }}
}}

Procfile should include:
- web: bundle exec puma -C config/puma.rb
- worker: bundle exec sidekiq -C config/sidekiq.yml
- release: bundle exec rails db:migrate

config/puma.rb should include:
- Workers based on WEB_CONCURRENCY env var
- Threads configuration
- Port from PORT env var
- Preload app for memory efficiency
- On worker boot: ActiveRecord connection handling
"""

        try:
            result = llm.generate_json(DEVOPS_AGENT_PROMPT, user_prompt)
            return [
                GeneratedFile(
                    path=f.get("path", "deploy.config"),
                    content=f.get("content", ""),
                    language=f.get("language", "text"),
                )
                for f in result.get("files", [])
            ]
        except Exception as e:
            self.logger.error(f"Failed to generate deploy config: {e}")
            return []

    def _generate_env_setup(self, prefs) -> list[GeneratedFile]:
        """Generate environment variable documentation."""
        user_prompt = f"""Generate environment setup documentation for Rails:

AUTH: {prefs.auth_preference}
PAYMENTS: {prefs.payments_preference}
DATABASE: {prefs.database_preference}

Generate JSON with env files:
{{
    "files": [
        {{
            "path": ".env.example",
            "language": "env",
            "content": "# Required environment variables..."
        }},
        {{
            "path": ".env.development",
            "language": "env",
            "content": "# Development defaults..."
        }},
        {{
            "path": "docs/ENVIRONMENT.md",
            "language": "markdown",
            "content": "# Environment Setup..."
        }}
    ]
}}

.env.example should include (with placeholders):
# Rails
RAILS_ENV=development
SECRET_KEY_BASE=
RAILS_MASTER_KEY=

# Database
DATABASE_URL=postgres://user:password@localhost:5432/app_development

# Redis
REDIS_URL=redis://localhost:6379/0

# Authentication (Devise)
# (Devise uses database, no external auth service needed)

# Stripe
STRIPE_PUBLISHABLE_KEY=pk_test_xxx
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# Email (Resend)
RESEND_API_KEY=re_xxx
MAILER_FROM_EMAIL=noreply@example.com

# Application
APP_HOST=localhost:3000
ALLOWED_HOSTS=localhost

# Sidekiq
SIDEKIQ_CONCURRENCY=5

docs/ENVIRONMENT.md should document:
- All required environment variables
- Example values and format
- Where to get API keys
- Development vs production differences
- How to use Rails credentials
"""

        try:
            result = llm.generate_json(DEVOPS_AGENT_PROMPT, user_prompt)
            return [
                GeneratedFile(
                    path=f.get("path", ".env.example"),
                    content=f.get("content", ""),
                    language=f.get("language", "env"),
                )
                for f in result.get("files", [])
            ]
        except Exception as e:
            self.logger.error(f"Failed to generate env setup: {e}")
            return []

    def _generate_monitoring_config(self, opp) -> list[GeneratedFile]:
        """Generate monitoring and observability config for Rails."""
        user_prompt = f"""Generate monitoring configuration for Rails:

PRODUCT: {opp.name}

Generate JSON with monitoring files:
{{
    "files": [
        {{
            "path": "config/initializers/sentry.rb",
            "language": "ruby",
            "content": "# Sentry configuration..."
        }},
        {{
            "path": "app/controllers/health_controller.rb",
            "language": "ruby",
            "content": "class HealthController..."
        }},
        {{
            "path": "config/initializers/lograge.rb",
            "language": "ruby",
            "content": "# Lograge configuration..."
        }}
    ]
}}

Include:
1. config/initializers/sentry.rb - Sentry error tracking
   - Conditional on SENTRY_DSN presence
   - Set environment from RAILS_ENV
   - Configure breadcrumbs
   - Filter sensitive params

2. app/controllers/health_controller.rb - Health check endpoint
   - GET /health returns JSON status
   - Check database connection
   - Check Redis connection
   - Return overall health status

3. config/initializers/lograge.rb - Structured logging
   - Enable lograge
   - JSON format for production
   - Include useful request data
   - Filter sensitive params

4. config/initializers/rack_attack.rb - Rate limiting
   - Throttle login attempts
   - Throttle API requests
   - Block bad actors
   - Safelist for internal IPs

5. lib/tasks/health.rake - Health check rake task
   - Check all services
   - Useful for deployment verification
"""

        try:
            result = llm.generate_json(DEVOPS_AGENT_PROMPT, user_prompt)
            return [
                GeneratedFile(
                    path=f.get("path", "config/initializers/monitoring.rb"),
                    content=f.get("content", ""),
                    language=f.get("language", "ruby"),
                )
                for f in result.get("files", [])
            ]
        except Exception as e:
            self.logger.error(f"Failed to generate monitoring: {e}")
            return []

    def _push_to_github(self, state: FactoryState, files: list[GeneratedFile]):
        """Push infrastructure files to GitHub."""
        if not state.github_repo:
            self.logger.error("No GitHub repo info available - CodeAgent must run first")
            raise RuntimeError("No GitHub repo info available")

        repo_info = state.github_repo
        if not repo_info.get("owner") or not repo_info.get("name"):
            self.logger.error("GitHub repo info incomplete - missing owner or name")
            raise RuntimeError("GitHub repo info incomplete")

        try:
            file_data = [
                {"path": f.path, "content": f.content, "message": f"Add {f.path}"}
                for f in files
            ]

            created = github.create_files_batch(
                repo_info["owner"],
                repo_info["name"],
                file_data
            )

            # Verify files were pushed
            if len(created) != len(files):
                failed = [f.path for f in files if f.path not in created]
                self.logger.warning(f"Failed to push {len(failed)} devops files: {failed[:5]}")

            self.logger.info(f"Successfully pushed {len(created)} devops files to GitHub")

        except Exception as e:
            self.logger.error(f"Failed to push to GitHub: {e}")
            raise RuntimeError(f"Failed to push devops files to GitHub: {e}")
