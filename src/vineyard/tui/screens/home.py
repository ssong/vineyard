"""Run list screen."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from vineyard.models import PhaseStatus
from vineyard.storage import RunStore
from vineyard.tui.screens.confirm import ConfirmScreen

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
        Binding("r", "refresh", "Refresh"),
        Binding("d", "delete", "Delete"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            "Runs (n: new · enter to open · d: delete · r: refresh)",
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

    def action_delete(self) -> None:
        table: DataTable = self.query_one("#run-table", DataTable)
        if table.row_count == 0:
            return
        try:
            cell_key = table.coordinate_to_cell_key(table.cursor_coordinate)
        except Exception:
            return
        run_id = getattr(cell_key.row_key, "value", None)
        if not run_id:
            return

        store = RunStore()
        rows = [r for r in store.list() if r["run_id"] == run_id]
        product = rows[0]["product_name"] if rows else "(unknown)"

        def _on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            store.delete(run_id)
            self.notify(f"Deleted {run_id[:8]} ({product})", timeout=4)
            self.action_refresh()

        self.app.push_screen(
            ConfirmScreen(f"Delete run {run_id[:8]} ({product})?"),
            _on_confirm,
        )
