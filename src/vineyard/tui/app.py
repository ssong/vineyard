"""Vineyard Textual application root."""

from textual.app import App
from textual.binding import Binding

from vineyard.tui.screens.home import HomeScreen


class VineyardApp(App):
    CSS_PATH = "theme.tcss"
    TITLE = "Vineyard"
    SUB_TITLE = "PRD → codebase"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("n", "new_run", "New run"),
        Binding("?", "help", "Help"),
    ]

    def on_mount(self) -> None:
        self.push_screen(HomeScreen())

    def action_new_run(self) -> None:
        from vineyard.tui.screens.new_run import NewRunScreen
        self.push_screen(NewRunScreen())

    def action_help(self) -> None:
        self.notify(
            "n: new run · enter: open run · a: approve checkpoint · q: quit",
            title="Vineyard",
            timeout=6,
        )
