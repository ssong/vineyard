from vineyard.stacks.base import StackProfile, _stack_dir

_DIR = _stack_dir("fastapi")

FASTAPI = StackProfile(
    name="fastapi",
    display_name="FastAPI",
    description="FastAPI + SQLAlchemy + Pydantic + Alembic",
    container_image="python:3.12-bookworm",
    default_auth="oauth",
    default_payments="none",
    default_db="postgresql",
    rubric_path=_DIR / "rubric.md",
    system_prompt_path=_DIR / "system_prompt.md",
    prompt_dir=_DIR / "prompts",
    file_extensions=(".py", ".sql", ".toml", ".yaml"),
    validate_commands=(
        "pip install -q uv",
        "uv sync --frozen || uv sync",
        "uv run ruff check .",
        "uv run pytest -q",
    ),
)
