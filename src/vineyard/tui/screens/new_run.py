"""New-run screen — collect PRD + stack pick + executor toggle."""

import re
import uuid
from datetime import datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static, Switch, TextArea

from vineyard.config import StackName, settings
from vineyard.models import Handoff, PRDInput
from vineyard.orchestrator.runner import create_run, run_factory
from vineyard.stacks import registry


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or f"run-{uuid.uuid4().hex[:6]}"


class NewRunScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("New run · esc to go back", classes="section-title")
        with Vertical(id="new-run-form"):
            yield Label("Product name")
            yield Input(placeholder="e.g. Bandung CRM", id="name")

            yield Label("Stack")
            yield Select(
                [(profile.display_name, profile.name) for profile in registry.all()],
                id="stack",
                value=settings.default_stack,
            )

            yield Label("Build executor")
            yield Switch(id="executor-toggle", value=settings.build_executor == "managed_agents")
            yield Static("on = Managed Agents · off = local Claude Agent SDK", classes="muted")

            yield Label("PRD")
            yield TextArea("", id="prd", language="markdown")

            yield Button("Start run", variant="primary", id="start")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "start":
            return
        name = (self.query_one("#name", Input).value or "").strip()
        prd_text = (self.query_one("#prd", TextArea).text or "").strip()
        stack: StackName = self.query_one("#stack", Select).value  # type: ignore[assignment]
        executor = "managed_agents" if self.query_one("#executor-toggle", Switch).value else "local_sdk"

        if not name or not prd_text:
            self.notify("Provide a product name and PRD before starting.", severity="warning")
            return

        profile = registry.get(stack)
        prefs = profile.default_preferences()
        handoff = Handoff(
            handoff_id=str(uuid.uuid4()),
            triggered_at=datetime.utcnow(),
            triggered_by="local",
            prd_input=PRDInput(name=name, slug=_slugify(name), prd_text=prd_text),
            build_preferences=prefs,
            executor=executor,
        )
        state = create_run(handoff)
        self.app.pop_screen()
        from vineyard.tui.screens.run_detail import RunDetailScreen
        self.app.push_screen(RunDetailScreen(state.run_id, autostart=True))
