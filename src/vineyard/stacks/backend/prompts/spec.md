Express the API as FastAPI routers under `app/api/v1/`. Define request/response Pydantic schemas separately from SQLAlchemy models. Database schema in SQLAlchemy declarative form with an Alembic initial migration.

In addition to the standard spec, include:

- A short **Infrastructure** section listing AWS resources required (VPC topology, RDS sizing, App Runner config, any extras like S3/SQS/SES if the spec calls for them)
- Environment variables the App Runner service consumes (and which come from Secrets Manager vs. plain env)
- Operational concerns: log retention, alarms (CloudWatch), backup policy
