"""Vineyard Bot - Unified entry point for Research Agent and Factory.

This module creates a single Slack App instance shared by both systems,
reducing resource usage and ensuring consistent bot behavior.

APPROACH: Create temporary apps for each project, import their handlers
(which register via decorators), then copy the registered listeners to
our shared app.
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


def copy_listeners(from_app, to_app):
    """Copy all registered listeners from one App to another.
    
    Slack Bolt stores listeners in internal registries. We need to copy
    them to our shared app so they respond to events.
    """
    # Copy command listeners
    if hasattr(from_app, '_listeners'):
        for listener in from_app._listeners:
            to_app._listeners.append(listener)
    
    # Copy from listener_runner if present
    if hasattr(from_app, '_listener_runner') and hasattr(from_app._listener_runner, 'listeners'):
        for listener in from_app._listener_runner.listeners:
            if listener not in to_app._listener_runner.listeners:
                to_app._listener_runner.listeners.append(listener)


def register_research_agent_handlers(shared_app, settings):
    """Register Research Agent handlers."""
    set_project_path(RESEARCH_AGENT_PATH)
    clear_src_modules()
    
    # Create a temporary app that handlers will register to
    temp_app = App(token=settings.slack_bot_token)
    
    # Patch the app module to use our temp app
    import src.slack.app as slack_app_module
    slack_app_module.app = temp_app
    
    # Import handlers - they register to temp_app via decorators
    from src.slack import commands  # noqa: F401
    from src.slack import interactions  # noqa: F401
    
    # Copy registered listeners to shared app
    copy_listeners(temp_app, shared_app)
    
    listener_count = len(temp_app._listeners) if hasattr(temp_app, '_listeners') else 0
    logger.info(f"✓ Research Agent handlers registered ({listener_count} listeners)")


def register_factory_handlers(shared_app, settings):
    """Register Factory handlers."""
    set_project_path(FACTORY_PATH)
    clear_src_modules()
    
    # Create a temporary app that handlers will register to
    temp_app = App(token=settings.slack_bot_token)
    
    # Patch the app module to use our temp app
    import src.slack.app as slack_app_module
    slack_app_module.app = temp_app
    
    # Import handlers - they register to temp_app via decorators
    from src.slack import commands  # noqa: F401
    from src.slack import interactions  # noqa: F401
    
    # Copy registered listeners to shared app
    copy_listeners(temp_app, shared_app)
    
    listener_count = len(temp_app._listeners) if hasattr(temp_app, '_listeners') else 0
    logger.info(f"✓ Factory handlers registered ({listener_count} listeners)")


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
