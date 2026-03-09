"""Vineyard Bot - PRD-first factory pipeline.

Users submit a PRD via Slack modal, and the factory pipeline analyzes it,
asks clarifying questions, designs, specs, builds, and prepares for launch.

Commands:
  /vineyard new        - Open PRD submission modal
  /vineyard status     - List factory runs and their status
  /vineyard resume [id] - Resume a failed factory run
  /vineyard help       - Show help message
"""

import argparse
import logging
import os
import sys
import threading

from dotenv import load_dotenv
from slack_bolt import App, Ack, Respond
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
    """Inject a pre-made src.slack.app module with our shared app."""
    import types

    src_module = types.ModuleType('src')
    src_module.__path__ = [os.path.join(project_path, 'src')]

    slack_module = types.ModuleType('src.slack')
    slack_module.__path__ = [os.path.join(project_path, 'src', 'slack')]

    app_module = types.ModuleType('src.slack.app')
    app_module.app = shared_app
    app_module.__file__ = os.path.join(project_path, 'src', 'slack', 'app.py')

    src_module.slack = slack_module
    setattr(slack_module, 'app', shared_app)

    sys.modules['src'] = src_module
    sys.modules['src.slack'] = slack_module
    sys.modules['src.slack.app'] = app_module


def register_factory_handlers(shared_app, settings):
    """Register Factory interaction handlers."""
    set_project_path(FACTORY_PATH)
    clear_src_modules()
    inject_app_module(FACTORY_PATH, shared_app)

    before_count = len(shared_app._listeners) if hasattr(shared_app, '_listeners') else 0

    from src.slack import interactions  # noqa: F401

    after_count = len(shared_app._listeners) if hasattr(shared_app, '_listeners') else 0
    new_listeners = after_count - before_count
    logger.info(f"✓ Factory interaction handlers registered ({new_listeners} listeners)")


def start_api_server(settings):
    """Start the Factory API server for Linear webhooks."""
    set_project_path(FACTORY_PATH)
    clear_src_modules()

    from src.api.server import start_server

    logger.info(f"Starting API server on {settings.api_host}:{settings.api_port}")
    start_server(host=settings.api_host, port=settings.api_port)


def register_unified_command_handler(shared_app):
    """Register the /vineyard command handler."""

    @shared_app.command("/vineyard")
    def handle_vineyard_command(ack: Ack, respond: Respond, command: dict):
        """Unified handler for /vineyard command."""
        ack()

        subcommand = command.get("text", "").strip().lower()

        if subcommand == "new":
            _handle_new_prd(respond, command, shared_app)
        elif subcommand.startswith("resume"):
            _handle_factory_resume(respond, command, shared_app)
        elif subcommand == "status" or subcommand == "runs":
            _handle_list_runs(respond, shared_app)
        elif subcommand == "help":
            respond(
                text="*Vineyard Commands*\n"
                "• `/vineyard new` - Submit a new PRD to build\n"
                "• `/vineyard status` - List factory runs and their status\n"
                "• `/vineyard resume [execution-id]` - Resume a failed factory run\n"
                "• `/vineyard help` - Show this help message"
            )
        else:
            respond(
                text="Unknown command. Use `/vineyard help` to see available commands."
            )

    logger.info("✓ Unified /vineyard command handler registered")


def _handle_new_prd(respond: Respond, command: dict, shared_app: App):
    """Handle /vineyard new - open PRD submission modal."""
    trigger_id = command.get("trigger_id")

    if not trigger_id:
        respond(text="❌ Unable to open modal. Please try again.")
        return

    try:
        shared_app.client.views_open(
            trigger_id=trigger_id,
            view={
                "type": "modal",
                "callback_id": "prd_submission",
                "title": {"type": "plain_text", "text": "New Product"},
                "submit": {"type": "plain_text", "text": "Submit PRD"},
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "product_name_block",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "product_name_input",
                            "placeholder": {"type": "plain_text", "text": "e.g., InvoiceBot"},
                        },
                        "label": {"type": "plain_text", "text": "Product Name"},
                    },
                    {
                        "type": "input",
                        "block_id": "prd_text_block",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "prd_text_input",
                            "multiline": True,
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Describe your product idea. Can be as brief as a sentence or as detailed as a full PRD.",
                            },
                        },
                        "label": {"type": "plain_text", "text": "PRD / Product Description"},
                    },
                ],
            },
        )
    except Exception as e:
        logger.exception("Failed to open PRD modal")
        respond(text=f"❌ Failed to open modal: {str(e)}")


def _handle_list_runs(respond: Respond, shared_app: App):
    """Handle /vineyard status - shows factory runs."""
    set_project_path(FACTORY_PATH)
    clear_src_modules()
    inject_app_module(FACTORY_PATH, shared_app)

    try:
        from src.orchestrator.persistence import list_states

        states = list_states()

        if not states:
            respond(
                text="No factory runs found.\n\n"
                "_Use `/vineyard new` to submit a PRD and start a new factory run._"
            )
            return

        lines = ["*Factory Runs*\n"]

        for state in states[:10]:
            exec_id = state.get("execution_id", "")
            phase = state.get("current_phase", "unknown")
            status = state.get("status", "unknown")
            name = state.get("product_name", "Unknown")

            status_emoji = {
                "pending": "⏳",
                "in_progress": "🔄",
                "completed": "✅",
                "failed": "❌",
                "awaiting_approval": "⏸️",
            }.get(status, "📋")

            lines.append(f"{status_emoji} *{name}*")
            lines.append(f"   Phase: `{phase}` | Status: `{status}`")
            lines.append(f"   ID: `{exec_id}`")
            lines.append("")

        if len(states) > 10:
            lines.append(f"_...and {len(states) - 10} more runs_")

        lines.append("_Use `/vineyard resume [execution-id]` to resume a failed run_")

        respond(text="\n".join(lines))

    except Exception as e:
        logger.exception("Failed to list runs")
        respond(text=f"❌ Failed to list runs: {str(e)}")


def _handle_factory_resume(respond: Respond, command: dict, shared_app: App):
    """Handle /vineyard resume - resumes a failed factory run."""
    set_project_path(FACTORY_PATH)
    clear_src_modules()
    inject_app_module(FACTORY_PATH, shared_app)

    text = command.get("text", "").strip()
    parts = text.split()

    execution_id = parts[1] if len(parts) > 1 else None
    channel_id = command["channel_id"]

    if not execution_id:
        try:
            from src.orchestrator.persistence import list_states

            failed_states = [s for s in list_states() if s.get("status") == "failed"]

            if not failed_states:
                respond(
                    text="No failed runs to resume.\n\n"
                    "_Use `/vineyard status` to see all factory runs._"
                )
                return

            lines = ["Please provide an execution ID: `/vineyard resume [execution-id]`\n"]
            lines.append("*Failed runs that can be resumed:*\n")

            for state in failed_states[:5]:
                exec_id = state.get("execution_id", "")
                name = state.get("product_name", "Unknown")
                phase = state.get("current_phase", "unknown")
                lines.append(f"• *{name}* - failed at `{phase}`")
                lines.append(f"  ID: `{exec_id}`")

            respond(text="\n".join(lines))
            return

        except Exception as e:
            respond(
                text="Please provide an execution ID: `/vineyard resume [execution-id]`\n\n"
                "_Use `/vineyard status` to see all factory runs._"
            )
            return

    respond(
        text=f"🔄 *Resuming factory run*\n"
        f"Execution ID: `{execution_id[:8]}...`\n"
        "_Attempting to resume from last failed phase..._"
    )

    try:
        from src.orchestrator.runner import resume_factory
        from src.orchestrator.persistence import load_state

        state = load_state(execution_id)
        if not state:
            shared_app.client.chat_postMessage(
                channel=channel_id,
                text=f"❌ Execution not found: `{execution_id}`\n\n"
                "_Use `/vineyard status` to see available runs._"
            )
            return

        updated_state = resume_factory(execution_id)

        if updated_state:
            phase_name = updated_state.current_phase.value.replace("_", " ").title()
            status = updated_state.phase_statuses.get(updated_state.current_phase.value)

            if updated_state.completed_at:
                shared_app.client.chat_postMessage(
                    channel=channel_id,
                    text=f"✅ *Factory run complete!*\n\n"
                    f"Product: {updated_state.handoff.prd_input.name}\n"
                    f"Linear: <{updated_state.handoff.linear_project_url}|View in Linear>"
                )
            elif status and status.value == "failed":
                shared_app.client.chat_postMessage(
                    channel=channel_id,
                    text=f"❌ *Factory failed again at {phase_name}*\n\n"
                    f"Check Linear for error details.\n"
                    f"Use `/vineyard resume {execution_id}` to try again."
                )
            else:
                shared_app.client.chat_postMessage(
                    channel=channel_id,
                    text=f"🔄 *Factory resumed*\n\n"
                    f"Current phase: *{phase_name}*\n"
                    f"Status: `{status.value if status else 'unknown'}`"
                )
        else:
            shared_app.client.chat_postMessage(
                channel=channel_id,
                text="❌ Failed to resume factory. Check logs for details."
            )

    except Exception as e:
        logger.exception("Failed to resume factory")
        shared_app.client.chat_postMessage(
            channel=channel_id,
            text=f"❌ Failed to resume: {str(e)}"
        )


def main():
    """Start the Vineyard Bot."""
    parser = argparse.ArgumentParser(description="Vineyard Bot")
    parser.add_argument(
        "--mode",
        choices=["all", "slack", "api"],
        default="all",
        help="Which services to run (default: all)",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Vineyard Bot - PRD-First Factory Pipeline")
    logger.info("=" * 60)

    try:
        settings = get_factory_settings()

        if args.mode == "api":
            logger.info("Running in API-only mode")
            start_api_server(settings)
            return

        app = create_shared_app(settings)

        # Register unified command handler
        register_unified_command_handler(app)

        # Register factory interaction handlers
        register_factory_handlers(app, settings)

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
        logger.info("  /vineyard new        - Submit a PRD to build")
        logger.info("  /vineyard status     - List factory runs")
        logger.info("  /vineyard resume [id] - Resume a failed run")
        logger.info("  /vineyard help       - Show help")
        logger.info("Press Ctrl+C to stop")

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
