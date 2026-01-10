"""Vineyard Bot - Unified entry point for Research Agent and Factory.

This module creates a single Slack App instance shared by both systems,
reducing resource usage and ensuring consistent bot behavior.

APPROACH: Pre-inject a fake src.slack.app module into sys.modules that contains
our shared app. When command/interaction modules are imported, their decorators
(@app.command, @app.action, etc.) register handlers directly to the shared app.
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
    """Clear all src.* modules from sys.modules."""
    modules_to_remove = [key for key in list(sys.modules.keys()) 
                         if key.startswith('src.') or key == 'src']
    for mod in modules_to_remove:
        del sys.modules[mod]
    return len(modules_to_remove)


def set_project_path(project_path):
    """Set a project path at the front of sys.path."""
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


def inject_app_module(project_path, shared_app):
    """Inject a pre-made src.slack.app module with our shared app.

    This ensures that when command modules do `from src.slack.app import app`,
    they get our shared app instance, and decorators register to it directly.
    """
    import types

    # Create the module hierarchy
    src_module = types.ModuleType('src')
    src_module.__path__ = [os.path.join(project_path, 'src')]

    slack_module = types.ModuleType('src.slack')
    slack_module.__path__ = [os.path.join(project_path, 'src', 'slack')]

    app_module = types.ModuleType('src.slack.app')
    app_module.app = shared_app
    app_module.__file__ = os.path.join(project_path, 'src', 'slack', 'app.py')

    # Wire up the module hierarchy
    src_module.slack = slack_module

    # The __init__.py does `from .app import app`, so src.slack.app should be:
    # 1. A module (src.slack.app) with an `app` attribute
    # 2. Also exported as src.slack.app (the App instance) from __init__.py
    # We set both: the submodule reference and the direct app instance
    setattr(slack_module, 'app', shared_app)  # src.slack.app = App instance (from __init__.py export)

    # Inject into sys.modules
    sys.modules['src'] = src_module
    sys.modules['src.slack'] = slack_module
    sys.modules['src.slack.app'] = app_module  # src.slack.app module


def register_research_agent_handlers(shared_app, settings):
    """Register Research Agent handlers."""
    set_project_path(RESEARCH_AGENT_PATH)
    clear_src_modules()

    # Pre-inject the app module with our shared app BEFORE importing commands
    # This ensures decorators register directly to shared_app
    inject_app_module(RESEARCH_AGENT_PATH, shared_app)

    # Track listener count before import
    before_count = len(shared_app._listeners) if hasattr(shared_app, '_listeners') else 0

    # Import handlers - decorators register directly to shared_app
    from src.slack import commands  # noqa: F401
    from src.slack import interactions  # noqa: F401

    after_count = len(shared_app._listeners) if hasattr(shared_app, '_listeners') else 0
    new_listeners = after_count - before_count
    logger.info(f"✓ Research Agent handlers registered ({new_listeners} listeners)")


def register_factory_handlers(shared_app, settings):
    """Register Factory handlers."""
    set_project_path(FACTORY_PATH)
    clear_src_modules()

    # Pre-inject the app module with our shared app BEFORE importing commands
    # This ensures decorators register directly to shared_app
    inject_app_module(FACTORY_PATH, shared_app)

    # Track listener count before import
    before_count = len(shared_app._listeners) if hasattr(shared_app, '_listeners') else 0

    # Import handlers - decorators register directly to shared_app
    from src.slack import commands  # noqa: F401
    from src.slack import interactions  # noqa: F401

    after_count = len(shared_app._listeners) if hasattr(shared_app, '_listeners') else 0
    new_listeners = after_count - before_count
    logger.info(f"✓ Factory handlers registered ({new_listeners} listeners)")


def start_api_server(settings):
    """Start the Factory API server for Linear webhooks."""
    set_project_path(FACTORY_PATH)
    clear_src_modules()
    
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
        register_research_agent_handlers(app, settings)
        register_factory_handlers(app, settings)
        
        # Log total listeners
        total_listeners = len(app._listeners) if hasattr(app, '_listeners') else 0
        logger.info(f"Total listeners registered: {total_listeners}")

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
