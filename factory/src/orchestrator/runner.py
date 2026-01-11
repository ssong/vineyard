"""Factory orchestrator - phase execution, state management, and recovery."""

import logging
import uuid
from datetime import datetime
from typing import Optional

from src.agents.engineering import CodeAgent, DevOpsAgent, QAAgent, SecurityAgent, TestAgent
from src.agents.gtm import GrowthAgent, LaunchAgent, MarketingAgent, SupportAgent
from src.agents.product import DesignAgent, ResearchEnrichmentAgent, SpecAgent
from src.models import FactoryHandoff, FactoryState, Phase, PhaseStatus
from src.orchestrator.persistence import (
    delete_state,
    list_states,
    load_state,
    save_state,
)
from src.tools import linear

logger = logging.getLogger(__name__)

# Phase configuration
PHASE_CONFIG = {
    Phase.RESEARCH_ENRICHMENT: {
        "agent": ResearchEnrichmentAgent,
        "checkpoint": False,
    },
    Phase.DESIGN: {
        "agent": DesignAgent,
        "checkpoint": True,
    },
    Phase.SPEC: {
        "agent": SpecAgent,
        "checkpoint": False,
    },
    Phase.BUILD: {
        "agent": None,  # Composite of Code, Test, Security, DevOps
        "checkpoint": True,
    },
    Phase.LAUNCH_PREP: {
        "agent": None,  # Composite of Marketing, Launch
        "checkpoint": False,
    },
    Phase.LAUNCH: {
        "agent": LaunchAgent,
        "checkpoint": True,
    },
    Phase.GROWTH: {
        "agent": None,  # Composite of Growth, Support
        "checkpoint": False,
    },
}

# Phase order
PHASE_ORDER = [
    Phase.RESEARCH_ENRICHMENT,
    Phase.DESIGN,
    Phase.SPEC,
    Phase.BUILD,
    Phase.LAUNCH_PREP,
    Phase.LAUNCH,
    Phase.GROWTH,
]


def create_factory_run(handoff: FactoryHandoff) -> FactoryState:
    """Create a new factory execution."""
    state = FactoryState(
        execution_id=str(uuid.uuid4()),
        handoff=handoff,
        current_phase=Phase.RESEARCH_ENRICHMENT,
    )

    # Initialize phase statuses
    for phase in PHASE_ORDER:
        state.phase_statuses[phase.value] = PhaseStatus.PENDING

    # Create upfront Linear issues for all phases
    try:
        phase_issues = _initialize_linear_tracking(state)
        state.linear_phase_issues = phase_issues
        logger.info(f"Created {len(phase_issues)} upfront Linear issues")
    except Exception as e:
        logger.warning(f"Failed to create upfront Linear issues: {e}")

    save_state(state)
    logger.info(f"Created factory run: {state.execution_id}")

    return state


def _initialize_linear_tracking(state: FactoryState) -> dict[str, dict]:
    """
    Create upfront Linear issues for all factory phases with task sub-issues.

    Creates:
    1. Phase issues for each factory phase
    2. Task sub-issues under each phase with detailed approaches for review

    Returns:
        Dict mapping phase names to their issue info including task IDs
    """
    if not state.handoff.linear_project_id:
        logger.warning("No Linear project ID in handoff, skipping issue creation")
        return {}

    # Get team ID from project
    project = linear.get_project(state.handoff.linear_project_id)
    teams = project.get("teams", {}).get("nodes", [])

    if not teams:
        logger.warning("No team found for Linear project")
        return {}

    state.linear_team_id = teams[0]["id"]

    # Create upfront issues for all phases
    phase_issues = linear.create_factory_issues(
        project_id=state.handoff.linear_project_id,
        product_name=state.handoff.opportunity.name,
        execution_id=state.execution_id,
    )

    # Create task sub-issues for each phase
    for phase_name, phase_info in phase_issues.items():
        if phase_name == "root":
            continue
        
        phase_id = phase_info.get("id")
        if not phase_id:
            continue
        
        task_issues = _create_phase_tasks(
            state=state,
            phase_name=phase_name,
            phase_issue_id=phase_id,
        )
        
        # Store task IDs in the phase info
        phase_issues[phase_name]["tasks"] = task_issues

    return phase_issues


def _create_phase_tasks(
    state: FactoryState,
    phase_name: str,
    phase_issue_id: str,
) -> dict[str, dict]:
    """
    Create task sub-issues for a phase with detailed approaches.

    Args:
        state: Factory state with Linear tracking info
        phase_name: Name of the phase
        phase_issue_id: Parent issue ID

    Returns:
        Dict mapping task keys to their issue info (id, identifier, url)
    """
    from src.config.task_config import get_phase_tasks

    tasks = get_phase_tasks(phase_name)
    if not tasks:
        return {}

    task_issues = {}
    label = linear.PHASE_ISSUE_CONFIG.get(phase_name, {}).get("label", "phase")

    for task in tasks:
        try:
            issue = linear.create_task_with_approach(
                project_id=state.handoff.linear_project_id,
                team_id=state.linear_team_id,
                parent_id=phase_issue_id,
                title=task["title"],
                objective=task["objective"],
                approach=task["approach"],
                inputs=task["inputs"],
                expected_output=task["expected_output"],
                labels=[label],
                assignee_name="vineyard",
            )
            
            if issue:
                task_issues[task["key"]] = {
                    "id": issue.get("id"),
                    "identifier": issue.get("identifier"),
                    "url": issue.get("url"),
                }
                logger.debug(f"Created task {task['key']}: {issue.get('identifier')}")
        except Exception as e:
            logger.warning(f"Failed to create task {task['key']}: {e}")

    logger.info(f"Created {len(task_issues)} tasks for phase {phase_name}")
    return task_issues


def run_factory(
    state: FactoryState,
    channel_id: Optional[str] = None,
) -> FactoryState:
    """
    Execute the factory pipeline.

    Args:
        state: Current factory state
        channel_id: Slack channel for notifications (optional)

    Returns when complete, at a checkpoint, or on failure.
    """
    logger.info(f"Starting factory run: {state.execution_id}")

    # Ensure Linear tracking is initialized (for resumed runs)
    if not state.linear_phase_issues and state.handoff.linear_project_id:
        try:
            state.linear_phase_issues = _initialize_linear_tracking(state)
            save_state(state)
        except Exception as e:
            logger.warning(f"Failed to initialize Linear tracking on resume: {e}")

    while True:
        current_phase = state.current_phase

        # Check if we need approval for this phase
        if _requires_approval(state, current_phase):
            state.update_phase_status(current_phase, PhaseStatus.AWAITING_APPROVAL)
            save_state(state)
            logger.info(f"Phase {current_phase.value} awaiting approval")

            # Update Linear issue to show awaiting review, assign to operator
            _update_linear_phase_status(
                state, current_phase, "awaiting_review",
                f"Phase {current_phase.value.replace('_', ' ')} completed, awaiting review before proceeding.",
                assign_to="sang",  # Assign to operator for review
                mention_user="sang",  # Tag operator in comment
            )

            # Send Slack notification
            if channel_id:
                _notify_checkpoint(channel_id, state)

            return state

        # Execute current phase
        try:
            state.update_phase_status(current_phase, PhaseStatus.IN_PROGRESS)
            save_state(state)

            # Update Linear issue to show in-progress
            _update_linear_phase_status(
                state, current_phase, "started",
                f"Starting {current_phase.value.replace('_', ' ')} phase..."
            )

            output = _execute_phase(state, current_phase)

            state.store_output(current_phase, output)
            state.update_phase_status(current_phase, PhaseStatus.COMPLETED)
            save_state(state)

            logger.info(f"Phase {current_phase.value} completed")

            # Update Linear issue to show completed
            _update_linear_phase_status(
                state, current_phase, "completed",
                _get_phase_summary(current_phase, output)
            )

            # Send progress notification
            if channel_id:
                _notify_phase_complete(channel_id, state, current_phase)

        except Exception as e:
            logger.exception(f"Phase {current_phase.value} failed")
            state.update_phase_status(current_phase, PhaseStatus.FAILED)
            state.errors.append({
                "phase": current_phase.value,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            })
            save_state(state)

            # Update Linear issue to show failed (adds label, tags operator)
            _update_linear_phase_status(
                state, current_phase, "failed",
                str(e),
                mention_user="sang",  # Tag operator for failure review
            )

            # Send failure notification with resume option
            if channel_id:
                _notify_failure(channel_id, state, str(e))

            return state

        # Move to next phase
        next_phase = _get_next_phase(current_phase)

        if next_phase is None:
            state.completed_at = datetime.utcnow()
            save_state(state)
            logger.info(f"Factory run complete: {state.execution_id}")

            # Mark root issue as complete
            _complete_factory_run_linear(state)

            # Send completion notification
            if channel_id:
                _notify_complete(channel_id, state)

            return state

        state.current_phase = next_phase
        save_state(state)


def resume_factory(
    execution_id: str,
    channel_id: Optional[str] = None,
) -> Optional[FactoryState]:
    """
    Resume a failed or stopped factory run.

    Args:
        execution_id: The execution ID to resume
        channel_id: Slack channel for notifications

    Returns:
        Updated state, or None if execution not found
    """
    state = load_state(execution_id)
    
    if not state:
        logger.error(f"No state found for execution: {execution_id}")
        return None
    
    current_status = state.phase_statuses.get(state.current_phase.value)
    
    if current_status == PhaseStatus.FAILED:
        # Reset failed phase to pending and retry
        logger.info(f"Resuming failed execution {execution_id} from {state.current_phase.value}")
        state.update_phase_status(state.current_phase, PhaseStatus.PENDING)
        save_state(state)
        return run_factory(state, channel_id)
    
    elif current_status == PhaseStatus.AWAITING_APPROVAL:
        logger.info(f"Execution {execution_id} is awaiting approval, not resuming")
        return state
    
    elif current_status == PhaseStatus.COMPLETED:
        # Move to next phase if current is complete
        next_phase = _get_next_phase(state.current_phase)
        if next_phase:
            state.current_phase = next_phase
            save_state(state)
            return run_factory(state, channel_id)
        else:
            logger.info(f"Execution {execution_id} is already complete")
            return state
    
    else:
        # Continue from current state
        return run_factory(state, channel_id)


def approve_checkpoint(
    state: FactoryState,
    phase: Phase,
    channel_id: Optional[str] = None,
) -> FactoryState:
    """Approve a checkpoint and continue execution."""
    if state.phase_statuses.get(phase.value) != PhaseStatus.AWAITING_APPROVAL:
        raise ValueError(f"Phase {phase.value} is not awaiting approval")

    state.clear_checkpoint(phase.value)
    state.update_phase_status(phase, PhaseStatus.APPROVED)
    save_state(state)

    logger.info(f"Checkpoint {phase.value} approved, continuing...")

    # Continue execution
    return run_factory(state, channel_id)


def get_failed_runs() -> list[dict]:
    """Get all failed factory runs that can be resumed."""
    return list_states(status_filter="failed")


def get_pending_runs() -> list[dict]:
    """Get all runs awaiting approval."""
    return list_states(status_filter="awaiting_approval")


def cleanup_old_runs(days: int = 30) -> int:
    """Delete factory runs older than specified days."""
    from datetime import timedelta
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    deleted = 0
    
    for run in list_states():
        started = datetime.fromisoformat(run["started_at"])
        if started < cutoff:
            delete_state(run["execution_id"])
            deleted += 1
    
    logger.info(f"Cleaned up {deleted} old factory runs")
    return deleted


def _requires_approval(state: FactoryState, phase: Phase) -> bool:
    """Check if phase requires human approval."""
    # Check if already approved
    if phase.value in state.checkpoints_cleared:
        return False

    # Check if phase is in approval list
    approval_checkpoints = state.handoff.approval_checkpoints
    phase_name = phase.value.replace("_", "")  # Match format like "design", "build"

    for checkpoint in approval_checkpoints:
        if checkpoint.lower() in phase_name:
            return True

    return False


def _execute_phase(state: FactoryState, phase: Phase) -> dict:
    """Execute a single phase."""
    logger.info(f"Executing phase: {phase.value}")

    if phase == Phase.BUILD:
        # Composite phase: Code → QA → Test → Security → DevOps
        outputs = {}

        # 1. Generate code
        code_agent = CodeAgent()
        outputs["code"] = code_agent.run(state)

        # Store github repo info for other agents (TestAgent, DevOpsAgent, QAAgent)
        code_output = outputs["code"]
        state.github_repo = {
            "owner": code_output.get("github_owner", ""),
            "name": code_output.get("github_repo_name", ""),
            "url": code_output.get("github_repo_url", ""),
        }
        state.store_output(Phase.BUILD, outputs)

        # 2. QA validation and auto-remediation (validates deps, structure, pushes fixes)
        qa_agent = QAAgent()
        outputs["qa"] = qa_agent.run(state)

        logger.info(
            f"QA: {len(outputs['qa'].get('issues_found', []))} found, "
            f"{len(outputs['qa'].get('issues_fixed', []))} fixed, "
            f"{len(outputs['qa'].get('issues_unfixable', []))} unfixable"
        )

        # 3. Generate and push tests
        test_agent = TestAgent()
        outputs["test"] = test_agent.run(state)

        # 4. Security scan
        security_agent = SecurityAgent()
        outputs["security"] = security_agent.run(state)

        # 5. DevOps configuration
        devops_agent = DevOpsAgent()
        outputs["devops"] = devops_agent.run(state)

        return outputs

    elif phase == Phase.LAUNCH_PREP:
        # Composite: Marketing + Launch prep
        outputs = {}

        marketing_agent = MarketingAgent()
        outputs["marketing"] = marketing_agent.run(state)
        state.store_output(Phase.LAUNCH_PREP, outputs)

        return outputs

    elif phase == Phase.GROWTH:
        # Composite: Growth + Support
        outputs = {}

        growth_agent = GrowthAgent()
        outputs["growth"] = growth_agent.run(state)

        support_agent = SupportAgent()
        outputs["support"] = support_agent.run(state)

        return outputs

    else:
        # Single agent phase
        config = PHASE_CONFIG.get(phase)
        if not config or not config["agent"]:
            return {}

        agent = config["agent"]()
        return agent.run(state)


def _get_next_phase(current: Phase) -> Optional[Phase]:
    """Get the next phase in the pipeline."""
    try:
        current_idx = PHASE_ORDER.index(current)
        if current_idx + 1 < len(PHASE_ORDER):
            return PHASE_ORDER[current_idx + 1]
    except ValueError:
        pass
    return None


# Notification helpers
def _notify_checkpoint(channel_id: str, state: FactoryState):
    """Send checkpoint approval request."""
    try:
        from src.slack.notifications import send_checkpoint_request
        send_checkpoint_request(channel_id, state)
    except Exception as e:
        logger.error(f"Failed to send checkpoint notification: {e}")


def _notify_phase_complete(channel_id: str, state: FactoryState, phase: Phase):
    """Send phase completion notification."""
    try:
        from src.slack.notifications import send_phase_update
        send_phase_update(channel_id, state, phase)
    except Exception as e:
        logger.error(f"Failed to send phase notification: {e}")


def _notify_failure(channel_id: str, state: FactoryState, error: str):
    """Send failure notification with resume option."""
    try:
        from src.slack.app import app
        
        app.client.chat_postMessage(
            channel=channel_id,
            text=f"❌ Factory failed at {state.current_phase.value}",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "❌ Factory Execution Failed",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Phase:*\n{state.current_phase.value.replace('_', ' ').title()}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Product:*\n{state.handoff.opportunity.name}",
                        },
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Error:*\n```{error[:500]}```",
                    },
                },
                {"type": "divider"},
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "🔄 Resume Factory"},
                            "style": "primary",
                            "value": state.execution_id,
                            "action_id": "resume_factory",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "📋 View in Linear"},
                            "url": state.handoff.linear_project_url,
                            "action_id": "view_linear",
                        },
                    ],
                },
            ],
        )
    except Exception as e:
        logger.error(f"Failed to send failure notification: {e}")


def _notify_complete(channel_id: str, state: FactoryState):
    """Send completion notification."""
    try:
        from src.slack.notifications import send_factory_complete
        send_factory_complete(channel_id, state)
    except Exception as e:
        logger.error(f"Failed to send completion notification: {e}")


def _update_linear_phase_status(
    state: FactoryState,
    phase: Phase,
    status: str,
    message: Optional[str] = None,
    assign_to: Optional[str] = None,
    mention_user: Optional[str] = None,
    output_links: Optional[list[str]] = None,
):
    """
    Update the Linear issue for a phase with current status.

    Args:
        state: Factory state with phase issues
        phase: Current phase
        status: One of 'started', 'in_progress', 'completed', 'failed', 'blocked', 'awaiting_review'
        message: Optional progress message
        assign_to: Optional user name to assign the issue to (for reviews)
        mention_user: Optional user name to @ mention in comment (for failures/reviews)
        output_links: Optional list of output artifact URLs to link
    """
    try:
        phase_info = state.linear_phase_issues.get(phase.value)
        if not phase_info:
            logger.debug(f"No Linear issue found for phase {phase.value}")
            return

        phase_issue_id = phase_info.get("id")
        if not phase_issue_id or not state.linear_team_id:
            return

        linear.update_phase_issue(
            phase_issue_id=phase_issue_id,
            team_id=state.linear_team_id,
            status=status,
            progress_message=message,
            execution_id=state.execution_id if status == "failed" else None,
            assign_to=assign_to,
            mention_user=mention_user,
            output_links=output_links,
        )

    except Exception as e:
        logger.warning(f"Failed to update Linear phase status: {e}")


def _complete_factory_run_linear(state: FactoryState):
    """Mark the root factory issue as complete in Linear."""
    try:
        root_info = state.linear_phase_issues.get("root")
        if not root_info or not state.linear_team_id:
            return

        root_id = root_info.get("id")
        if root_id:
            linear.complete_issue(root_id, state.linear_team_id)

            # Add completion summary
            linear.add_comment(
                root_id,
                f"""## ✅ Factory Run Complete

All phases have completed successfully.

**Product:** {state.handoff.opportunity.name}
**Duration:** Started at {state.started_at.isoformat()}
**Completed:** {state.completed_at.isoformat() if state.completed_at else 'now'}

---
*Vineyard Factory*
"""
            )

    except Exception as e:
        logger.warning(f"Failed to complete factory root issue: {e}")


def _get_phase_summary(phase: Phase, output) -> str:
    """Generate a summary of phase output for Linear comment."""
    from dataclasses import asdict, is_dataclass

    if not output:
        return "Phase completed successfully."

    # Convert dataclasses, Pydantic models to dict for uniform handling
    if is_dataclass(output) and not isinstance(output, type):
        output = asdict(output)
    elif hasattr(output, "model_dump"):
        output = output.model_dump()
    elif hasattr(output, "dict"):
        output = output.dict()
    elif not isinstance(output, dict):
        return "Phase completed successfully."

    summary_parts = []

    if phase == Phase.RESEARCH_ENRICHMENT:
        summary_parts.append("Research enrichment completed:")
        if output.get("enriched_data"):
            summary_parts.append("- Market data enriched")
        if output.get("competitor_analysis"):
            summary_parts.append("- Competitor analysis updated")

    elif phase == Phase.DESIGN:
        summary_parts.append("Design phase completed:")
        if output.get("prd"):
            summary_parts.append("- PRD generated")
        if output.get("user_flows"):
            summary_parts.append("- User flows created")
        features = output.get("features", [])
        if features:
            summary_parts.append(f"- {len(features)} features specified")

    elif phase == Phase.SPEC:
        summary_parts.append("Technical specification completed:")
        endpoints = output.get("endpoints", [])
        if endpoints:
            summary_parts.append(f"- {len(endpoints)} API endpoints designed")
        database = output.get("database", {})
        if database:
            tables = database.get("tables", []) if isinstance(database, dict) else []
            summary_parts.append(f"- {len(tables)} database tables")
        tasks = output.get("tasks", [])
        if tasks:
            summary_parts.append(f"- {len(tasks)} engineering tasks")

    elif phase == Phase.BUILD:
        summary_parts.append("Build phase completed:")
        code = output.get("code", {})
        if code:
            files = code.get("files_generated", []) if isinstance(code, dict) else []
            summary_parts.append(f"- {len(files)} code files generated")
        test = output.get("test", {})
        if test:
            tests = test.get("test_files", []) if isinstance(test, dict) else []
            summary_parts.append(f"- {len(tests)} test files created")
        if output.get("security"):
            summary_parts.append("- Security review complete")
        if output.get("devops"):
            summary_parts.append("- DevOps configuration ready")

    elif phase == Phase.LAUNCH_PREP:
        summary_parts.append("Launch preparation completed:")
        if output.get("marketing"):
            summary_parts.append("- Marketing content ready")

    elif phase == Phase.LAUNCH:
        summary_parts.append("Launch completed:")
        summary_parts.append("- Product deployed to production")

    elif phase == Phase.GROWTH:
        summary_parts.append("Growth setup completed:")
        if output.get("growth"):
            summary_parts.append("- Growth experiments configured")
        if output.get("support"):
            summary_parts.append("- Support documentation ready")

    return "\n".join(summary_parts) if summary_parts else "Phase completed successfully."


def add_work_items_to_phase(
    state: FactoryState,
    phase: Phase,
    work_items: list[dict],
) -> list[dict]:
    """
    Add work item issues to a phase during execution.

    This is called by agents to create sub-issues for actual work items.

    Args:
        state: Factory state
        phase: The phase these items belong to
        work_items: List of {"title": str, "description": str, "priority": int}

    Returns:
        List of created issue dicts with id, identifier, url
    """
    if not state.handoff.linear_project_id or not state.linear_team_id:
        return []

    phase_info = state.linear_phase_issues.get(phase.value)
    if not phase_info:
        return []

    phase_id = phase_info.get("id")
    if not phase_id:
        return []

    try:
        label = linear.PHASE_ISSUE_CONFIG.get(phase.value, {}).get("label", "phase")

        created = linear.create_work_items(
            project_id=state.handoff.linear_project_id,
            team_id=state.linear_team_id,
            phase_issue_id=phase_id,
            work_items=work_items,
            label=label,
        )

        # Track created issues in state
        if phase.value not in state.linear_issues:
            state.linear_issues[phase.value] = []
        state.linear_issues[phase.value].extend([i.get("id") for i in created if i.get("id")])

        save_state(state)
        return created

    except Exception as e:
        logger.warning(f"Failed to add work items to phase: {e}")
        return []


def start_work_item(state: FactoryState, issue_id: str) -> bool:
    """Mark a work item as in-progress."""
    if not state.linear_team_id:
        return False
    try:
        return linear.start_issue(issue_id, state.linear_team_id)
    except Exception as e:
        logger.warning(f"Failed to start work item: {e}")
        return False


def complete_work_item(state: FactoryState, issue_id: str) -> bool:
    """Mark a work item as done."""
    if not state.linear_team_id:
        return False
    try:
        return linear.complete_issue(issue_id, state.linear_team_id)
    except Exception as e:
        logger.warning(f"Failed to complete work item: {e}")
        return False
