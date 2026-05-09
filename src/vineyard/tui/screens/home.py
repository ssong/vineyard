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
    BINDINGS = [Binding("r", "refresh", "Refresh")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            "Runs (n: new · enter or click to open · r: refresh)",
            classes="section-title",
        )
        yield Container(DataTable(id="run-table"))
        yield Static("", id="empty-msg", classes="muted")
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
        empty: Static = self.query_one("#empty-msg", Static)
        table.clear()
        if not rows:
            empty.update("(no runs yet — press n to create one)")
            return
        empty.update("")
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
                key=row["run_id"],
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        run_id = getattr(event.row_key, "value", None) or str(event.row_key)
        if not run_id:
            return
        from vineyard.tui.screens.run_detail import RunDetailScreen
        self.app.push_screen(RunDetailScreen(run_id))
