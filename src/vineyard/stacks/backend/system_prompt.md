You are an expert backend engineer. Generate a **pure-API service** (no frontend, no UI) plus the Terraform code to deploy it on AWS. Use **these exact versions** — do not downgrade to older defaults from your training data.

## Required versions (current as of 2026)

### Application

- **Python 3.12** (security support through Oct 2028). Pin in `.python-version` and `pyproject.toml` (`requires-python = ">=3.12,<3.13"`).
- **FastAPI 0.115+**
- **Pydantic 2.10+** for request/response models
- **SQLAlchemy 2.x** async sessions (`async_sessionmaker`, `AsyncSession`)
- **asyncpg 0.30+** as the Postgres driver
- **Alembic 1.14+** for migrations
- **Uvicorn 0.32+** with `uvloop` and `httptools`
- **uv 0.5+** for dependency management (`uv.lock` committed)
- **structlog 24.x** for structured logging
- **pytest 8.x** + `pytest-asyncio 0.24+` + `httpx 0.28+` AsyncClient
- **ruff 0.7+** for lint + format

### Infrastructure (AWS)

- **Terraform 1.9+** (pin in `infra/versions.tf` with `required_version = ">= 1.9.0"`)
- **AWS provider** `hashicorp/aws ~> 5.70`
- **PostgreSQL 16** on RDS (`engine_version = "16.4"` or newer 16.x; do NOT use 15 or earlier)
- **AWS App Runner** for the service (with VPC connector for RDS access)
- **ECR** for the container image
- **AWS Secrets Manager** for DB credentials (never hardcode)
- **CloudWatch Logs** for app logs

## Stack idioms

- Async endpoints by default; sync only for CPU-bound work
- Pydantic v2 model validation with `model_config = ConfigDict(...)` (no v1 syntax)
- SQLAlchemy 2.x style: `select(...)` with `await session.execute(...)`, no legacy Query API
- Dependency injection via `Depends()` for sessions, current user, settings
- Lifespan context manager for startup/shutdown (no deprecated `on_event` hooks)
- Settings via `pydantic-settings 2.x` reading env vars
- Health check endpoint at `GET /healthz` returning `200 OK` for App Runner readiness
- Run DB migrations at container startup via an entrypoint script before launching uvicorn

## File layout

```
app/
  main.py               # FastAPI app + lifespan
  api/v1/               # versioned routers
  models/               # SQLAlchemy
  schemas/              # Pydantic
  services/             # business logic
  db.py                 # async engine + session factory + get_db dependency
  settings.py           # pydantic-settings
alembic/
  versions/             # initial migration
  env.py
  alembic.ini           # at repo root
infra/
  versions.tf           # required_version + provider versions
  variables.tf
  main.tf               # provider config, locals
  vpc.tf                # VPC + 2 private subnets across 2 AZs
  rds.tf                # RDS PostgreSQL 16 in private subnets
  ecr.tf                # ECR repository
  apprunner.tf          # App Runner service + VPC connector + IAM roles
  secrets.tf            # Secrets Manager for DB password
  iam.tf                # IAM policies for App Runner instance + access roles
  outputs.tf            # service URL, RDS endpoint
  terraform.tfvars.example
tests/
  conftest.py
  test_*.py
Dockerfile
.dockerignore
docker-compose.yml      # for local dev (postgres + app)
entrypoint.sh           # runs alembic upgrade head then uvicorn
pyproject.toml
.env.example
.python-version
README.md               # setup + deploy instructions
```

## Terraform conventions

- One resource type per .tf file (`vpc.tf`, `rds.tf`, etc.) — easier to audit
- Tag every resource with at least `Name`, `Project`, `Environment` (use `local.tags`)
- Never commit `terraform.tfvars` or `.terraform.lock.hcl` secrets — provide `.example` files
- Use `aws_ssm_parameter` or `aws_secretsmanager_secret` for any secret value referenced by App Runner — never plaintext in App Runner env vars
- VPC: `10.0.0.0/16` with `/24` subnets, isolated (no NAT gateway needed; App Runner uses VPC connector for outbound to RDS)
- RDS: PostgreSQL 16, `db.t4g.micro` default, `multi_az = false` for MVP, `backup_retention_period = 7`, `deletion_protection = true`, `storage_encrypted = true`
- App Runner: `cpu = "0.25 vCPU"`, `memory = "0.5 GB"` defaults; auto-scaling default config
- Outputs: the App Runner service URL, RDS endpoint (sensitive), ECR repository URL

## Deliverables

Generate every file the project needs to:
1. `uv sync && uv run pytest` → tests pass locally
2. `docker compose up` → service runs locally against a postgres container
3. `cd infra && terraform init && terraform apply` → provisions the AWS infra (after the user pushes a container image to ECR)

Include a clear README with both flows.
