"""Run detail screen — live phase progress, checkpoint approval, output access."""

from datetime import UTC, datetime

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, RichLog, Static

from vineyard.models import Phase, PhaseStatus, RunState
from vineyard.models.state import PHASE_ORDER
from vineyard.orchestrator import approve_checkpoint, restart_run, resume_run, run_factory
from vineyard.storage import RunStore
from vineyard.tui.screens.confirm import ConfirmScreen
from vineyard.tui.widgets.phase_card import PhaseCard

_KIND_STYLE = {
    "phase": "bold cyan",
    "agent": "magenta",
    "tool": "green",
    "error": "bold red",
}


class RunDetailScreen(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("v", "view", "View phase output"),
        Binding("a", "approve", "Approve checkpoint"),
        Binding("r", "resume", "Resume / retry"),
        Binding("x", "stop", "Stop"),
        Binding("R", "restart", "Restart"),
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
        yield RichLog(id="event-log", highlight=False, markup=True, wrap=True, max_lines=2000)
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
        await run_factory(
            state,
            store=store,
            on_progress=self._on_progress,
            on_event=self._on_event,
        )
        self._refresh()

    async def _on_progress(self, state: RunState, phase: Phase, status: PhaseStatus) -> None:
        self._state = state
        card = self.query_one(f"#card-{phase.value}", PhaseCard)
        card.update_state(status=status)
        self.query_one("#footer-status", Static).update(
            f"Cost so far: ${state.cost_usd:.4f} · Output: {state.output_dir}"
        )

        if status == PhaseStatus.AWAITING_CLARIFICATION:
            self._prompt_for_clarifications(phase)

    def _prompt_for_clarifications(self, phase: Phase) -> None:
        # If this run detail screen is on top, jump straight into the answer
        # form so the user can't miss it. Otherwise floats a toast above
        # whatever screen they're on.
        from vineyard.tui.screens.phase_output import PhaseOutputScreen

        if self.app.screen is self:
            self.app.push_screen(PhaseOutputScreen(self.run_id, phase))
            return
        self.app.notify(
            f"{phase.value} needs answers — open run {self.run_id[:8]}",
            title="Vineyard · clarifications pending",
            severity="warning",
            timeout=10,
        )

    def _on_event(self, kind: str, text: str) -> None:
        try:
            log = self.query_one("#event-log", RichLog)
        except Exception:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        style = _KIND_STYLE.get(kind, "white")
        log.write(f"[dim]{ts}[/] [{style}]{kind:>5}[/] {text}")

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
        await approve_checkpoint(
            state,
            phase,
            store=store,
            on_progress=self._on_progress,
            on_event=self._on_event,
        )
        self._refresh()

    @work(exclusive=True, group="run")
    async def action_resume(self) -> None:
        store = RunStore()
        state = store.load(self.run_id)
        if state is None:
            self.notify("Run not found.", severity="error")
            return
        status = state.phase_statuses.get(state.current_phase.value)
        if status == PhaseStatus.IN_PROGRESS:
            self.notify("Run is already in progress.", severity="warning")
            return
        if status == PhaseStatus.AWAITING_APPROVAL:
            self.notify("Press 'a' to approve the pending checkpoint.", severity="warning")
            return
        if status == PhaseStatus.AWAITING_CLARIFICATION:
            self.notify(
                "Phase has unanswered clarifying questions — press 'v' to open and answer them.",
                severity="warning",
            )
            return
        self.notify(f"Resuming from {state.current_phase.value} ({status})…", timeout=3)
        self._on_event("phase", f"resume from {state.current_phase.value}")
        await resume_run(
            self.run_id,
            store=store,
            on_progress=self._on_progress,
            on_event=self._on_event,
        )
        self._refresh()

    def action_open_output(self) -> None:
        if self._state is None:
            return
        path = self._state.output_dir
        self.notify(f"Output dir: {path}", timeout=5)

    def action_view(self) -> None:
        state = self._state or RunStore().load(self.run_id)
        if state is None:
            return
        from vineyard.tui.screens.phase_output import PhaseOutputScreen
        self.app.push_screen(PhaseOutputScreen(self.run_id, state.current_phase))

    def on_phase_card_selected(self, event: PhaseCard.Selected) -> None:
        from vineyard.tui.screens.phase_output import PhaseOutputScreen
        self.app.push_screen(PhaseOutputScreen(self.run_id, event.phase))

    def action_stop(self) -> None:
        store = RunStore()
        state = store.load(self.run_id)
        if state is None:
            return
        status = state.phase_statuses.get(state.current_phase.value)
        if status != PhaseStatus.IN_PROGRESS.value:
            self.notify("Nothing to stop — no phase is running.", severity="warning")
            return

        def _on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            self._do_stop()

        self.app.push_screen(
            ConfirmScreen(f"Stop {state.current_phase.value}? You can resume later."),
            _on_confirm,
        )

    def _do_stop(self) -> None:
        # Cancel any running 'run' workers on this screen.
        for worker in list(self.workers):
            if worker.group == "run":
                worker.cancel()

        store = RunStore()
        state = store.load(self.run_id)
        if state is None:
            return
        if state.phase_statuses.get(state.current_phase.value) == PhaseStatus.IN_PROGRESS.value:
            state.update_phase_status(state.current_phase, PhaseStatus.FAILED)
            state.errors.append({
                "phase": state.current_phase.value,
                "error": "Stopped by user",
                "timestamp": datetime.now(UTC).isoformat(),
            })
            store.save(state)
        self._on_event("error", f"{state.current_phase.value} stopped by user")
        self.notify("Run stopped. Press 'r' to resume from this phase.", timeout=4)
        self._refresh()

    def action_restart(self) -> None:
        store = RunStore()
        state = store.load(self.run_id)
        if state is None:
            return

        def _on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            self._do_restart()

        self.app.push_screen(
            ConfirmScreen(
                f"Restart from prd_analysis? This wipes phase outputs and "
                f"the build dir for {self.run_id[:8]}."
            ),
            _on_confirm,
        )

    @work(exclusive=True, group="run")
    async def _do_restart(self) -> None:
        # `exclusive=True` cancels any prior 'run' worker before this one starts.
        self._on_event("phase", "restart requested by user")
        await restart_run(
            self.run_id,
            on_progress=self._on_progress,
            on_event=self._on_event,
        )
        self._refresh()
