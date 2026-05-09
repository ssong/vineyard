Generate a runnable Textual TUI package. Required files:

- `pyproject.toml` with `[project.scripts]` mapping the entry command to `<package>.cli:main`
- `src/<package>/cli.py` — Typer entry that constructs the `App` and calls `.run()`
- `src/<package>/__main__.py` so `python -m <package>` also works
- `src/<package>/app.py` — the `App` subclass with `CSS_PATH = "theme.tcss"`
- `src/<package>/screens/<name>.py` — one `Screen` per file
- `src/<package>/widgets/<name>.py` — only if a custom widget is needed
- `src/<package>/theme.tcss` — global styles
- `tests/conftest.py` and snapshot tests under `tests/test_<screen>.py`
- `README.md` documenting install, how to run, keybindings, dev workflow

Every `Screen` has explicit `BINDINGS`; every long-running action uses
`@work(exclusive=True, group=...)`; every error path calls
`self.notify(..., severity="error")` instead of raising uncaught.

Snapshot tests must use `snap_compare` from `pytest-textual-snapshot`. Initial
snapshots are generated automatically on first run; commit the resulting
`tests/__snapshots__/` directory.
