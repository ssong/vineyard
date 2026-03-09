"""PDF generation for factory phase outputs."""

import logging
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import markdown
from weasyprint import CSS, HTML

from src.models import FactoryState, Phase

logger = logging.getLogger(__name__)

# Ensure outputs directory exists
OUTPUTS_DIR = Path(__file__).parent.parent.parent / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

# PDF styling (same as research-agent for consistency)
PDF_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #1a1a1a;
    max-width: 800px;
    margin: 0 auto;
    padding: 40px;
}

h1 {
    font-size: 24pt;
    font-weight: 700;
    color: #111;
    border-bottom: 3px solid #4f46e5;
    padding-bottom: 10px;
    margin-bottom: 20px;
}

h2 {
    font-size: 18pt;
    font-weight: 600;
    color: #1a1a1a;
    margin-top: 30px;
    margin-bottom: 15px;
}

h3 {
    font-size: 14pt;
    font-weight: 600;
    color: #4f46e5;
    margin-top: 25px;
    margin-bottom: 10px;
}

h4 {
    font-size: 12pt;
    font-weight: 600;
    color: #333;
    margin-top: 20px;
    margin-bottom: 8px;
}

hr {
    border: none;
    border-top: 1px solid #e5e5e5;
    margin: 25px 0;
}

blockquote {
    background: #f8f9fa;
    border-left: 4px solid #4f46e5;
    padding: 12px 20px;
    margin: 15px 0;
    font-style: italic;
    color: #555;
}

strong {
    font-weight: 600;
}

ul, ol {
    margin: 10px 0;
    padding-left: 25px;
}

li {
    margin: 5px 0;
}

code {
    background: #f1f1f1;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: 'SF Mono', Monaco, monospace;
    font-size: 10pt;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 15px 0;
}

th, td {
    border: 1px solid #ddd;
    padding: 8px 12px;
    text-align: left;
}

th {
    background: #f5f5f5;
    font-weight: 600;
}

.meta {
    color: #666;
    font-size: 10pt;
    margin-bottom: 20px;
}

@page {
    size: A4;
    margin: 2cm;
}

@page:first {
    margin-top: 1cm;
}
"""


def _to_dict(obj: Any) -> Any:
    """Convert dataclass or nested structure to dict."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    elif hasattr(obj, "model_dump"):
        return obj.model_dump()
    elif hasattr(obj, "dict"):
        return obj.dict()
    elif isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_to_dict(v) for v in obj]
    return obj


def _generate_prd_analysis_markdown(output: dict, product_name: str) -> str:
    """Generate markdown for PRD analysis output."""
    lines = [
        f"# PRD Analysis Report",
        f"## {product_name}",
        "",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "---",
        "",
    ]

    # Product Summary
    if output.get("product_summary"):
        lines.extend([
            "## Product Summary",
            "",
            output["product_summary"],
            "",
        ])

    # Core Problem
    if output.get("core_problem"):
        lines.extend([
            "## Core Problem",
            "",
            output["core_problem"],
            "",
        ])

    # Target Users
    target_users = output.get("target_users", [])
    if target_users:
        lines.extend(["## Target Users", ""])
        for user in target_users:
            lines.append(f"- {user}")
        lines.append("")

    # Identified Gaps
    gaps = output.get("identified_gaps", [])
    if gaps:
        lines.extend(["## Identified Gaps", ""])
        for gap in gaps:
            lines.append(f"- {gap}")
        lines.append("")

    # Q&A
    qa = output.get("clarification_qa", [])
    if qa:
        lines.extend(["## Clarification Q&A", ""])
        for pair in qa:
            lines.append(f"**Q:** {pair.get('question', '')}")
            lines.append(f"**A:** {pair.get('answer', '')}")
            lines.append("")

    # MVP Scope Notes
    if output.get("mvp_scope_notes"):
        lines.extend([
            "## MVP Scope Notes",
            "",
            output["mvp_scope_notes"],
            "",
        ])

    # Enriched PRD
    if output.get("enriched_prd_markdown"):
        lines.extend([
            "---",
            "",
            "## Enriched PRD",
            "",
            output["enriched_prd_markdown"],
            "",
        ])

    return "\n".join(lines)


def _generate_design_markdown(output: dict, opp_name: str) -> str:
    """Generate markdown for design output."""
    lines = [
        f"# Design Phase Report",
        f"## {opp_name}",
        "",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "---",
        "",
    ]

    # PRD content (if it's markdown, include it)
    if output.get("prd_markdown"):
        lines.extend([
            "## Product Requirements Document",
            "",
            output["prd_markdown"],
            "",
        ])

    # Features
    features = output.get("features", [])
    if features:
        lines.extend([
            "## Features",
            "",
        ])

        for feature in features:
            priority = feature.get("priority", "")
            lines.extend([
                f"### {feature.get('name', 'Feature')} ({priority})",
                "",
                feature.get("description", ""),
                "",
            ])

            if feature.get("user_stories"):
                lines.append("**User Stories:**")
                for story in feature["user_stories"]:
                    lines.append(f"- {story}")
                lines.append("")

            if feature.get("acceptance_criteria"):
                lines.append("**Acceptance Criteria:**")
                for ac in feature["acceptance_criteria"]:
                    lines.append(f"- {ac}")
                lines.append("")

    return "\n".join(lines)


def _generate_generic_markdown(output: dict, phase_name: str, opp_name: str) -> str:
    """Generate generic markdown for any phase output."""
    lines = [
        f"# {phase_name.replace('_', ' ').title()} Phase Report",
        f"## {opp_name}",
        "",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "---",
        "",
    ]

    def format_value(value: Any, indent: int = 0) -> list[str]:
        """Format a value as markdown lines."""
        prefix = "  " * indent
        result = []

        if isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, (dict, list)):
                    result.append(f"{prefix}**{k}:**")
                    result.extend(format_value(v, indent + 1))
                else:
                    result.append(f"{prefix}**{k}:** {v}")
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    result.extend(format_value(item, indent))
                    result.append("")
                else:
                    result.append(f"{prefix}- {item}")
        else:
            result.append(f"{prefix}{value}")

        return result

    for key, value in output.items():
        if key in ("linear_issues",):  # Skip internal fields
            continue

        display_key = key.replace("_", " ").title()
        lines.append(f"## {display_key}")
        lines.append("")
        lines.extend(format_value(value))
        lines.append("")

    return "\n".join(lines)


def generate_phase_markdown(state: FactoryState, phase: Phase) -> Optional[str]:
    """
    Generate markdown content for a phase's output.

    Args:
        state: Current factory state
        phase: Phase to generate report for

    Returns:
        Markdown string or None if no output available
    """
    output = state.phase_outputs.get(phase.value)
    if not output:
        return None

    output_dict = _to_dict(output)
    product_name = state.handoff.prd_input.name

    # Use phase-specific formatter if available
    if phase == Phase.PRD_ANALYSIS:
        return _generate_prd_analysis_markdown(output_dict, product_name)
    elif phase == Phase.DESIGN:
        return _generate_design_markdown(output_dict, product_name)
    else:
        return _generate_generic_markdown(output_dict, phase.value, product_name)


def generate_phase_report_pdf(state: FactoryState, phase: Phase) -> Optional[str]:
    """
    Generate a PDF report for a phase's output.

    Args:
        state: Current factory state
        phase: Phase to generate report for

    Returns:
        Path to generated PDF file, or None if generation failed
    """
    markdown_content = generate_phase_markdown(state, phase)
    if not markdown_content:
        logger.warning(f"No output available for phase {phase.value}")
        return None

    # Convert markdown to HTML
    html_content = markdown.markdown(
        markdown_content,
        extensions=["tables", "fenced_code"],
    )

    # Wrap in HTML document
    product_name = state.handoff.prd_input.name
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{phase.value.replace('_', ' ').title()} Report - {product_name}</title>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """

    # Generate PDF
    filename = f"{state.handoff.prd_input.slug}-{phase.value}-{state.execution_id[:8]}.pdf"
    output_path = OUTPUTS_DIR / filename

    try:
        html = HTML(string=full_html)
        css = CSS(string=PDF_CSS)
        html.write_pdf(output_path, stylesheets=[css])

        logger.info(f"Generated PDF: {output_path}")
        return str(output_path)

    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        # Fallback: save as markdown
        fallback_path = OUTPUTS_DIR / filename.replace(".pdf", ".md")
        with open(fallback_path, "w") as f:
            f.write(markdown_content)
        logger.info(f"Saved markdown fallback: {fallback_path}")
        return str(fallback_path)
