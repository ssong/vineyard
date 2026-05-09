from vineyard.stacks.base import StackProfile, _stack_dir

_DIR = _stack_dir("django")

DJANGO = StackProfile(
    name="django",
    display_name="Django 5.2",
    description="Django + DRF + HTMX + PostgreSQL",
    container_image="python:3.12-bookworm",
    default_auth="credentials",
    default_payments="stripe",
    default_db="postgresql",
    rubric_path=_DIR / "rubric.md",
    system_prompt_path=_DIR / "system_prompt.md",
    prompt_dir=_DIR / "prompts",
    file_extensions=(".py", ".html", ".toml"),
    validate_commands=(
        "pip install -q uv",
        "uv sync --frozen || uv sync",
        "uv run ruff check .",
        "uv run python manage.py check",
        "uv run pytest -q",
    ),
)
