Frame the product as a **terminal command-line tool** — single-user, local-first. Out of scope: web UI, mobile, server. In scope: subcommands, flags, stdin/stdout flows, optional local data store (SQLite), config via env/file.

When identifying gaps, focus on: top-level subcommand surface, what the user runs day-to-day, where persistent state lives (or whether the tool is stateless), expected scriptability (machine-readable output formats?), and whether interactive prompts are acceptable or everything must be flag-driven.
