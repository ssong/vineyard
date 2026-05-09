from vineyard.stacks.base import StackProfile, _stack_dir

_DIR = _stack_dir("nextjs")

NEXTJS = StackProfile(
    name="nextjs",
    display_name="Next.js 15",
    description="Next.js App Router + TypeScript + Tailwind + Drizzle",
    container_image="node:20-bookworm",
    default_auth="magic_link",
    default_payments="none",
    default_db="postgresql",
    rubric_path=_DIR / "rubric.md",
    system_prompt_path=_DIR / "system_prompt.md",
    prompt_dir=_DIR / "prompts",
    file_extensions=(".ts", ".tsx", ".js", ".jsx", ".css", ".json"),
)
