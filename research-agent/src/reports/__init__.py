"""Reports package."""

from .generator import generate_markdown_report
from .pdf import generate_pdf

__all__ = ["generate_markdown_report", "generate_pdf"]
