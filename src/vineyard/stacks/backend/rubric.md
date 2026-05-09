# Backend + Terraform Build Rubric

## Application setup

- `pyproject.toml` declares `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic`, `pydantic-settings`, `httpx`, `pytest`, `pytest-asyncio`, `structlog`, `ruff`
- `requires-python = ">=3.12,<3.13"`
- `.env.example` lists every env var the app consumes
- `app/main.py` instantiates FastAPI, registers routers, defines a `/healthz` endpoint
- `app/settings.py` uses `pydantic-settings` BaseSettings

## Code quality

- All endpoints are `async def`
- Request/response bodies use Pydantic v2 models in `app/schemas/`
- Database access goes through `Depends(get_db)`; no global sessions
- No business logic inside route handlers — delegate to `app/services/`
- Lifespan context manager (no deprecated `on_event` hooks)

## Database

- `app/models/` defines all SQLAlchemy models with proper `Mapped[...]` typing
- `alembic/versions/` contains an initial migration
- `app/db.py` exposes `engine`, `async_session_factory`, `get_db`
- `entrypoint.sh` runs `alembic upgrade head` before uvicorn starts

## Tests

- At least one test per router under `tests/` using `httpx.AsyncClient`
- `tests/conftest.py` provides an async test session and an app fixture

## Container

- `Dockerfile` uses `python:3.12-slim` (or distroless), runs as non-root, copies `uv.lock` and uses `uv sync --frozen`
- Multi-stage build to keep the runtime image small
- `docker-compose.yml` for local dev with a postgres service and the app linked
- `.dockerignore` excludes `.venv`, `__pycache__`, `.git`, `.pytest_cache`, `infra/.terraform`

## Terraform

- `infra/versions.tf` pins `required_version >= 1.9.0` and `aws provider ~> 5.70`
- `infra/main.tf` configures the AWS provider with `default_tags`
- VPC with at least 2 private subnets across 2 AZs (`infra/vpc.tf`)
- RDS PostgreSQL 16 in private subnets with security group restricted to the App Runner VPC connector (`infra/rds.tf`)
- ECR repository for the container image (`infra/ecr.tf`)
- App Runner service with VPC connector pointing at the private subnets (`infra/apprunner.tf`)
- Secrets Manager for DB password, referenced by App Runner via `runtime_environment_secrets` (`infra/secrets.tf`)
- IAM roles for App Runner instance + access roles (`infra/iam.tf`)
- Outputs: App Runner URL, RDS endpoint, ECR repository URL (`infra/outputs.tf`)
- No hardcoded credentials, account IDs, or region strings — all parameterized via `variables.tf`

## Deliverables

- `README.md` documents three flows: local test (`uv sync && uv run pytest`), local run (`docker compose up`), AWS deploy (`terraform init && terraform apply` + ECR image push)
- Running `uv sync && uv run pytest` succeeds
- `terraform validate` would succeed (correct HCL, all references valid)
- `terraform plan` against an empty AWS account would only show resource creates (no errors, no warnings about deprecated arguments)
