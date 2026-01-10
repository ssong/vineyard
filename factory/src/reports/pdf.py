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


def _generate_research_enrichment_markdown(output: dict, opp_name: str) -> str:
    """Generate markdown for research enrichment output."""
    lines = [
        f"# Research Enrichment Report",
        f"## {opp_name}",
        "",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "---",
        "",
    ]

    # Positioning Statement
    if output.get("positioning_statement"):
        lines.extend([
            "## Positioning Statement",
            "",
            f"> {output['positioning_statement']}",
            "",
        ])

    # User Personas
    personas = output.get("personas", [])
    if personas:
        lines.extend([
            "## User Personas",
            "",
        ])

        primary = output.get("primary_persona", "")

        for persona in personas:
            is_primary = primary and primary.lower() in persona.get("name", "").lower()
            primary_badge = " **(Primary)**" if is_primary else ""

            lines.extend([
                f"### {persona.get('name', 'Unnamed')}{primary_badge}",
                f"**Role:** {persona.get('role', 'N/A')}",
                "",
                f"**Demographics:** {persona.get('demographics', 'N/A')}",
                "",
            ])

            if persona.get("goals"):
                lines.append("**Goals:**")
                for goal in persona["goals"]:
                    lines.append(f"- {goal}")
                lines.append("")

            if persona.get("frustrations"):
                lines.append("**Frustrations:**")
                for frustration in persona["frustrations"]:
                    lines.append(f"- {frustration}")
                lines.append("")

            if persona.get("jobs_to_be_done"):
                lines.append("**Jobs to be Done:**")
                for job in persona["jobs_to_be_done"]:
                    lines.append(f"- {job}")
                lines.append("")

            if persona.get("willingness_to_pay"):
                lines.append(f"**Willingness to Pay:** {persona['willingness_to_pay']}")
                lines.append("")

            if persona.get("acquisition_channels"):
                lines.append("**Acquisition Channels:** " + ", ".join(persona["acquisition_channels"]))
                lines.append("")

            lines.append("---")
            lines.append("")

    # Competitor Analysis
    competitors = output.get("competitor_matrix", [])
    if competitors:
        lines.extend([
            "## Competitive Analysis",
            "",
        ])

        for comp in competitors:
            lines.extend([
                f"### {comp.get('competitor_name', 'Unknown')}",
                f"**Website:** {comp.get('website', 'N/A')}",
                "",
            ])

            if comp.get("key_strengths"):
                lines.append("**Strengths:**")
                for strength in comp["key_strengths"]:
                    lines.append(f"- {strength}")
                lines.append("")

            if comp.get("key_gaps"):
                lines.append("**Gaps/Weaknesses:**")
                for gap in comp["key_gaps"]:
                    lines.append(f"- {gap}")
                lines.append("")

            if comp.get("review_summary"):
                lines.append(f"**Review Summary:** {comp['review_summary']}")
                lines.append("")

            # Pricing tiers
            pricing = comp.get("pricing_tiers", [])
            if pricing:
                lines.append("**Pricing:**")
                for tier in pricing:
                    if isinstance(tier, dict):
                        tier_name = tier.get("name", "Tier")
                        tier_price = tier.get("price", "N/A")
                        lines.append(f"- {tier_name}: {tier_price}")
                lines.append("")

            lines.append("---")
            lines.append("")

    # SEO Strategy
    seo = output.get("seo_strategy", {})
    if seo:
        lines.extend([
            "## SEO Strategy",
            "",
        ])

        if seo.get("primary_keywords"):
            lines.append("**Primary Keywords:**")
            for kw in seo["primary_keywords"]:
                if isinstance(kw, dict):
                    keyword = kw.get("keyword", kw.get("term", str(kw)))
                    volume = kw.get("volume", kw.get("search_volume", ""))
                    if volume:
                        lines.append(f"- {keyword} (volume: {volume})")
                    else:
                        lines.append(f"- {keyword}")
                else:
                    lines.append(f"- {kw}")
            lines.append("")

        if seo.get("long_tail_keywords"):
            lines.append("**Long-tail Keywords:**")
            for kw in seo["long_tail_keywords"][:10]:  # Limit to 10
                lines.append(f"- {kw}")
            lines.append("")

        if seo.get("content_opportunities"):
            lines.append("**Content Opportunities:**")
            for opp in seo["content_opportunities"]:
                lines.append(f"- {opp}")
            lines.append("")

        if seo.get("estimated_organic_potential"):
            lines.append(f"**Estimated Organic Potential:** {seo['estimated_organic_potential']}")
            lines.append("")

    # Miro link
    if output.get("competitive_landscape_miro_url"):
        lines.extend([
            "---",
            "",
            f"**Competitive Landscape Diagram:** [{output['competitive_landscape_miro_url']}]({output['competitive_landscape_miro_url']})",
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

    # User flows
    if output.get("user_flow_miro_url"):
        lines.extend([
            "---",
            "",
            f"**User Flow Diagram:** [{output['user_flow_miro_url']}]({output['user_flow_miro_url']})",
            "",
        ])

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
    opp_name = state.handoff.opportunity.name

    # Use phase-specific formatter if available
    if phase == Phase.RESEARCH_ENRICHMENT:
        return _generate_research_enrichment_markdown(output_dict, opp_name)
    elif phase == Phase.DESIGN:
        return _generate_design_markdown(output_dict, opp_name)
    else:
        return _generate_generic_markdown(output_dict, phase.value, opp_name)


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
    opp_name = state.handoff.opportunity.name
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{phase.value.replace('_', ' ').title()} Report - {opp_name}</title>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """

    # Generate PDF
    filename = f"{state.handoff.opportunity.slug}-{phase.value}-{state.execution_id[:8]}.pdf"
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
