Generate **both** the application AND the Terraform — they are equally part of the deliverable. A run that produces only `app/` files is incomplete.

Order of operations the agent should follow:

1. Application code (`app/`, `tests/`, `alembic/`, `pyproject.toml`)
2. Container (`Dockerfile`, `.dockerignore`, `entrypoint.sh`, `docker-compose.yml`)
3. Terraform under `infra/` — every resource referenced in the rubric
4. README with all three flows (test / local / deploy)

Terraform-specific guardrails:

- Always declare a provider version constraint in `versions.tf`
- Tag every resource via `default_tags` in the provider block (Project, Environment, ManagedBy=terraform)
- Never use `aws_db_instance.password` in plaintext — use `aws_secretsmanager_secret_version` and reference via App Runner `runtime_environment_secrets`
- Set `deletion_protection = true` on RDS even in MVP — surprise drops are a footgun
- Set `storage_encrypted = true` on RDS
- Default `multi_az = false` to keep MVP costs low; flag in README that production should flip it
- Output the App Runner URL but mark RDS endpoint outputs as `sensitive = true`
