"""Slack slash command handlers."""

import asyncio
import logging
import uuid
from datetime import datetime

from slack_bolt import Ack, Respond

from src.agents.orchestrator import run_research_pipeline
from src.reports.generator import generate_markdown_report
from src.reports.pdf import generate_pdf
from src.slack.app import app

logger = logging.getLogger(__name__)


@app.command("/vineyard")
def handle_vineyard_command(ack: Ack, respond: Respond, command: dict):
    """Handle /vineyard slash command."""
    ack()  # Acknowledge immediately

    subcommand = command.get("text", "").strip().lower()

    if subcommand == "new":
        handle_new_research(respond, command)
    elif subcommand == "help":
        respond(
            text="*Vineyard Commands*\n"
            "• `/vineyard new` - Start a new research cycle\n"
            "• `/vineyard help` - Show this help message"
        )
    else:
        respond(
            text="Unknown command. Use `/vineyard help` to see available commands."
        )


def handle_new_research(respond: Respond, command: dict):
    """Start a new research cycle."""
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    # Post initial message
    respond(
        text="🔍 *Research starting...*\n"
        "This typically takes 2-3 minutes.\n\n"
        "_Discovering opportunities, validating markets, and scoring potential..._"
    )

    # Run research in background
    # Note: In production, this would be async or use a task queue
    try:
        report = run_research_pipeline()

        # Generate PDF
        markdown_content = generate_markdown_report(report)
        pdf_path = generate_pdf(markdown_content, report.report_id)

        # Upload PDF and post results
        post_research_results(channel_id, user_id, report, pdf_path)

    except Exception as e:
        logger.exception("Research pipeline failed")
        from src.slack.app import app as slack_app

        slack_app.client.chat_postMessage(
            channel=channel_id,
            text=f"❌ Research failed: {str(e)}\n\nPlease try again or check the logs.",
        )


def post_research_results(channel_id: str, user_id: str, report, pdf_path: str):
    """Post research results to Slack with interactive elements."""
    from src.slack.app import app as slack_app

    # Upload PDF
    slack_app.client.files_upload_v2(
        channel=channel_id,
        file=pdf_path,
        title=f"Research Report - {datetime.now().strftime('%Y-%m-%d')}",
        initial_comment="📊 *Research Complete*\n\nFull report attached below.",
    )

    # Build opportunity blocks
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🎯 Top Opportunities", "emoji": True},
        },
        {"type": "divider"},
    ]

    for i, opp_report in enumerate(report.opportunities[:3], 1):
        opp = opp_report.opportunity
        forecast = opp_report.forecast

        # Format MRR range
        mrr_low = forecast.mrr_month_12_conservative / 100
        mrr_high = forecast.mrr_month_12_optimistic / 100

        blocks.extend(
            [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*{i}. {opp.name}* (Score: {opp.overall_score}/100)\n"
                            f"{opp.one_liner}\n"
                            f"💰 ${mrr_low:,.0f} - ${mrr_high:,.0f} MRR @ 12mo"
                        ),
                    },
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Select This", "emoji": True},
                        "value": opp.id,
                        "action_id": f"select_opportunity_{i}",
                    },
                },
                {"type": "divider"},
            ]
        )

    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"_Research completed in {report.research_duration_seconds}s. Reply with a number (1-3) to select._",
                }
            ],
        }
    )

    # Store report ID in metadata for later retrieval
    slack_app.client.chat_postMessage(
        channel=channel_id,
        blocks=blocks,
        text="Research results - select an opportunity to proceed",
        metadata={
            "event_type": "research_results",
            "event_payload": {"report_id": report.report_id},
        },
    )
