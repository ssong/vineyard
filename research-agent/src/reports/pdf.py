"""PDF generation from markdown."""

import logging
import os
from pathlib import Path

import markdown
from weasyprint import CSS, HTML

logger = logging.getLogger(__name__)

# Ensure outputs directory exists
OUTPUTS_DIR = Path(__file__).parent.parent.parent / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

# PDF styling
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

@page {
    size: A4;
    margin: 2cm;
}

@page:first {
    margin-top: 1cm;
}
"""


def generate_pdf(markdown_content: str, report_id: str) -> str:
    """
    Convert markdown to styled PDF.

    Args:
        markdown_content: Markdown string to convert
        report_id: Report ID for filename

    Returns:
        Path to generated PDF file
    """
    # Convert markdown to HTML
    html_content = markdown.markdown(
        markdown_content,
        extensions=["tables", "fenced_code"],
    )

    # Wrap in HTML document
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Research Report</title>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """

    # Generate PDF
    output_path = OUTPUTS_DIR / f"research-report-{report_id[:8]}.pdf"

    try:
        html = HTML(string=full_html)
        css = CSS(string=PDF_CSS)
        html.write_pdf(output_path, stylesheets=[css])

        logger.info(f"Generated PDF: {output_path}")
        return str(output_path)

    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        # Fallback: save as markdown
        fallback_path = OUTPUTS_DIR / f"research-report-{report_id[:8]}.md"
        with open(fallback_path, "w") as f:
            f.write(markdown_content)
        logger.info(f"Saved markdown fallback: {fallback_path}")
        return str(fallback_path)
