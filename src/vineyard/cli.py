"""Vineyard CLI — `vineyard` opens the TUI; subcommands provide non-interactive ops."""

import asyncio
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from vineyard.config import ExecutorName, StackName, settings
from vineyard.llm.logfire import configure_logfire
from vineyard.models import Handoff, PRDInput
from vineyard.orchestrator import create_run, restart_run, resume_run, run_factory
from vineyard.stacks import registry
from vineyard.storage import RunStore

app = typer.Typer(help="Vineyard — PRD → multi-stack codebase factory.", no_args_is_help=False)
console = Console()


@app.callback(invoke_without_command=True)
def _root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        from vineyard.tui import VineyardApp
        configure_logfire()
        VineyardApp().run()


@app.command()
def run(
    prd_path: Path = typer.Argument(..., exists=True, readable=True, help="Path to a PRD markdown file."),
    name: str = typer.Option(..., "--name", "-n", help="Product name."),
    stack: StackName = typer.Option(settings.default_stack, "--stack", "-s"),
    executor: ExecutorName = typer.Option(settings.build_executor, "--executor", "-e"),
    skip_approval: bool = typer.Option(False, "--yes", help="Auto-approve checkpoints."),
) -> None:
    """Run the factory non-interactively against a PRD file."""
    configure_logfire()
    profile = registry.get(stack)
    prd_text = prd_path.read_text()
    handoff = Handoff(
        handoff_id=str(uuid.uuid4()),
        triggered_at=datetime.now(UTC),
        triggered_by="cli",
        prd_input=PRDInput(name=name, slug=_slugify(name), prd_text=prd_text),
        build_preferences=profile.default_preferences(),
        executor=executor,
        approval_checkpoints=[] if skip_approval else ["design", "build"],
    )
    state = create_run(handoff)
    console.print(f"[bold green]Created run[/] {state.run_id}")
    final = asyncio.run(run_factory(state))
    console.print(f"[bold]Phase:[/] {final.current_phase.value} · cost ${final.cost_usd:.4f}")
    console.print(f"[bold]Output:[/] {final.output_dir}")


@app.command("list")
def list_runs() -> None:
    """List all runs."""
    store = RunStore()
    rows = store.list()
    if not rows:
        console.print("[dim]No runs yet — run `vineyard` to start one.[/]")
        return
    table = Table(title="Vineyard runs", show_lines=False)
    for col in ("ID", "Product", "Stack", "Phase", "Status", "Started", "Cost"):
        table.add_column(col)
    for row in rows:
        table.add_row(
            row["run_id"][:8],
            row["product_name"],
            row["stack"],
            row["current_phase"],
            row["status"],
            row["started_at"][:19].replace("T", " "),
            f"${row['cost_usd']:.4f}",
        )
    console.print(table)


@app.command()
def resume(run_id: str) -> None:
    """Resume a failed or paused run."""
    configure_logfire()
    state = asyncio.run(resume_run(run_id))
    if state is None:
        console.print(f"[red]No run found:[/] {run_id}")
        raise typer.Exit(code=1)
    console.print(f"[bold]Phase:[/] {state.current_phase.value} · cost ${state.cost_usd:.4f}")


@app.command()
def restart(
    run_id: str = typer.Argument(..., help="Full run ID or unique short prefix."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Wipe a run's phase outputs and re-run it from the first phase."""
    configure_logfire()
    store = RunStore()
    matches = [r for r in store.list() if r["run_id"].startswith(run_id)]
    if not matches:
        console.print(f"[red]No run found:[/] {run_id}")
        raise typer.Exit(code=1)
    if len(matches) > 1:
        console.print(f"[red]Ambiguous prefix[/] {run_id} matches {len(matches)} runs:")
        for m in matches:
            console.print(f"  {m['run_id'][:12]} · {m['product_name']}")
        raise typer.Exit(code=1)
    target = matches[0]
    full_id = target["run_id"]
    if not yes:
        typer.confirm(
            f"Restart run {full_id[:8]} ({target['product_name']})? "
            f"This wipes all phase outputs and the build directory.",
            abort=True,
        )
    state = asyncio.run(restart_run(full_id, store=store))
    if state is None:
        console.print(f"[red]No run found:[/] {full_id}")
        raise typer.Exit(code=1)
    console.print(f"[bold]Phase:[/] {state.current_phase.value} · cost ${state.cost_usd:.4f}")


@app.command()
def stacks() -> None:
    """List available stacks."""
    table = Table(title="Stacks")
    for col in ("Name", "Display", "Description", "Default DB", "Container"):
        table.add_column(col)
    for profile in registry.all():
        table.add_row(
            profile.name,
            profile.display_name,
            profile.description,
            profile.default_db,
            profile.container_image,
        )
    console.print(table)


@app.command()
def config(
    key: str | None = typer.Argument(None),
    value: str | None = typer.Argument(None),
) -> None:
    """Show or set Vineyard config (writes to ~/.vineyard/config.env)."""
    settings.ensure_dirs()
    config_path = settings.data_dir / "config.env"
    if key is None:
        if not config_path.exists():
            console.print("[dim](no config file yet)[/]")
            return
        console.print(config_path.read_text())
        return
    if value is None:
        console.print(f"[red]Provide a value:[/] vineyard config {key} <value>")
        raise typer.Exit(code=1)
    env_key = f"VINEYARD_{key.upper().replace('-', '_')}"
    lines = config_path.read_text().splitlines() if config_path.exists() else []
    lines = [ln for ln in lines if not ln.startswith(f"{env_key}=")]
    lines.append(f'{env_key}="{value}"')
    config_path.write_text("\n".join(lines) + "\n")
    config_path.chmod(0o600)
    console.print(f"[green]Set[/] {env_key}")


@app.command()
def delete(
    run_id: str = typer.Argument(..., help="Full run ID or unique short prefix."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Delete a run (DB row + on-disk output)."""
    store = RunStore()
    matches = [r for r in store.list() if r["run_id"].startswith(run_id)]
    if not matches:
        console.print(f"[red]No run found:[/] {run_id}")
        raise typer.Exit(code=1)
    if len(matches) > 1:
        console.print(f"[red]Ambiguous prefix[/] {run_id} matches {len(matches)} runs:")
        for m in matches:
            console.print(f"  {m['run_id'][:12]} · {m['product_name']}")
        raise typer.Exit(code=1)
    target = matches[0]
    full_id = target["run_id"]
    if not yes:
        typer.confirm(
            f"Delete run {full_id[:8]} ({target['product_name']})? "
            f"This removes the SQLite row and the output directory.",
            abort=True,
        )
    store.delete(full_id)
    console.print(f"[green]Deleted[/] {full_id[:8]} ({target['product_name']})")


@app.command()
def cost(
    run_id: str = typer.Argument(..., help="Full run ID or unique short prefix."),
) -> None:
    """Fetch authoritative gateway cost from Logfire for a run.

    Uses VINEYARD_LOGFIRE_READ_TOKEN — a separate read token created in your
    Logfire project (Project → Read tokens), not the write token used for
    sending traces.
    """
    if not settings.logfire_read_token:
        console.print("[red]VINEYARD_LOGFIRE_READ_TOKEN not set.[/]")
        console.print(
            "Create a Logfire read token (Project → Read tokens) and run:\n"
            "  vineyard config logfire-read-token pylf_v1_us_..."
        )
        raise typer.Exit(code=1)

    store = RunStore()
    matches = [r for r in store.list() if r["run_id"].startswith(run_id)]
    if not matches:
        console.print(f"[red]No run found:[/] {run_id}")
        raise typer.Exit(code=1)
    if len(matches) > 1:
        console.print(f"[red]Ambiguous prefix[/] {run_id} matches {len(matches)} runs:")
        for m in matches:
            console.print(f"  {m['run_id'][:12]} · {m['product_name']}")
        raise typer.Exit(code=1)
    full_id = matches[0]["run_id"]

    # Lazy import — keeps `vineyard --help` fast and avoids importing the query
    # client into every CLI invocation.
    from logfire.query_client import LogfireQueryClient, QueryExecutionError

    sql = f"""
        SELECT span_name, attributes, start_timestamp
        FROM records
        WHERE attributes->>'run_id' = '{full_id}'
        ORDER BY start_timestamp
    """

    try:
        with LogfireQueryClient(read_token=settings.logfire_read_token) as client:
            result = client.query_json_rows(sql=sql)
    except QueryExecutionError as exc:
        console.print(f"[red]Logfire query failed:[/] {exc}")
        raise typer.Exit(code=1) from exc

    rows = result.get("rows") or []
    if not rows:
        console.print(
            f"[yellow]No Logfire spans found for run {full_id[:8]}.[/]\n"
            "Did the run execute with VINEYARD_LOGFIRE_TOKEN set?"
        )
        return

    cost_keys = ("gen_ai.usage.cost", "gen_ai.usage.cost_usd", "cost", "cost_usd")
    in_keys = ("gen_ai.usage.input_tokens", "input_tokens", "request_tokens")
    out_keys = ("gen_ai.usage.output_tokens", "output_tokens", "response_tokens")

    table = Table(title=f"Logfire spans for run {full_id[:8]}")
    table.add_column("Span")
    table.add_column("Cost", justify="right")
    table.add_column("In", justify="right")
    table.add_column("Out", justify="right")

    total_cost = 0.0
    found_any_cost = False
    for row in rows:
        attrs = row.get("attributes") or {}
        cost_val = _first_attr(attrs, cost_keys)
        if cost_val is not None:
            found_any_cost = True
            total_cost += float(cost_val)
        in_val = _first_attr(attrs, in_keys) or 0
        out_val = _first_attr(attrs, out_keys) or 0
        table.add_row(
            row.get("span_name", "?"),
            f"${float(cost_val):.4f}" if cost_val is not None else "—",
            str(int(in_val)) if in_val else "—",
            str(int(out_val)) if out_val else "—",
        )

    console.print(table)

    if found_any_cost:
        console.print(f"\n[bold]Total cost (gateway-recorded):[/] ${total_cost:.4f}")
    else:
        console.print(
            "\n[yellow]No cost attribute found on any span.[/] "
            "The gateway may not have stamped one. Inspect the span attributes "
            "in Logfire and tell me the attribute name to wire it in."
        )


def _first_attr(attrs: dict, keys: tuple[str, ...]):
    for k in keys:
        if k in attrs and attrs[k] is not None:
            return attrs[k]
    return None


@app.command()
def open_output(run_id: str) -> None:
    """Print the output dir for a run."""
    store = RunStore()
    state = store.load(run_id)
    if state is None:
        console.print(f"[red]No run found:[/] {run_id}")
        raise typer.Exit(code=1)
    console.print(state.output_dir)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or f"run-{uuid.uuid4().hex[:6]}"


def main() -> None:
    app()


if __name__ == "__main__":
    main()
