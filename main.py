"""Vineyard Bot - Unified entry point for Research Agent and Factory.

This module creates a single Slack App instance shared by both systems,
reducing resource usage and ensuring consistent bot behavior.

CRITICAL: We must patch the app module BEFORE importing command handlers,
because decorators register with the app at import time.
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


def clear_src_modules():
    """Clear all src.* modules from sys.modules.
    
    This must be done before importing from a different project's src package.
    Uses list() to avoid 'dictionary changed size during iteration' error.
    """
    modules_to_remove = [key for key in list(sys.modules.keys()) 
                         if key.startswith('src.') or key == 'src']
    for mod in modules_to_remove:
        del sys.modules[mod]
    return len(modules_to_remove)


def set_project_path(project_path):
    """Set a project path at the front of sys.path.
    
    Removes it first if already present to ensure it's at the front.
    """
    if project_path in sys.path:
        sys.path.remove(project_path)
    sys.path.insert(0, project_path)


def get_factory_settings():
    """Load settings from factory config."""
    set_project_path(FACTORY_PATH)
    from src.config import settings
    return settings


def create_shared_app(settings):
    """Create the shared Slack App instance."""
    return App(token=settings.slack_bot_token)


def register_research_agent_handlers(app):
    """Register Research Agent handlers by patching app before import."""
    set_project_path(RESEARCH_AGENT_PATH)
    cleared = clear_src_modules()
    logger.debug(f"Cleared {cleared} src.* modules for research-agent")
    
    # Import and patch the app module BEFORE importing handlers
    import src.slack.app as slack_app_module
    slack_app_module.app = app
    
    # Now import handlers - decorators will use our patched app
    from src.slack import commands  # noqa: F401
    from src.slack import interactions  # noqa: F401
    
    logger.info("✓ Research Agent handlers registered")


def register_factory_handlers(app):
    """Register Factory handlers by patching app before import."""
    set_project_path(FACTORY_PATH)
    cleared = clear_src_modules()
    logger.debug(f"Cleared {cleared} src.* modules for factory")
    
    # Import and patch the app module BEFORE importing handlers
    import src.slack.app as slack_app_module
    slack_app_module.app = app
    
    # Now import handlers - decorators will use our patched app
    from src.slack import commands  # noqa: F401
    from src.slack import interactions  # noqa: F401
    
    logger.info("✓ Factory handlers registered")


def start_api_server(settings):
    """Start the Factory API server for Linear webhooks."""
    set_project_path(FACTORY_PATH)
    cleared = clear_src_modules()
    logger.debug(f"Cleared {cleared} src.* modules for API server")
    
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
    logger.debug(f"BASE_DIR: {BASE_DIR}")
    logger.debug(f"RESEARCH_AGENT_PATH: {RESEARCH_AGENT_PATH}")
    logger.debug(f"FACTORY_PATH: {FACTORY_PATH}")

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
