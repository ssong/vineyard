# Vineyard

Single-user Textual TUI that turns a PRD into a working multi-stack codebase
and verifies it actually compiles and tests pass.

Powered by Pydantic AI (with the Pydantic AI Gateway for routing + Logfire
observability) for the planning agents, and either Pydantic AI itself
(default) or Anthropic's Claude Agent SDK (beta) for the heavy code
generation phase.

## Pipeline

```
PRD → PRD_ANALYSIS → DESIGN → SPEC → BUILD → VALIDATE
                                       ↑         │
                                       └ fix mode if failed
```

Every phase is a Pydantic AI `Agent` with a typed Pydantic output. The build
agent uses tool calls (`write_file` / `read_file` / `list_files`) to assemble
the codebase. The validate phase actually runs the generated code in a
sandbox; if it fails, it loops back into BUILD with the failing step's
stderr/stdout in the prompt so the agent can surgically fix it.

## Stacks

| Name | Description |
|---|---|
| `nextjs` | Next.js 15 + React 19 + TypeScript + Tailwind v4 + Drizzle |
| `rails` | Rails 8.0 + Hotwire + Solid Queue + ViewComponent |
| `fastapi` | FastAPI 0.115+ + SQLAlchemy 2 + Pydantic v2 + Alembic |
| `django` | Django 5.2 + DRF + HTMX + psycopg 3 |
| `backend` | Pure-API FastAPI + Terraform (AWS App Runner + RDS) |

Each stack pins specific LTS / current versions in its system prompt so the
agent doesn't drift to older defaults.

## Install (development)

Vineyard uses [`uv`](https://docs.astral.sh/uv/) as its package manager.

```bash
uv sync                # create .venv, install runtime + dev deps from uv.lock
uv sync --extra e2b    # also install the E2B sandbox SDK (optional)
uv run vineyard        # launch the TUI
uv run pytest          # run tests
uv run ruff check src tests
uv run ruff format src tests
```

`uv.lock` is committed; bump with `uv lock --upgrade-package <pkg>`.

## Configure

Required:

```bash
vineyard config pydantic-ai-gateway-api-key pylf_v1_us_...   # required
```

Optional:

```bash
vineyard config logfire-token pylf_v1_us_...        # client-side spans
vineyard config logfire-read-token pylf_v1_us_...   # for `vineyard cost`
vineyard config anthropic-api-key sk-ant-...        # only for managed_agents
vineyard config e2b-api-key e2b_...                 # validate via E2B sandbox
```

Or set the equivalent `VINEYARD_*` env vars directly. Run `vineyard config`
with no args to print the current values.

The config file is `~/.vineyard/config.env` (chmod 600). Run data lives at
`~/.vineyard/runs/<run-id>/`.

## CLI

```bash
vineyard                       # opens the TUI
vineyard run prd.md \
  --name "Bandung CRM" \
  --stack backend \
  --executor pydantic_ai       # or managed_agents (beta)
vineyard list                  # show all runs
vineyard resume <run-id>       # resume a paused/failed run
vineyard restart <run-id>      # wipe outputs and re-run from PRD analysis
vineyard delete <run-id>       # remove a run (DB row + on-disk output)
vineyard cost <run-id>         # gateway-recorded cost from Logfire
vineyard stacks                # list available stacks
vineyard config [key] [value]  # show or set config
```

`run-id` arguments accept any unique short prefix (e.g. `vineyard delete abc12345`).

## TUI keybindings

**Home screen** — `n` new · `enter`/click open · `d` delete · `r` refresh · `q` quit · `?` help

**Run detail** — `v` view current phase · `a` approve checkpoint · `r` resume / retry ·
`x` stop · `R` restart · `o` open output dir · `esc` back

**Phase output** — `a` approve · `Ctrl+S` save clarification answers · `esc` back

## Build executors

`pydantic_ai` (default): a Pydantic AI `Agent` with closure-based file tools,
routed through the Pydantic AI Gateway. Cost computed from token counts using
Anthropic list pricing.

`managed_agents` (beta): the Claude Agent SDK (`claude-agent-sdk`) running
locally with built-in `Read` / `Write` / `Edit` / `Glob` / `Grep` tools.
Cost surfaced authoritatively from `ResultMessage.total_cost_usd`. Marked as
the wire-up point for Anthropic Outcomes when its API surface stabilizes.

Toggle from the new-run screen or pass `--executor managed_agents` on the CLI.

## Validate phase

After BUILD, the VALIDATE phase actually runs the stack's commands against
the generated code:

| Stack | Commands |
|---|---|
| `nextjs` | `pnpm install --frozen-lockfile && tsc --noEmit && pnpm test && pnpm build` |
| `fastapi` | `uv sync && ruff check && pytest` |
| `django` | `uv sync && ruff check && manage.py check && pytest` |
| `backend` | FastAPI commands + `terraform init -backend=false && terraform validate && terraform fmt -check` |
| `rails` | `bundle install && zeitwerk:check && rspec` |

Backend selection (`VINEYARD_VALIDATE_EXECUTOR=auto` is the default):

- E2B sandbox if `VINEYARD_E2B_API_KEY` is set
- otherwise local Docker if the `docker` CLI is on PATH
- otherwise validation is skipped with a notice

Force a specific backend with `VINEYARD_VALIDATE_EXECUTOR=docker | e2b | none`.

### Auto-fix loop

When a validate step exits non-zero, the loop feeds the failing command,
exit code, and stderr/stdout tail back into BUILD as a "fix mode" prompt
appended to the standard build context. The agent reads the affected files
(via the existing `read_file` tool) and overwrites them surgically. Then we
re-validate.

Bounded by:

- `VINEYARD_VALIDATE_MAX_RETRIES` (default `2`, so up to 3 builds total)
- `VINEYARD_RUN_COST_CAP_USD` (default `5.0`, set to `0` or unset to disable)

If retries are exhausted or the cost cap is hit, the validate phase fails
with the last error preserved — recoverable via `r` (resume) on the run
detail screen.

## Approval checkpoints

By default the run pauses for user approval at the `design` and `build`
phases. Approve from the run detail screen with `a`, or pass `--yes` on the
CLI to skip.

## Clarifications

PRD analysis (and optionally design / spec) can ask clarifying questions.
The runner detects unanswered items, pauses the phase as
`AWAITING_CLARIFICATION`, and pushes the phase output screen with an inline
form. Answers feed back into downstream phase prompts.

## Output

Each run lands at `~/.vineyard/runs/<run-id>/output/`. The build phase writes
to `output/build/`. The generated `README.md` inside that directory covers
local install / run instructions for that stack.

## Pipeline observability

All LLM traffic flows through the Pydantic AI Gateway → Logfire. Set
`VINEYARD_LOGFIRE_TOKEN` to also send local `with logfire.span(...)` spans
to a Logfire project of your choice. `vineyard cost <run-id>` queries Logfire
for the gateway-recorded cost using a separate read token.

## License

MIT
