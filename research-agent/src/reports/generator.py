"""Markdown report generator."""

from datetime import datetime

from src.models import ResearchReport


def generate_markdown_report(report: ResearchReport) -> str:
    """
    Generate a markdown report from ResearchReport.

    Args:
        report: The research report to convert

    Returns:
        Markdown string
    """
    sections = []

    # Header
    sections.append(f"# Micro-SaaS Research Report")
    sections.append(f"\n**Generated:** {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}")
    sections.append(f"**Duration:** {report.research_duration_seconds} seconds")
    sections.append(f"**Report ID:** {report.report_id[:8]}")

    # Executive Summary
    sections.append("\n---\n")
    sections.append("## Executive Summary\n")
    sections.append(report.executive_summary)

    # Top Opportunities
    sections.append("\n---\n")
    sections.append("## Top Opportunities\n")

    for i, opp_report in enumerate(report.opportunities, 1):
        opp = opp_report.opportunity
        forecast = opp_report.forecast
        validation = opp_report.validation

        sections.append(f"### {i}. {opp.name}")
        sections.append(f"\n**Score:** {opp.overall_score}/100 | "
                       f"**4U Score:** {opp.four_u_score}/100")
        sections.append(f"\n> {opp.one_liner}\n")

        # Details
        sections.append(f"**Problem:** {opp.problem_statement}\n")
        sections.append(f"**Target:** {opp.target_market_description}\n")
        sections.append(f"**Category:** {opp.category.value.replace('_', ' ').title()}\n")
        sections.append(f"**Business Model:** {opp.business_model.value.replace('_', ' ').title()}\n")

        # Pricing
        sections.append(f"\n**Suggested Pricing:**")
        sections.append(f"- Low: ${opp.suggested_price_low/100:.0f}/mo")
        sections.append(f"- Mid: ${opp.suggested_price_mid/100:.0f}/mo")
        sections.append(f"- High: ${opp.suggested_price_high/100:.0f}/mo\n")

        # Revenue Forecast
        sections.append(f"**Revenue Forecast (12 months):**")
        sections.append(f"- Conservative: ${forecast.mrr_month_12_conservative/100:,.0f}/mo")
        sections.append(f"- Moderate: ${forecast.mrr_month_12_moderate/100:,.0f}/mo")
        sections.append(f"- Optimistic: ${forecast.mrr_month_12_optimistic/100:,.0f}/mo\n")

        # Build Assessment
        sections.append(f"**Build Assessment:**")
        sections.append(f"- Complexity: {opp.build_complexity.title()}")
        sections.append(f"- Estimated Time: {opp.estimated_build_weeks} weeks")
        sections.append(f"- Solo Viability: {opp.solo_viability_score}/100\n")

        # Validation Details
        sections.append(f"**4U Framework Breakdown:**")
        sections.append(f"- Unworkable: {validation.four_u_result.unworkable_score}/25")
        sections.append(f"- Unavoidable: {validation.four_u_result.unavoidable_score}/25")
        sections.append(f"- Urgent: {validation.four_u_result.urgent_score}/25")
        sections.append(f"- Underserved: {validation.four_u_result.underserved_score}/25\n")

        # Risks and Opportunities
        if validation.key_risks:
            sections.append(f"**Key Risks:**")
            for risk in validation.key_risks[:3]:
                sections.append(f"- {risk}")
            sections.append("")

        if validation.key_opportunities:
            sections.append(f"**Key Opportunities:**")
            for opp_item in validation.key_opportunities[:3]:
                sections.append(f"- {opp_item}")
            sections.append("")

        # Recommendation
        sections.append(f"**Recommendation:** {opp_report.recommendation.value.replace('_', ' ').title()}")
        sections.append(f"\n{opp_report.recommendation_rationale}\n")

        # Next Steps
        if opp_report.next_steps:
            sections.append(f"**Next Steps:**")
            for step in opp_report.next_steps[:3]:
                sections.append(f"1. {step}")
            sections.append("")

        sections.append("\n---\n")

    # Methodology
    sections.append("## Methodology\n")
    sections.append("**Data Sources:**")
    for source in report.data_sources_used:
        sections.append(f"- {source}")

    sections.append("\n**Limitations:**")
    for limitation in report.limitations:
        sections.append(f"- {limitation}")

    return "\n".join(sections)
