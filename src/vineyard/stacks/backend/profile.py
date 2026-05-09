from vineyard.stacks.base import StackProfile, _stack_dir

_DIR = _stack_dir("backend")

BACKEND = StackProfile(
    name="backend",
    display_name="Backend API + Terraform",
    description="Pure-API FastAPI service with AWS Terraform (App Runner + RDS, no UI)",
    container_image="python:3.12-bookworm",
    default_auth="oauth",
    default_payments="none",
    default_db="postgresql",
    rubric_path=_DIR / "rubric.md",
    system_prompt_path=_DIR / "system_prompt.md",
    prompt_dir=_DIR / "prompts",
    file_extensions=(".py", ".tf", ".tfvars", ".sql", ".toml", ".yaml", ".yml"),
)
