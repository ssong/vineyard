Design as a CLI tool. Treat each `feature` as **a subcommand or subcommand group**:

- `name` is the command name (e.g. `sync`, `add`, `list`)
- `description` explains what the command does
- `user_stories` are framed as "As a user, I run `<cmd>` to..."
- `acceptance_criteria` cover exit codes, output format, error handling

User flows describe **terminal sessions** — sequences of commands the user runs to accomplish a task. Steps look like `$ tool init` / `$ tool add foo` / `$ tool list`.

`ui_copy` covers help strings, error messages, success messages, prompts (if any). Be specific — `"Database not initialized — run `tool init` first."`, not `"Error."`.
