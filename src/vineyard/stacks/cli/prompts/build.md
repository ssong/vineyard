Generate a runnable CLI package. Required files:

- `pyproject.toml` with `[project.scripts]` mapping the CLI command to `<package>.cli:main`
- `src/<package>/cli.py` with a Typer app and a `main()` function that calls `app()`
- `src/<package>/__main__.py` so `python -m <package>` also works
- `src/<package>/commands/<verb>.py` for each subcommand or subcommand group
- `tests/conftest.py` exposing a `CliRunner` fixture
- A test file per subcommand using `runner.invoke(app, [...])`
- `README.md` with install / usage / dev sections

Every command parameter must have a `help=` string. Every error path must
exit non-zero with a clear Rich-rendered message — never let an uncaught
exception bubble out to the user.
