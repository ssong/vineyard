CLI tools don't have HTTP API endpoints — leave `api_endpoints` empty. Focus on:

- `database_schema`: SQLite tables for any persistent state. Include `id INTEGER PRIMARY KEY` and timestamps.
- `task_breakdown`: one engineering task per subcommand + supporting modules (storage, config, error handling)
- `technical_spec_markdown`: lay out the **command tree** (`tool <verb> <noun>` or `tool <verb>`), per-command flags, output format (text/JSON/table), exit codes, and where data lives on disk

Operational concerns: how does the user upgrade between versions? Does the schema migrate? Is there a `tool doctor` / `tool config` command for diagnostics?
