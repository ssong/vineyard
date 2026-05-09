"""Run list screen."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from vineyard.models import PhaseStatus
from vineyard.storage import RunStore

_STATUS_EMOJI = {
    PhaseStatus.PENDING.value: "⏳",
    PhaseStatus.IN_PROGRESS.value: "🔄",
    PhaseStatus.AWAITING_APPROVAL.value: "⏸",
    PhaseStatus.APPROVED.value: "✓",
    PhaseStatus.COMPLETED.value: "✅",
    PhaseStatus.FAILED.value: "❌",
}


class HomeScreen(Screen):
    BINDINGS = [
        Binding("enter", "open_selected", "Open"),
        Binding("r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("Runs (n: new · enter: open · r: refresh)", classes="section-title")
        yield Container(DataTable(id="run-table"))
        yield Footer()

    def on_mount(self) -> None:
        table: DataTable = self.query_one("#run-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Status", "Product", "Stack", "Phase", "Started", "Cost", "ID")
        self.action_refresh()

    def action_refresh(self) -> None:
        store = RunStore()
        rows = store.list()
        table: DataTable = self.query_one("#run-table", DataTable)
        table.clear()
        if not rows:
            table.add_row("—", "(no runs yet — press n to create one)", "—", "—", "—", "—", "—")
            return
        for row in rows:
            emoji = _STATUS_EMOJI.get(row["status"], "·")
            table.add_row(
                f"{emoji} {row['status']}",
                row["product_name"],
                row["stack"],
                row["current_phase"],
                row["started_at"][:19].replace("T", " "),
                f"${row['cost_usd']:.4f}",
                row["run_id"][:8],
            )

    def action_open_selected(self) -> None:
        table: DataTable = self.query_one("#run-table", DataTable)
        if table.row_count == 0:
            return
        try:
            row = table.get_row_at(table.cursor_row)
        except Exception:
            return
        run_id_short = row[-1]
        store = RunStore()
        for entry in store.list():
            if entry["run_id"].startswith(run_id_short):
                from vineyard.tui.screens.run_detail import RunDetailScreen
                self.app.push_screen(RunDetailScreen(entry["run_id"]))
                return
