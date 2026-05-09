# Vineyard

Single-user Textual TUI that turns a PRD into a working multi-stack codebase.
Powered by Pydantic AI (with the Pydantic AI Gateway for observability) and
Anthropic Managed Agents for the heavy code-generation phase.

## Stacks

- `nextjs` — Next.js 15 + TypeScript + Tailwind + Drizzle
- `rails` — Ruby on Rails 7.1 + Hotwire + ViewComponent
- `fastapi` — FastAPI + SQLAlchemy + Alembic
- `django` — Django 5 + DRF + HTMX

## Install

End users:

```bash
brew install vineyard-dev/tap/vineyard      # once the tap exists
# or:
uv tool install vineyard
```

## Develop

Vineyard uses [`uv`](https://docs.astral.sh/uv/) as its package manager.

```bash
uv sync                # create .venv, install runtime + dev deps from uv.lock
uv run vineyard        # launch the TUI
uv run pytest          # run tests
uv run ruff check src tests
uv run ruff format src tests
```

Add a dependency:

```bash
uv add anthropic       # runtime
uv add --dev ruff      # dev only
```

`uv.lock` is committed; bump it with `uv lock --upgrade-package <pkg>`.

## Configure

```bash
vineyard config gateway-key pylf_v1_...
vineyard config logfire-token ...
vineyard config anthropic-key sk-ant-...
```

Or set `VINEYARD_PYDANTIC_AI_GATEWAY_API_KEY`, `VINEYARD_LOGFIRE_TOKEN`,
`VINEYARD_ANTHROPIC_API_KEY` directly.

## Use

```bash
vineyard                  # opens the TUI
vineyard run prd.md \
  --name "Bandung CRM" \
  --stack nextjs \
  --executor managed_agents
vineyard list             # show all runs
vineyard resume <run-id>  # resume a paused/failed run
vineyard stacks           # list available stacks
```

The TUI runs at `vineyard`. From the home screen:

- `n` — start a new run
- `enter` — open the highlighted run
- `a` — approve an awaiting checkpoint
- `q` — quit

## Pipeline

```
PRD → PRD_ANALYSIS → DESIGN → SPEC → BUILD
                                       │
                          Managed Agents (default)
                                  ── or ──
                          Local Claude Agent SDK
```

Each phase is a Pydantic AI `Agent` with a typed output. Build is delegated to
either the Managed Agents harness (with stack-specific outcome rubrics) or, with
`--executor local_sdk`, to the Claude Agent SDK running on your machine.

All LLM traffic flows through the Pydantic AI Gateway → Logfire for traces,
costs, and evals.

## Output

Each run lands at `~/.vineyard/runs/<run-id>/output/`. Use the stack's README
inside the output dir to install dependencies and run the project.

## License

MIT
