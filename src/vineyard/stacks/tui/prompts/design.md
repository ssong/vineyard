Design as a TUI app. Treat each `feature` as **a screen or screen group**:

- `name` is the screen name (e.g. `HomeScreen`, `DetailScreen`)
- `description` explains what the user sees and does there
- `user_stories` are framed as "As a user, on the X screen, I press Y to..."
- `acceptance_criteria` cover keybindings, visible widgets, transitions to other screens

User flows describe **screen-level navigation paths** — sequences like "user opens app → HomeScreen → press n → NewItemScreen → fill form → submit → back to HomeScreen with new item highlighted". Steps reference keybindings and screen transitions, not URLs.

`ui_copy` covers static text rendered in widgets: section titles, button labels, empty-state messages, error toasts, help text. Be specific.
