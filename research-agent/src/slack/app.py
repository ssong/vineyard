"""Slack Bolt app setup with Socket Mode."""

import logging

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from src.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize Slack Bolt app
app = App(token=settings.slack_bot_token)


def start_socket_mode():
    """Start the Slack app in Socket Mode."""
    logger.info("Starting Vineyard Research Agent in Socket Mode...")
    handler = SocketModeHandler(app, settings.slack_app_token)
    handler.start()
