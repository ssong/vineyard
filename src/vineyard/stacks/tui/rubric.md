# Python TUI (Textual) Build Rubric

## Project setup

- `pyproject.toml` declares `textual>=0.80`, `typer>=0.12`, `pydantic-settings>=2`
- `requires-python = ">=3.12,<3.13"`
- `[project.scripts]` declares the entry point pointing at `<package>.cli:main`
- `.python-version` pins 3.12
- `.env.example` lists every env var

## Code quality

- One `App` subclass; `CSS_PATH = "theme.tcss"`
- Each `Screen` lives in its own file under `screens/`
- `BINDINGS` declared on the class with `Binding(key, action, description)`
- Long-running work uses `@work(exclusive=True, group=...)` so the UI stays responsive
- Modal flows use `ModalScreen[T]` returning a value via `dismiss(value)`
- Errors surface via `self.notify(..., severity="error")` — never raw `print` or uncaught exception

## Storage (when applicable)

- SQLite via stdlib `sqlite3` through a `storage.py` helper
- Default DB path under `Path.home() / ".<app>"` (or `XDG_CONFIG_HOME`)

## Tests

- Snapshot tests via `pytest-textual-snapshot`: at least one snapshot per `Screen`
- `tests/conftest.py` exposes any necessary fixtures (test DB, etc.)
- Snapshots live under `tests/__snapshots__/`

## Deliverables

- `README.md` documents: install, how to run the TUI, the keybindings, and dev workflow
- `uv sync && uv run pytest` succeeds (snapshot tests pass)
- `uv run <command-name>` launches the TUI without crashing on first paint
- `python -m <package>` is an equivalent entry point
