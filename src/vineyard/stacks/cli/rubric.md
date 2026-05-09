# Python CLI (Typer) Build Rubric

## Project setup

- `pyproject.toml` declares `typer>=0.12`, `rich>=13.9`, `pydantic-settings>=2`
- `requires-python = ">=3.12,<3.13"`
- `[project.scripts]` declares the CLI entry point pointing at `<package>.cli:main`
- `.python-version` pins 3.12
- `.env.example` lists every env var the app consumes

## Code quality

- Each subcommand is a function decorated with `@app.command()` (or registered via `app.add_typer(...)`)
- Every parameter has explicit `typer.Option`/`typer.Argument` with `help=`
- Output goes through a Rich `Console`, not `print()`
- Errors raise `typer.Exit(code=1)` with a clear Rich error message
- Long-running work uses `rich.progress.Progress`
- Settings come from `pydantic-settings` BaseSettings; no module-level `os.getenv` calls

## Storage (when applicable)

- SQLite goes through `storage.py` with explicit connection lifecycle
- Default DB path uses `Path.home() / ".<app-name>" / "<app>.db"` (or `XDG_CONFIG_HOME` if set)
- `storage.py` exposes a small set of pure functions; tests can inject a tmp_path-based DB

## Tests

- `tests/conftest.py` provides a `CliRunner` fixture and a tmp data dir fixture
- At least one test per top-level subcommand using `runner.invoke(app, [...])`
- Tests assert on `result.exit_code` AND `result.stdout` content

## Deliverables

- `README.md` documents: install (`uv sync && uv tool install .` or equivalent), basic usage, `--help` output, and a dev workflow section
- `uv sync && uv run pytest` succeeds
- `uv run <command-name> --help` returns 0 and prints the command tree
