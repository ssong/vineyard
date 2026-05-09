TUI apps don't have HTTP API endpoints — leave `api_endpoints` empty. Focus on:

- `database_schema`: SQLite tables for any persistent state. Include `id INTEGER PRIMARY KEY` and timestamps.
- `task_breakdown`: one engineering task per Screen + supporting modules (custom widgets, storage, config). Treat the App class as its own task.
- `technical_spec_markdown`: lay out the **screen graph** (which screens exist, what pushes/pops them), per-screen widgets and bindings, the data model, and the file layout.

Operational concerns: terminal compatibility, color theme, mouse support, accessibility (screen readers don't read TUIs well — flag that), packaging (will users install via `uv tool install` or `pipx`?).
