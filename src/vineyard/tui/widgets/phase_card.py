"""Phase progress card."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from vineyard.models import Phase, PhaseStatus

_STATUS_LABEL = {
    PhaseStatus.PENDING: ("⏳", "pending", ""),
    PhaseStatus.IN_PROGRESS: ("🔄", "running", "running"),
    PhaseStatus.AWAITING_APPROVAL: ("⏸", "awaiting approval (press a)", "awaiting"),
    PhaseStatus.APPROVED: ("✓", "approved", ""),
    PhaseStatus.COMPLETED: ("✅", "completed", "completed"),
    PhaseStatus.FAILED: ("❌", "failed", "failed"),
}


class PhaseCard(Widget):
    DEFAULT_CLASSES = "phase-card"
    status: reactive[PhaseStatus] = reactive(PhaseStatus.PENDING)

    def __init__(self, *, phase: Phase, **kwargs) -> None:
        super().__init__(**kwargs)
        self.phase = phase

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static(self._label_text(), id=f"label-{self.phase.value}")

    def _label_text(self) -> str:
        emoji, label, _ = _STATUS_LABEL[self.status]
        return f"{emoji}  {self.phase.value.replace('_', ' ').upper():18}  {label}"

    def update_state(self, *, status: PhaseStatus) -> None:
        self.status = status
        for cls in ("running", "completed", "failed", "awaiting"):
            self.remove_class(cls)
        cls = _STATUS_LABEL[status][2]
        if cls:
            self.add_class(cls)
        try:
            self.query_one(f"#label-{self.phase.value}", Static).update(self._label_text())
        except Exception:
            pass
