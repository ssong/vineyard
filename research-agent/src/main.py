"""Vineyard Research Agent - Main entry point."""

import logging
import sys

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging before imports
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Start the Vineyard Research Agent."""
    logger.info("=" * 50)
    logger.info("Vineyard Research Agent")
    logger.info("=" * 50)

    try:
        # Import after environment is loaded
        from src.slack.app import start_socket_mode

        # Import handlers to register them
        from src.slack import commands  # noqa: F401
        from src.slack import interactions  # noqa: F401

        logger.info("Starting Slack bot in Socket Mode...")
        logger.info("Use /vineyard new in Slack to start a research cycle")
        logger.info("Press Ctrl+C to stop")

        start_socket_mode()

    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
