"""Logs screen — points the user at Logfire for full traces, surfaces local log dir."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from vineyard.config import settings


class LogsScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Logs", classes="section-title")
        yield Static(
            f"Local data dir: {settings.data_dir}\n\n"
            "Open Logfire (https://logfire.pydantic.dev) for full traces, costs, and spans.",
            classes="muted",
        )
        yield Footer()
