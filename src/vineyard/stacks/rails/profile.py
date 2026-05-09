from vineyard.stacks.base import StackProfile, _stack_dir

_DIR = _stack_dir("rails")

RAILS = StackProfile(
    name="rails",
    display_name="Ruby on Rails 7.1",
    description="Rails + Hotwire + ViewComponent + PostgreSQL",
    container_image="ruby:3.3-bookworm",
    default_auth="devise",
    default_payments="stripe",
    default_db="postgresql",
    rubric_path=_DIR / "rubric.md",
    system_prompt_path=_DIR / "system_prompt.md",
    prompt_dir=_DIR / "prompts",
    file_extensions=(".rb", ".erb", ".yml", ".rake"),
)
