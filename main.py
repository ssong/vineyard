"""Vineyard Bot - Unified entry point for Research Agent and Factory.

This module creates a single Slack App instance shared by both systems,
reducing resource usage and ensuring consistent bot behavior.

IMPORTANT: In Docker, PYTHONPATH must include both subdirectories:
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

# Compute paths once at module level
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESEARCH_AGENT_PATH = os.path.join(BASE_DIR, "research-agent")
FACTORY_PATH = os.path.join(BASE_DIR, "factory")


def ensure_paths():
    """Ensure both project paths are in sys.path.
    
    This is a fallback for local development - in Docker, PYTHONPATH handles this.
    """
    for path in [RESEARCH_AGENT_PATH, FACTORY_PATH]:
        if path not in sys.path:
            sys.path.insert(0, path)
            logger.debug(f"Added to sys.path: {path}")


def get_factory_settings():
    """Load settings from factory config."""
    ensure_paths()
    # Push factory to front of path for this import
    if FACTORY_PATH in sys.path:
        sys.path.remove(FACTORY_PATH)
    sys.path.insert(0, FACTORY_PATH)
    
    from src.config import settings
    return settings


def create_shared_app(settings):
    """Create the shared Slack App instance."""
    return App(token=settings.slack_bot_token)


def patch_and_register_handlers(app, project_path, project_name):
    """Patch a project's app module and register its handlers.
    
    Temporarily prioritizes the project path, then imports handlers.
    """
    ensure_paths()
    
    # Put this project's path first
    if project_path in sys.path:
        sys.path.remove(project_path)
    sys.path.insert(0, project_path)
    
    # Patch the app module
    import src.slack.app as slack_app_module
    slack_app_module.app = app
    
    # Import handlers (they register via decorators)
    # Need to reload if already imported
    import importlib
    importlib.invalidate_caches()
    
    from src.slack import commands
    from src.slack import interactions
    
    # Force reload to ensure decorators run with our app
    importlib.reload(commands)
    importlib.reload(interactions)
    
    logger.info(f"✓ {project_name} handlers registered")


def start_api_server(settings):
    """Start the Factory API server for Linear webhooks."""
    # Ensure factory is in path
    if FACTORY_PATH not in sys.path:
        sys.path.insert(0, FACTORY_PATH)
    
    # Make sure factory is first for this import
    if FACTORY_PATH in sys.path:
        sys.path.remove(FACTORY_PATH)
    sys.path.insert(0, FACTORY_PATH)
    
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

    logger.info("=" * 60)
    logger.info("Vineyard Bot - Unified Research Agent + Factory")
    logger.info("=" * 60)
    logger.debug(f"sys.path: {sys.path[:5]}")

    try:
        # Get settings (uses factory's config)
        settings = get_factory_settings()

        if args.mode == "api":
            logger.info("Running in API-only mode")
            start_api_server(settings)
            return

        # Create shared Slack app
        app = create_shared_app(settings)

        # Register handlers from both systems
        patch_and_register_handlers(app, RESEARCH_AGENT_PATH, "Research Agent")
        patch_and_register_handlers(app, FACTORY_PATH, "Factory")

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
