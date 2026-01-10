"""Vineyard Bot - Unified entry point for Research Agent and Factory.

This module creates a single Slack App instance shared by both systems,
reducing resource usage and ensuring consistent bot behavior.
"""

import argparse
import logging
import sys
import threading

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# Load environment variables first
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_settings():
    """Load settings from factory config."""
    from factory.src.config import settings
    return settings


def create_shared_app(settings):
    """Create the shared Slack App instance."""
    return App(token=settings.slack_bot_token)


def register_research_agent_handlers(app):
    """Register Research Agent slash commands and interactions."""
    # Patch the app module to use our shared app
    import research_agent.src.slack.app as research_app_module
    research_app_module.app = app

    # Import handlers (they auto-register via decorators)
    from research_agent.src.slack import commands  # noqa: F401
    from research_agent.src.slack import interactions  # noqa: F401

    logger.info("✓ Research Agent handlers registered")


def register_factory_handlers(app):
    """Register Factory slash commands and interactions."""
    # Patch the app module to use our shared app
    import factory.src.slack.app as factory_app_module
    factory_app_module.app = app

    # Import handlers (they auto-register via decorators)
    from factory.src.slack import commands  # noqa: F401
    from factory.src.slack import interactions  # noqa: F401

    logger.info("✓ Factory handlers registered")


def start_api_server(settings):
    """Start the Factory API server for Linear webhooks."""
    from factory.src.api.server import start_server

    logger.info(f"Starting API server on {settings.api_host}:{settings.api_port}")
    start_server(host=settings.api_host, port=settings.api_port)


def main():
    """Start the unified Vineyard Bot."""
    parser = argparse.ArgumentParser(description="Vineyard Bot")
    parser.add_argument(
        "--mode",
        choices=["all", "slack", "api"],
        default="all",
        help="Which services to run (default: all)",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Vineyard Bot - Unified Research Agent + Factory")
    logger.info("=" * 60)

    try:
        settings = get_settings()

        if args.mode == "api":
            logger.info("Running in API-only mode")
            start_api_server(settings)
            return

        # Create shared Slack app
        app = create_shared_app(settings)

        # Register handlers from both systems
        register_research_agent_handlers(app)
        register_factory_handlers(app)

        if args.mode == "all":
            logger.info("Starting API server in background...")
            api_thread = threading.Thread(
                target=start_api_server,
                args=(settings,),
                daemon=True
            )
            api_thread.start()

        logger.info("Starting Slack bot in Socket Mode...")
        logger.info("Available commands:")
        logger.info("  /vineyard new        - Start research cycle")
        logger.info("  /vineyard build [id] - Start factory for project")
        logger.info("  /vineyard help       - Show help")
        logger.info("Press Ctrl+C to stop")

        # Start Socket Mode (blocking)
        handler = SocketModeHandler(app, settings.slack_app_token)
        handler.start()

    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

