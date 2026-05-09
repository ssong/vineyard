from vineyard.stacks.base import StackProfile, _stack_dir

_DIR = _stack_dir("tui")

TUI = StackProfile(
    name="tui",
    display_name="Python TUI (Textual)",
    description="Local-first Python TUI with Textual + Rich, packaged via uv",
    container_image="python:3.12-bookworm",
    default_auth="none",
    default_payments="none",
    default_db="sqlite",
    rubric_path=_DIR / "rubric.md",
    system_prompt_path=_DIR / "system_prompt.md",
    prompt_dir=_DIR / "prompts",
    file_extensions=(".py", ".tcss", ".toml", ".md", ".yaml"),
    validate_commands=(
        "pip install -q uv",
        "uv sync --frozen || uv sync",
        "uv run ruff check .",
        "uv run pytest -q",
    ),
)
