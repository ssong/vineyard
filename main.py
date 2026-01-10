"""Vineyard Bot - Unified entry point for Research Agent and Factory.

This module creates a single Slack App instance shared by both systems,
reducing resource usage and ensuring consistent bot behavior.

IMPORTANT: This script expects PYTHONPATH to include both subdirectories:
  PYTHONPATH=/app:/app/research-agent:/app/factory
"""

import argparse
import logging
import os
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


def setup_paths():
    """Add subdirectories to Python path if not already set via PYTHONPATH."""
    base = os.path.dirname(os.path.abspath(__file__))
    
    research_path = os.path.join(base, "research-agent")
    factory_path = os.path.join(base, "factory")
    
    if research_path not in sys.path:
        sys.path.insert(0, research_path)
    if factory_path not in sys.path:
        sys.path.insert(0, factory_path)


def get_settings():
    """Load settings from factory config.
    
    Factory settings include all required vars (Slack, Anthropic, Linear, etc.)
    """
    # Import from factory's src.config (works because factory/ is in PYTHONPATH)
    from src.config import settings
    return settings


def create_shared_app(settings):
    """Create the shared Slack App instance."""
    return App(token=settings.slack_bot_token)


def patch_and_register_research_agent(app):
    """Patch research-agent's app module and register handlers.
    
    We need to patch the app module BEFORE importing handlers,
    because handlers use @app.command() decorators that register on import.
    """
    # Temporarily switch to research-agent context
    import src.slack.app as slack_app_module
    original_app = getattr(slack_app_module, 'app', None)
    slack_app_module.app = app
    
    # Now import handlers - they'll register with our shared app
    from src.slack import commands  # noqa: F401
    from src.slack import interactions  # noqa: F401
    
    logger.info("✓ Research Agent handlers registered")


def patch_and_register_factory(app):
    """Patch factory's app module and register handlers."""
    import src.slack.app as slack_app_module
    slack_app_module.app = app
    
    from src.slack import commands  # noqa: F401
    from src.slack import interactions  # noqa: F401
    
    logger.info("✓ Factory handlers registered")


def start_api_server(settings):
    """Start the Factory API server for Linear webhooks."""
    from src.api.server import start_server
    
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

    # Ensure paths are set up for local development
    setup_paths()

    logger.info("=" * 60)
    logger.info("Vineyard Bot - Unified Research Agent + Factory")
    logger.info("=" * 60)

    try:
        # Get settings (uses factory's config since it has everything)
        settings = get_settings()

        if args.mode == "api":
            logger.info("Running in API-only mode")
            start_api_server(settings)
            return

        # Create shared Slack app
        app = create_shared_app(settings)

        # Register handlers from both systems
        # Research agent first (temporarily adjust path priority)
        research_path = os.path.join(os.path.dirname(__file__), "research-agent")
        factory_path = os.path.join(os.path.dirname(__file__), "factory")
        
        # Register research-agent handlers
        if research_path in sys.path:
            sys.path.remove(research_path)
        sys.path.insert(0, research_path)
        patch_and_register_research_agent(app)
        
        # Register factory handlers  
        sys.path.remove(research_path)
        sys.path.insert(0, factory_path)
        patch_and_register_factory(app)

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
