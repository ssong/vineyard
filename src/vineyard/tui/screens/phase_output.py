"""Per-phase output viewer.

Markdown rendering for the content phases (PRD, design, spec) and a file
tree + viewer for the build phase. Reachable from the run detail screen
either by clicking a phase card or pressing ``v``.
"""

from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    DirectoryTree,
    Footer,
    Header,
    Markdown,
    Static,
)

from vineyard.models import (
    BuildOutput,
    DesignOutput,
    Phase,
    PhaseStatus,
    PRDAnalysisOutput,
    QAOutput,
    SpecOutput,
)
from vineyard.orchestrator import approve_checkpoint
from vineyard.storage import RunStore

_PHASE_MODEL: dict[Phase, type] = {
    Phase.PRD_ANALYSIS: PRDAnalysisOutput,
    Phase.DESIGN: DesignOutput,
    Phase.SPEC: SpecOutput,
}


class PhaseOutputScreen(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("a", "approve", "Approve"),
    ]

    def __init__(self, run_id: str, phase: Phase) -> None:
        super().__init__()
        self.run_id = run_id
        self.phase = phase

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self._title(), classes="section-title")
        store = RunStore()
        state = store.load(self.run_id)
        if state is None:
            yield Static("(run not found)", classes="muted")
            yield Footer()
            return

        status = state.phase_statuses.get(self.phase.value, PhaseStatus.PENDING.value)
        yield Static(f"Status: {status}", classes="muted")

        if self.phase == Phase.BUILD:
            yield from self._compose_build(state.output_dir / "build", state)
        else:
            yield Markdown(self._render_markdown(state), id="phase-md")

        yield Footer()

    def _title(self) -> str:
        return f"{self.phase.value.replace('_', ' ').upper()}  ·  press 'a' to approve · esc back"

    # ---- markdown phases ---------------------------------------------------

    def _render_markdown(self, state) -> str:
        raw = state.phase_outputs.get(self.phase.value)
        if raw is None:
            return f"# (no output yet for {self.phase.value})"

        model_cls = _PHASE_MODEL.get(self.phase)
        if model_cls is None:
            return f"# (unsupported phase: {self.phase.value})"

        output = raw if isinstance(raw, model_cls) else model_cls.model_validate(raw)

        if isinstance(output, PRDAnalysisOutput):
            return _render_prd(output)
        if isinstance(output, DesignOutput):
            return _render_design(output)
        if isinstance(output, SpecOutput):
            return _render_spec(output)
        return "# (no renderer for this phase)"

    # ---- build phase -------------------------------------------------------

    def _compose_build(self, build_dir: Path, state) -> ComposeResult:
        # Header summary (BuildOutput + QAOutput live in phase_outputs as a dict)
        raw = state.phase_outputs.get(Phase.BUILD.value) or {}
        summary_md = _render_build_summary(raw)
        yield Markdown(summary_md, id="build-summary")

        if not build_dir.exists():
            yield Static(
                f"(no files generated yet at {build_dir})",
                classes="muted",
            )
            return

        with Horizontal(id="build-layout"):
            yield DirectoryTree(str(build_dir), id="build-tree")
            with Vertical(id="build-pane"):
                yield Static("(select a file)", id="build-file-path", classes="muted")
                yield Static("", id="build-file-content")

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        path = Path(event.path)
        try:
            content = path.read_text()
        except Exception as exc:
            content = f"(could not read: {exc})"
        if len(content) > 40_000:
            content = content[:40_000] + "\n\n…(truncated)"
        self.query_one("#build-file-path", Static).update(str(path))
        self.query_one("#build-file-content", Static).update(content)

    # ---- approve -----------------------------------------------------------

    @work(exclusive=True, group="run")
    async def action_approve(self) -> None:
        store = RunStore()
        state = store.load(self.run_id)
        if state is None:
            self.notify("Run not found.", severity="error")
            return
        if state.phase_statuses.get(self.phase.value) != PhaseStatus.AWAITING_APPROVAL:
            self.notify(
                f"{self.phase.value} is not awaiting approval.", severity="warning"
            )
            return
        self.notify(f"Approving {self.phase.value}…", timeout=3)
        await approve_checkpoint(state, self.phase, store=store)
        self.app.pop_screen()


# ---------------------------------------------------------------------------
# Markdown composition helpers
# ---------------------------------------------------------------------------


def _render_prd(o: PRDAnalysisOutput) -> str:
    parts = [
        f"# PRD Analysis: {o.product_name}",
        "",
        o.product_summary,
        "",
        "## Core Problem",
        o.core_problem,
    ]
    if o.target_users:
        parts += ["", "## Target Users", *(f"- {u}" for u in o.target_users)]
    if o.mvp_scope_notes:
        parts += ["", "## MVP Scope Notes", o.mvp_scope_notes]
    if o.identified_gaps:
        parts += ["", "## Identified Gaps", *(f"- {g}" for g in o.identified_gaps)]
    if o.clarification_qa:
        parts += ["", "## Clarifications"]
        for qa in o.clarification_qa:
            parts += [f"**Q:** {qa.question}", f"**A:** {qa.answer}", ""]
    parts += ["", "---", "", "## Enriched PRD", "", o.enriched_prd_markdown]
    return "\n".join(parts)


def _render_design(o: DesignOutput) -> str:
    parts = ["# Design", "", o.prd_markdown]
    if o.features:
        parts += ["", "## Features"]
        for f in o.features:
            parts += [f"### [{f.priority}] {f.name}", "", f.description]
            if f.user_stories:
                parts += ["", "**User stories**", *(f"- {s}" for s in f.user_stories)]
            if f.acceptance_criteria:
                parts += [
                    "",
                    "**Acceptance criteria**",
                    *(f"- {c}" for c in f.acceptance_criteria),
                ]
            if f.technical_notes:
                parts += ["", f"_Notes:_ {f.technical_notes}"]
            parts += [""]
    if o.user_flows:
        parts += ["", "## User Flows"]
        for flow in o.user_flows:
            parts += [f"### {flow.name}"]
            parts += [f"{i + 1}. {step}" for i, step in enumerate(flow.steps)]
            parts += [""]
    return "\n".join(parts)


def _render_spec(o: SpecOutput) -> str:
    parts = [o.technical_spec_markdown]
    if o.api_endpoints:
        parts += ["", "## API Endpoints"]
        for e in o.api_endpoints:
            auth = "auth" if e.auth_required else "public"
            parts += [f"- `{e.method} {e.path}` ({auth}) — {e.description}"]
    if o.database_schema:
        parts += ["", "## Database Schema"]
        for t in o.database_schema:
            parts += [f"### `{t.name}`", t.description]
            for col in t.columns:
                null = "nullable" if col.nullable else "not null"
                parts += [f"- `{col.name}`: {col.type} ({null})"]
            if t.relationships:
                parts += ["**Relationships:** " + ", ".join(t.relationships)]
            parts += [""]
    if o.task_breakdown:
        parts += ["", "## Engineering Tasks"]
        for t in o.task_breakdown:
            parts += [f"### [{t.story_points}pt] {t.title}", t.description]
            if t.acceptance_criteria:
                parts += [
                    "**Acceptance**",
                    *(f"- {c}" for c in t.acceptance_criteria),
                ]
            if t.dependencies:
                parts += ["**Dependencies:** " + ", ".join(t.dependencies)]
            parts += [""]
    return "\n".join(parts)


def _render_build_summary(raw: dict | object) -> str:
    if not raw:
        return "# Build\n\n(no build output yet)"
    if isinstance(raw, dict):
        build_raw = raw.get("build")
        qa_raw = raw.get("qa")
    else:
        build_raw = getattr(raw, "build", None)
        qa_raw = getattr(raw, "qa", None)

    build = (
        build_raw
        if isinstance(build_raw, BuildOutput)
        else BuildOutput.model_validate(build_raw)
        if build_raw
        else None
    )
    qa = (
        qa_raw
        if isinstance(qa_raw, QAOutput)
        else QAOutput.model_validate(qa_raw)
        if qa_raw
        else None
    )

    parts = ["# Build"]
    if build is not None:
        parts += [
            "",
            f"**Files**: {len(build.files)} · **Cost**: ${build.cost_usd:.4f} · "
            f"**Grader**: {build.grader_result}",
            "",
            build.summary or "(no summary)",
        ]
        if build.grader_explanation:
            parts += ["", f"_Grader:_ {build.grader_explanation}"]
    if qa is not None:
        parts += ["", "## QA"]
        if qa.summary:
            parts += [qa.summary]
        if qa.issues_found:
            parts += [
                "",
                f"**Issues found ({len(qa.issues_found)})**",
                *(f"- {i}" for i in qa.issues_found),
            ]
        if qa.issues_fixed:
            parts += ["**Fixed**", *(f"- {i}" for i in qa.issues_fixed)]
        if qa.issues_unfixable:
            parts += [
                "**Unfixable**",
                *(f"- {i}" for i in qa.issues_unfixable),
            ]
    return "\n".join(parts)
