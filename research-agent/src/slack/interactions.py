"""Slack interaction handlers for buttons and messages."""

import logging
import re

from slack_bolt import Ack, Respond

from src.linear.client import create_project_for_opportunity
from src.persistence import save_report as _save_report, load_report as _load_report, mark_opportunity_selected
from src.slack.app import app

logger = logging.getLogger(__name__)


def store_report(report_id: str, report):
    """Store a research report for later retrieval (SQLite-backed)."""
    _save_report(report_id, report)


def get_report(report_id: str):
    """Retrieve a stored research report (SQLite-backed)."""
    return _load_report(report_id)


@app.action(re.compile(r"select_opportunity_\d+"))
def handle_opportunity_selection(ack: Ack, body: dict, respond: Respond):
    """Handle opportunity selection button click."""
    ack()

    action = body["actions"][0]
    opportunity_id = action["value"]
    user_id = body["user"]["id"]

    # Get the report from metadata or storage
    message = body.get("message", {})
    metadata = message.get("metadata", {})
    report_id = metadata.get("event_payload", {}).get("report_id")

    logger.info(f"User {user_id} selected opportunity {opportunity_id} from report {report_id}")

    # Find the opportunity in the stored report
    report = get_report(report_id) if report_id else None

    if not report:
        respond(
            text="⚠️ Could not find the research report. Please run `/vineyard new` again.",
            replace_original=False,
        )
        return

    selected_opp = None
    for opp_report in report.opportunities:
        if opp_report.opportunity.id == opportunity_id:
            selected_opp = opp_report
            break

    if not selected_opp:
        respond(
            text="⚠️ Could not find the selected opportunity. Please try again.",
            replace_original=False,
        )
        return

    # Create Linear project
    try:
        project_url = create_project_for_opportunity(selected_opp)

        # Mark opportunity as selected in database
        mark_opportunity_selected(opportunity_id, project_url)

        # Update the original message
        respond(
            text=(
                f"✅ *{selected_opp.opportunity.name}* selected!\n\n"
                f"📋 Linear project created: <{project_url}|View Project>\n\n"
                f"_Next: Run `/vineyard build` to start the factory_"
            ),
            replace_original=True,
        )

    except Exception as e:
        logger.exception("Failed to create Linear project")
        respond(
            text=f"❌ Failed to create Linear project: {str(e)}",
            replace_original=False,
        )


@app.message(re.compile(r"^[1-3]$"))
def handle_number_selection(ack: Ack, message: dict, say):
    """Handle number reply to select opportunity (1-3)."""
    ack()

    selection = int(message["text"])
    user_id = message["user"]
    channel_id = message["channel"]

    logger.info(f"User {user_id} selected option {selection} via message")

    # In production, we'd look up the most recent research report for this channel
    # For now, respond with guidance
    say(
        text=(
            f"To select option {selection}, please click the 'Select This' button "
            "on the opportunity you'd like to pursue."
        ),
        thread_ts=message.get("thread_ts"),
    )
