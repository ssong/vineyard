"""Vineyard Factory - Main entry point."""

import argparse
import logging
import sys
import threading

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def start_api_server():
    """Start the API server in a separate thread."""
    from src.api.server import start_server
    from src.config import settings

    logger.info(f"Starting API server on {settings.api_host}:{settings.api_port}")
    start_server(host=settings.api_host, port=settings.api_port)


def start_slack_bot():
    """Start the Slack bot in Socket Mode."""
    from src.slack.app import start_socket_mode

    # Import handlers to register them
    from src.slack import commands  # noqa: F401
    from src.slack import interactions  # noqa: F401

    logger.info("Starting Slack bot in Socket Mode...")
    start_socket_mode()


def main():
    """Start the Vineyard Factory."""
    parser = argparse.ArgumentParser(description="Vineyard Factory")
    parser.add_argument(
        "--mode",
        choices=["all", "slack", "api"],
        default="all",
        help="Which services to run (default: all)",
    )
    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("Vineyard Factory")
    logger.info("=" * 50)

    try:
        if args.mode == "api":
            # Run only the API server
            logger.info("Running in API-only mode")
            start_api_server()

        elif args.mode == "slack":
            # Run only the Slack bot
            logger.info("Running in Slack-only mode")
            start_slack_bot()

        else:
            # Run both (default)
            logger.info("Running Slack bot and API server...")
            logger.info("Use /vineyard build [project-id] to start factory")
            logger.info("Webhook endpoint: POST /webhooks/linear")
            logger.info("Press Ctrl+C to stop")

            # Start API server in background thread
            api_thread = threading.Thread(target=start_api_server, daemon=True)
            api_thread.start()

            # Start Slack bot in main thread (blocking)
            start_slack_bot()

    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
