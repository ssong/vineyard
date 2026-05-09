from vineyard.stacks.base import StackProfile, _stack_dir

_DIR = _stack_dir("cli")

CLI = StackProfile(
    name="cli",
    display_name="Python CLI (Typer)",
    description="Local-first Python CLI with Typer + Rich, packaged via uv",
    container_image="python:3.12-bookworm",
    default_auth="none",
    default_payments="none",
    default_db="sqlite",
    rubric_path=_DIR / "rubric.md",
    system_prompt_path=_DIR / "system_prompt.md",
    prompt_dir=_DIR / "prompts",
    file_extensions=(".py", ".toml", ".md", ".yaml"),
    validate_commands=(
        "pip install -q uv",
        "uv sync --frozen || uv sync",
        "uv run ruff check .",
        "uv run pytest -q",
    ),
)
