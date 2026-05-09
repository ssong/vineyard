"""Run detail screen — live phase progress, checkpoint approval, output access."""

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from vineyard.models import Phase, PhaseStatus, RunState
from vineyard.models.state import PHASE_ORDER
from vineyard.orchestrator import approve_checkpoint, run_factory
from vineyard.storage import RunStore
from vineyard.tui.widgets.phase_card import PhaseCard


class RunDetailScreen(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("a", "approve", "Approve checkpoint"),
        Binding("o", "open_output", "Open output dir"),
    ]

    def __init__(self, run_id: str, autostart: bool = False):
        super().__init__()
        self.run_id = run_id
        self.autostart = autostart
        self._state: RunState | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self._title(), id="title", classes="section-title")
        with Vertical(id="phases"):
            for phase in PHASE_ORDER:
                yield PhaseCard(phase=phase, id=f"card-{phase.value}")
        yield Static("", id="footer-status", classes="muted")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()
        if self.autostart:
            self._kick_off()

    def _title(self) -> str:
        store = RunStore()
        state = store.load(self.run_id)
        if state is None:
            return f"Run {self.run_id[:8]} (missing)"
        return f"{state.handoff.prd_input.name} · {state.handoff.build_preferences.stack} · {self.run_id[:8]}"

    def _refresh(self) -> None:
        store = RunStore()
        state = store.load(self.run_id)
        if state is None:
            return
        self._state = state
        self.query_one("#title", Static).update(self._title())
        for phase in PHASE_ORDER:
            card = self.query_one(f"#card-{phase.value}", PhaseCard)
            status_str = state.phase_statuses.get(phase.value, PhaseStatus.PENDING.value)
            status = PhaseStatus(status_str) if isinstance(status_str, str) else status_str
            card.update_state(status=status)
        self.query_one("#footer-status", Static).update(
            f"Cost so far: ${state.cost_usd:.4f} · Output: {state.output_dir}"
        )

    @work(exclusive=True, group="run")
    async def _kick_off(self) -> None:
        store = RunStore()
        state = store.load(self.run_id)
        if state is None:
            return
        await run_factory(state, store=store, on_progress=self._on_progress)
        self._refresh()

    async def _on_progress(self, state: RunState, phase: Phase, status: PhaseStatus) -> None:
        self._state = state
        card = self.query_one(f"#card-{phase.value}", PhaseCard)
        card.update_state(status=status)
        self.query_one("#footer-status", Static).update(
            f"Cost so far: ${state.cost_usd:.4f} · Output: {state.output_dir}"
        )

    @work(exclusive=True, group="run")
    async def action_approve(self) -> None:
        store = RunStore()
        state = store.load(self.run_id)
        if state is None:
            return
        phase = state.current_phase
        if state.phase_statuses.get(phase.value) != PhaseStatus.AWAITING_APPROVAL:
            self.notify("No checkpoint awaiting approval.", severity="warning")
            return
        await approve_checkpoint(state, phase, store=store, on_progress=self._on_progress)
        self._refresh()

    def action_open_output(self) -> None:
        if self._state is None:
            return
        path = self._state.output_dir
        self.notify(f"Output dir: {path}", timeout=5)
