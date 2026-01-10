"""DevOps Agent - Deployment infrastructure generation."""

from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import DEVOPS_AGENT_PROMPT
from src.models import FactoryState, GeneratedFile
from src.tools import github, llm


class DevOpsAgent(BaseAgent):
    """Agent for generating deployment infrastructure."""

    name = "DevOpsAgent"
    domain = "engineering"

    def run(self, state: FactoryState) -> dict[str, Any]:
        """
        Generate deployment configs, CI/CD, and monitoring setup.
        """
        self.log_start()

        opp = state.handoff.opportunity
        prefs = state.handoff.build_preferences

        # Generate Dockerfile
        dockerfile = self._generate_dockerfile(prefs)

        # Generate docker-compose
        compose = self._generate_docker_compose(opp, prefs)

        # Generate CI/CD workflow
        ci_cd = self._generate_ci_cd(opp, prefs)

        # Generate deployment config (Vercel/Fly.io)
        deploy_config = self._generate_deploy_config(opp, prefs)

        # Generate environment setup
        env_setup = self._generate_env_setup(prefs)

        # Generate monitoring config
        monitoring = self._generate_monitoring_config(opp)

        # Combine all files
        all_files = dockerfile + compose + ci_cd + deploy_config + env_setup + monitoring

        # Push to GitHub
        self._push_to_github(opp, all_files)

        # Note: Linear task tracking is now handled at the runner level

        output = {
            "infrastructure_files": all_files,
            "hosting": prefs.hosting_preference,
            "database": prefs.database_preference,
        }

        self.log_complete()
        return output

    def _generate_dockerfile(self, prefs) -> list[GeneratedFile]:
        """Generate Dockerfile for the application."""
        frontend = prefs.tech_stack.get("frontend", "nextjs")

        user_prompt = f"""Generate a production Dockerfile for:

FRONTEND: {frontend}
DATABASE: {prefs.database_preference}

Generate JSON with Dockerfile:
{{
    "files": [
        {{
            "path": "Dockerfile",
            "language": "dockerfile",
            "content": "# Multi-stage Dockerfile..."
        }}
    ]
}}

Include:
- Multi-stage build
- Non-root user
- Health check
- Optimized layer caching
- Security best practices
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
        user_prompt = f"""Generate docker-compose.yml for local development:

PRODUCT: {opp.name}
DATABASE: {prefs.database_preference}

Generate JSON with docker-compose:
{{
    "files": [
        {{
            "path": "docker-compose.yml",
            "language": "yaml",
            "content": "version: '3.8'..."
        }}
    ]
}}

Include services for:
- Application
- Database (PostgreSQL)
- Redis (if needed)
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
        """Generate GitHub Actions CI/CD workflow."""
        user_prompt = f"""Generate GitHub Actions CI/CD workflow:

PRODUCT: {opp.name}
FRONTEND: {prefs.tech_stack.get('frontend')}
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

CI workflow should:
- Run on push/PR
- Install dependencies
- Run linting
- Run tests
- Build application

Deploy workflow should:
- Deploy to {prefs.hosting_preference}
- Run on push to main
- Use environment secrets
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
        """Generate deployment platform config."""
        hosting = prefs.hosting_preference

        user_prompt = f"""Generate deployment config for {hosting}:

PRODUCT: {opp.name}
HOSTING: {hosting}
DATABASE: {prefs.database_preference}

Generate JSON with config files:
{{
    "files": [
        {{
            "path": "vercel.json",
            "language": "json",
            "content": "..."
        }}
    ]
}}

For Vercel: vercel.json
For Fly.io: fly.toml
Include environment variable references.
"""

        try:
            result = llm.generate_json(DEVOPS_AGENT_PROMPT, user_prompt)
            return [
                GeneratedFile(
                    path=f.get("path", "deploy.config"),
                    content=f.get("content", ""),
                    language=f.get("language", "json"),
                )
                for f in result.get("files", [])
            ]
        except Exception as e:
            self.logger.error(f"Failed to generate deploy config: {e}")
            return []

    def _generate_env_setup(self, prefs) -> list[GeneratedFile]:
        """Generate environment variable documentation."""
        user_prompt = f"""Generate environment setup documentation:

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
            "path": "docs/ENVIRONMENT.md",
            "language": "markdown",
            "content": "# Environment Setup..."
        }}
    ]
}}

Document all required environment variables with:
- Description
- Example values
- Where to get them
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
        """Generate monitoring and observability config."""
        user_prompt = f"""Generate monitoring configuration:

PRODUCT: {opp.name}

Generate JSON with monitoring files:
{{
    "files": [
        {{
            "path": "lib/monitoring.ts",
            "language": "typescript",
            "content": "// Monitoring setup..."
        }}
    ]
}}

Include:
- Health check endpoint
- Error tracking setup (Sentry-compatible)
- Basic logging configuration
- Performance monitoring hooks
"""

        try:
            result = llm.generate_json(DEVOPS_AGENT_PROMPT, user_prompt)
            return [
                GeneratedFile(
                    path=f.get("path", "lib/monitoring.ts"),
                    content=f.get("content", ""),
                    language=f.get("language", "typescript"),
                )
                for f in result.get("files", [])
            ]
        except Exception as e:
            self.logger.error(f"Failed to generate monitoring: {e}")
            return []

    def _push_to_github(self, opp, files: list[GeneratedFile]):
        """Push infrastructure files to GitHub."""
        try:
            file_data = [
                {"path": f.path, "content": f.content, "message": f"Add {f.path}"}
                for f in files
            ]

            github.create_files_batch("", opp.slug, file_data)

        except Exception as e:
            self.logger.error(f"Failed to push to GitHub: {e}")

