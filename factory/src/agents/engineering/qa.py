"""QA Agent - Validates, remediates, and tracks code quality issues for Rails.

Supports two modes:
1. Agent SDK mode: Claude autonomously validates and fixes issues (adaptive)
2. Direct mode: Sequential validation steps (fallback)
"""

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from src.agents.base import BaseAgent
from src.config import settings
from src.config.prompts import QA_AGENT_PROMPT
from src.models import FactoryState, GeneratedFile
from src.tools import github, linear, llm


class IssueSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    WARNING = "warning"


class IssueType(str, Enum):
    MISSING_DEPENDENCY = "missing_dependency"
    VULNERABLE_DEPENDENCY = "vulnerable_dependency"
    MISSING_STRUCTURE = "missing_structure"
    BUILD_ERROR = "build_error"
    LINT_ERROR = "lint_error"
    TEST_FAILURE = "test_failure"
    SECURITY_ISSUE = "security_issue"
    MISSING_ROUTE = "missing_route"
    PUSH_FAILED = "push_failed"
    DECISION_REQUIRED = "decision_required"


@dataclass
class QAIssue:
    """Represents a QA issue found during validation."""
    severity: IssueSeverity
    issue_type: IssueType
    message: str
    file: Optional[str] = None
    details: Optional[dict] = None
    linear_issue_id: Optional[str] = None
    fixed: bool = False
    fix_action: Optional[str] = None


class QAValidationError(Exception):
    """Raised when QA validation fails with unfixable critical issues."""

    def __init__(self, message: str, issues: list[QAIssue]):
        super().__init__(message)
        self.issues = issues


class QAAgent(BaseAgent):
    """
    Agent that validates generated Rails code, auto-remediates issues,
    and tracks progress in Linear.
    """

    name = "QAAgent"
    domain = "engineering"

    # Required Rails files
    REQUIRED_FILES = {
        "Gemfile": {
            "severity": IssueSeverity.CRITICAL,
            "description": "Ruby dependencies file",
        },
        "config/routes.rb": {
            "severity": IssueSeverity.CRITICAL,
            "description": "Rails routes configuration",
        },
        "config/database.yml": {
            "severity": IssueSeverity.HIGH,
            "description": "Database configuration",
        },
        "app/controllers/application_controller.rb": {
            "severity": IssueSeverity.CRITICAL,
            "description": "Base controller",
        },
        "app/models/application_record.rb": {
            "severity": IssueSeverity.CRITICAL,
            "description": "Base model",
        },
        "app/views/layouts/application.html.erb": {
            "severity": IssueSeverity.HIGH,
            "description": "Main layout template",
        },
    }

    # Recommended files
    RECOMMENDED_FILES = {
        "config/initializers/devise.rb": {
            "severity": IssueSeverity.MEDIUM,
            "description": "Devise auth configuration",
        },
        "public/404.html": {
            "severity": IssueSeverity.LOW,
            "description": "Custom 404 page",
        },
        "public/500.html": {
            "severity": IssueSeverity.LOW,
            "description": "Custom 500 page",
        },
        ".rubocop.yml": {
            "severity": IssueSeverity.LOW,
            "description": "RuboCop linting configuration",
        },
    }

    # Required gems for Rails app
    REQUIRED_GEMS = {
        "rails": "~> 7.1",
        "pg": "~> 1.5",
        "puma": "~> 6.4",
        "turbo-rails": None,
        "stimulus-rails": None,
        "tailwindcss-rails": None,
    }

    def __init__(self):
        super().__init__()
        self.issues: list[QAIssue] = []
        self.files_modified: list[str] = []
        self.linear_tracker = None
        self.qa_task_id: Optional[str] = None

    def run(self, state: FactoryState) -> dict[str, Any]:
        """
        Validate and remediate generated Rails code.
        """
        self.log_start()

        build_output = self.get_previous_output(state, "build")
        code_output = build_output.get("code", {})
        files = code_output.get("files", [])

        repo_info = state.github_repo
        if not repo_info or not repo_info.get("owner"):
            raise RuntimeError("No GitHub repo info available - CodeAgent must run first")

        # Initialize Linear tracking
        self._init_linear_tracking(state)

        # Convert to mutable dict for modifications
        files_dict = {f.path: f for f in files}

        # Create QA parent task in Linear
        self._create_qa_task(state)

        try:
            # Run validations with Linear subtask tracking
            self._run_validation_with_tracking(
                "gemfile_check",
                "Check and fix Gemfile dependencies",
                lambda: self._fix_gemfile(files_dict, state)
            )

            self._run_validation_with_tracking(
                "structure_check",
                "Check and fix project structure",
                lambda: self._fix_missing_structure(files_dict, state)
            )

            self._run_validation_with_tracking(
                "routes_check",
                "Verify routes configuration",
                lambda: self._verify_routes(files_dict, state)
            )

            # Push fixes to GitHub
            if self.files_modified:
                self._run_validation_with_tracking(
                    "push_fixes",
                    "Push fixes to GitHub",
                    lambda: self._push_fixes_to_github(files_dict, repo_info)
                )

            # Full build validation - use Agent SDK if available
            self._run_validation_with_tracking(
                "full_build_validation",
                "Clone and validate build (bundle, rubocop, rspec)",
                lambda: self._full_build_validation(repo_info, files_dict, state)
            )

            # Complete QA task
            self._complete_qa_task(state)

        except Exception as e:
            self._fail_qa_task(state, str(e))
            raise

        # Collect results
        issues_found = [i for i in self.issues]
        issues_fixed = [i for i in self.issues if i.fixed]
        issues_unfixable = [i for i in self.issues if not i.fixed and i.severity in [IssueSeverity.CRITICAL, IssueSeverity.HIGH]]

        # Fail only if there are unfixable critical issues
        critical_unfixed = [i for i in issues_unfixable if i.severity == IssueSeverity.CRITICAL]
        if critical_unfixed:
            raise QAValidationError(
                f"QA found {len(critical_unfixed)} unfixable critical issues",
                critical_unfixed
            )

        self.log_complete()

        return {
            "issues_found": [self._issue_to_dict(i) for i in issues_found],
            "issues_fixed": [self._issue_to_dict(i) for i in issues_fixed],
            "issues_unfixable": [self._issue_to_dict(i) for i in issues_unfixable],
            "files_modified": self.files_modified,
            "build_verified": not any(
                i.issue_type == IssueType.BUILD_ERROR and not i.fixed
                for i in self.issues
            ),
        }

    # =========================================================================
    # Full Build Validation
    # =========================================================================

    def _full_build_validation(
        self,
        repo_info: dict,
        files_dict: dict[str, GeneratedFile],
        state: FactoryState,
    ) -> None:
        """Run full build validation. Uses Agent SDK if available, otherwise direct."""
        from src.tools.agent_runner import is_sdk_available
        if is_sdk_available():
            self.logger.info("Using Agent SDK for adaptive build validation")
            self._full_build_validation_agent(repo_info, state)
        else:
            self.logger.info("Using direct build validation")
            self._full_build_validation_direct(repo_info, files_dict, state)

    def _full_build_validation_agent(
        self,
        repo_info: dict,
        state: FactoryState,
    ) -> None:
        """Use Agent SDK for adaptive build validation.

        Claude gets tools to run commands, read/write files, and report issues.
        It can adaptively fix problems as it finds them.
        """
        import os
        import subprocess
        import tempfile

        from src.tools import agent_tools
        from src.tools.agent_runner import run_agent

        self.logger.info("Starting Agent SDK build validation...")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Clone the repo
            token = settings.github_token
            if token:
                clone_url = f"https://{token}@github.com/{repo_info['owner']}/{repo_info['name']}.git"
            else:
                clone_url = f"https://github.com/{repo_info['owner']}/{repo_info['name']}.git"

            clone_result = subprocess.run(
                ["git", "clone", "--depth=1", clone_url, tmpdir],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if clone_result.returncode != 0:
                error_msg = clone_result.stderr.replace(token, "***") if token else clone_result.stderr
                self._add_issue(
                    IssueSeverity.CRITICAL,
                    IssueType.BUILD_ERROR,
                    f"Failed to clone repo: {error_msg[:200]}",
                )
                return

            # Configure git
            subprocess.run(["git", "config", "user.email", "factory@vineyard.dev"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Vineyard Factory"], cwd=tmpdir, capture_output=True)

            # Set up tool state
            agent_tools.reset_state()
            agent_tools._generation_state["project_dir"] = tmpdir

            # Get QA tools
            tools = agent_tools.get_qa_tools()

            prompt = f"""Validate and fix this Ruby on Rails 7.1 application.

The project has been cloned to the working directory. Run these validation steps in order:

1. **bundle install** - Install dependencies. If it fails, read the Gemfile and fix issues.
2. **bundle audit check --update** - Check for vulnerable dependencies. Report any CVEs found.
3. **bundle exec rubocop -A --format simple** - Run linter with auto-fix. Report remaining offenses.
4. **bundle exec brakeman -q --no-pager** - Security scan. Report any warnings.
5. **bundle exec rspec --format progress** - Run tests. If tests fail, try to fix obvious issues.
6. **RAILS_ENV=production SECRET_KEY_BASE_DUMMY=1 bundle exec rails assets:precompile** - Verify production build.

For each step:
- If it fails, read the error output carefully
- Try to fix the issue by modifying the relevant file
- Re-run the step to verify the fix
- Use `report_issue` to record each issue found (whether fixed or not)

After all steps, commit and push any fixes:
```
git add .
git commit -m "fix(qa): Auto-remediation by QA agent"
git push
```

Be thorough but efficient. Fix what you can, report what you can't."""

            try:
                result = run_agent(
                    prompt=prompt,
                    system_prompt=QA_AGENT_PROMPT,
                    tools=tools,
                    model="sonnet",
                    max_turns=40,
                    max_budget_usd=3.0,
                    cwd=tmpdir,
                )

                self.logger.info(
                    f"Agent SDK validation completed in {result.turns} turns, "
                    f"cost: ${result.cost_usd:.4f}"
                )

                # Collect issues from tool state
                qa_issues = agent_tools._generation_state.get("qa_issues", [])
                for issue_data in qa_issues:
                    severity = IssueSeverity(issue_data.get("severity", "medium"))
                    issue = self._add_issue(
                        severity,
                        IssueType(issue_data.get("issue_type", "build_error")),
                        issue_data["message"],
                        file=issue_data.get("file"),
                    )
                    if issue_data.get("fixed"):
                        self._mark_issue_fixed(issue, issue_data.get("fix_action", "Auto-fixed by agent"))

                # Track modified files
                modified = agent_tools._generation_state.get("files_modified", [])
                self.files_modified.extend(modified)

            except Exception as e:
                self.logger.error(f"Agent SDK validation failed: {e}")
                # Fall back to direct validation
                self.logger.info("Falling back to direct build validation")
                self._full_build_validation_direct(repo_info, files_dict={}, state=state)

    def _full_build_validation_direct(
        self,
        repo_info: dict,
        files_dict: dict[str, GeneratedFile],
        state: FactoryState,
    ) -> None:
        """Direct build validation (original approach)."""
        import os
        import subprocess
        import tempfile

        self.logger.info("Starting direct build validation for Rails...")

        local_fixes_made = False

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                token = settings.github_token
                if token:
                    clone_url = f"https://{token}@github.com/{repo_info['owner']}/{repo_info['name']}.git"
                else:
                    clone_url = f"https://github.com/{repo_info['owner']}/{repo_info['name']}.git"

                self.logger.info("Cloning repository...")
                clone_result = subprocess.run(
                    ["git", "clone", "--depth=1", clone_url, tmpdir],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                if clone_result.returncode != 0:
                    error_msg = clone_result.stderr.replace(token, "***") if token else clone_result.stderr
                    self._add_issue(
                        IssueSeverity.CRITICAL,
                        IssueType.BUILD_ERROR,
                        f"Failed to clone repo: {error_msg[:200]}",
                    )
                    return

                subprocess.run(["git", "config", "user.email", "factory@vineyard.dev"], cwd=tmpdir, capture_output=True)
                subprocess.run(["git", "config", "user.name", "Vineyard Factory"], cwd=tmpdir, capture_output=True)

                # 1. bundle install
                self.logger.info("Running bundle install...")
                install_result = subprocess.run(
                    ["bundle", "install"],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

                if install_result.returncode != 0:
                    self._add_issue(
                        IssueSeverity.CRITICAL,
                        IssueType.BUILD_ERROR,
                        "bundle install failed",
                        details={"stderr": install_result.stderr[:500]},
                    )
                    return

                # 2. bundle audit
                self.logger.info("Running bundle audit...")
                audit_result = subprocess.run(
                    ["bundle", "audit", "check", "--update"],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                if audit_result.returncode != 0:
                    for line in audit_result.stdout.split("\n"):
                        if "CVE-" in line or "GHSA-" in line:
                            self._add_issue(
                                IssueSeverity.HIGH,
                                IssueType.VULNERABLE_DEPENDENCY,
                                f"Security vulnerability: {line[:100]}",
                            )

                # 3. RuboCop with auto-fix
                self.logger.info("Running bundle exec rubocop -A...")
                rubocop_result = subprocess.run(
                    ["bundle", "exec", "rubocop", "-A", "--format", "simple"],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )

                status_result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                )
                if status_result.stdout.strip():
                    local_fixes_made = True

                if rubocop_result.returncode != 0:
                    offense_pattern = r'([^:]+):(\d+):\d+:\s+(\w):\s+(.+)'
                    for match in re.finditer(offense_pattern, rubocop_result.stdout):
                        severity = IssueSeverity.HIGH if match.group(3) == 'E' else IssueSeverity.MEDIUM
                        self._add_issue(
                            severity,
                            IssueType.LINT_ERROR,
                            f"{match.group(4)}",
                            file=match.group(1),
                        )

                # 4. Brakeman
                self.logger.info("Running bundle exec brakeman...")
                brakeman_result = subprocess.run(
                    ["bundle", "exec", "brakeman", "-q", "--no-pager", "--format", "json"],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )

                if brakeman_result.returncode != 0:
                    try:
                        brakeman_data = json.loads(brakeman_result.stdout)
                        for warning in brakeman_data.get("warnings", [])[:5]:
                            self._add_issue(
                                IssueSeverity.HIGH,
                                IssueType.SECURITY_ISSUE,
                                f"Brakeman: {warning.get('message', 'Security issue')}",
                                file=warning.get("file"),
                                details=warning,
                            )
                    except json.JSONDecodeError:
                        pass

                # 5. RSpec tests
                self.logger.info("Running bundle exec rspec...")
                test_result = subprocess.run(
                    ["bundle", "exec", "rspec", "--format", "progress"],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    env={**os.environ, "RAILS_ENV": "test"},
                )

                if test_result.returncode != 0:
                    failure_pattern = r'rspec\s+([^\s:]+):(\d+)'
                    for match in re.finditer(failure_pattern, test_result.stdout):
                        self._add_issue(
                            IssueSeverity.HIGH,
                            IssueType.TEST_FAILURE,
                            f"Test failed at line {match.group(2)}",
                            file=match.group(1),
                        )
                else:
                    self.logger.info("All tests passed!")

                # 6. Asset precompilation
                self.logger.info("Running assets:precompile...")
                build_result = subprocess.run(
                    ["bundle", "exec", "rails", "assets:precompile"],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    env={**os.environ, "RAILS_ENV": "production", "SECRET_KEY_BASE_DUMMY": "1"},
                )

                if build_result.returncode != 0:
                    self._add_issue(
                        IssueSeverity.CRITICAL,
                        IssueType.BUILD_ERROR,
                        "Asset precompilation failed",
                        details={"stderr": build_result.stderr[:500]},
                    )
                    return

                self.logger.info("Build passed!")

                # 7. Commit and push fixes
                if local_fixes_made:
                    self.logger.info("Committing and pushing local fixes...")
                    subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
                    commit_result = subprocess.run(
                        ["git", "commit", "-m", "fix(qa): Auto-remediation by QA agent\n\n- rubocop -A"],
                        cwd=tmpdir,
                        capture_output=True,
                        text=True,
                    )

                    if commit_result.returncode == 0:
                        push_result = subprocess.run(
                            ["git", "push"],
                            cwd=tmpdir,
                            capture_output=True,
                            text=True,
                            timeout=60,
                        )

                        if push_result.returncode == 0:
                            self.logger.info("Successfully pushed local fixes to GitHub")
                        else:
                            error_msg = push_result.stderr.replace(token, "***") if token else push_result.stderr
                            self._add_issue(
                                IssueSeverity.WARNING,
                                IssueType.PUSH_FAILED,
                                f"Failed to push local fixes: {error_msg[:200]}",
                            )

                self.logger.info("Full build validation completed!")

        except subprocess.TimeoutExpired as e:
            self._add_issue(
                IssueSeverity.WARNING,
                IssueType.BUILD_ERROR,
                f"Build validation timed out at step: {e.cmd[0] if e.cmd else 'unknown'}",
            )
        except Exception as e:
            self._add_issue(
                IssueSeverity.WARNING,
                IssueType.BUILD_ERROR,
                f"Build validation error: {e}",
            )

    # =========================================================================
    # Linear Tracking Methods
    # =========================================================================

    def _init_linear_tracking(self, state: FactoryState) -> None:
        """Initialize Linear tracker from state."""
        if state.linear_phase_issues and state.linear_team_id:
            self.linear_tracker = linear.FactoryLinearTracker(
                project_id=state.handoff.linear_project_id,
                product_name=state.handoff.prd_input.name,
                execution_id=state.execution_id,
            )
            self.linear_tracker.team_id = state.linear_team_id
            self.linear_tracker.phase_issues = state.linear_phase_issues

    def _create_qa_task(self, state: FactoryState) -> None:
        """Create QA validation task in Linear under BUILD phase."""
        if not self.linear_tracker or not self.linear_tracker.team_id:
            return

        build_phase_id = state.linear_phase_issues.get("build", {}).get("id")
        if not build_phase_id:
            return

        qa_issue = linear.create_issue(
            project_id=state.handoff.linear_project_id,
            team_id=self.linear_tracker.team_id,
            title="🔍 QA Validation & Auto-Remediation",
            description="""## QA Validation

Automated quality assurance for Rails that:
1. Validates Gemfile dependencies
2. Checks for security vulnerabilities (bundle audit)
3. Ensures required files exist
4. Runs RuboCop linting
5. Runs RSpec tests
6. Verifies build passes

Issues found will be auto-fixed when possible.
""",
            labels=["build", "qa"],
            priority=2,
            state_name="in_progress",
            parent_id=build_phase_id,
            assignee_name="vineyard",
        )

        if qa_issue:
            self.qa_task_id = qa_issue.get("id")
            self.logger.info(f"Created QA task: {qa_issue.get('identifier')}")

    def _run_validation_with_tracking(
        self,
        task_key: str,
        task_title: str,
        validation_fn: callable,
    ) -> None:
        """Run a validation step with Linear subtask tracking."""
        subtask_id = None

        if self.linear_tracker and self.qa_task_id:
            subtask = linear.create_issue(
                project_id=self.linear_tracker.project_id,
                team_id=self.linear_tracker.team_id,
                title=task_title,
                description=f"QA subtask: {task_title}",
                labels=["qa"],
                priority=3,
                state_name="in_progress",
                parent_id=self.qa_task_id,
                assignee_name="vineyard",
            )
            if subtask:
                subtask_id = subtask.get("id")

        try:
            validation_fn()

            if subtask_id and self.linear_tracker:
                linear.complete_issue(subtask_id, self.linear_tracker.team_id)

        except Exception as e:
            if subtask_id and self.linear_tracker:
                linear.add_comment(subtask_id, f"❌ Failed: {str(e)}")
            raise

    def _complete_qa_task(self, state: FactoryState) -> None:
        """Complete the QA task with summary."""
        if not self.qa_task_id or not self.linear_tracker:
            return

        fixed_count = len([i for i in self.issues if i.fixed])
        unfixed_count = len([i for i in self.issues if not i.fixed])

        summary = f"""## ✅ QA Validation Complete

**Issues Found:** {len(self.issues)}
**Auto-Fixed:** {fixed_count}
**Remaining:** {unfixed_count}
**Files Modified:** {len(self.files_modified)}
"""

        linear.add_comment(self.qa_task_id, summary)
        linear.complete_issue(self.qa_task_id, self.linear_tracker.team_id)

    def _fail_qa_task(self, state: FactoryState, error: str) -> None:
        """Mark QA task as failed and notify operator."""
        if not self.qa_task_id or not self.linear_tracker:
            return

        linear.mention_user_in_comment(
            self.qa_task_id,
            "sang",
            f"## ❌ QA Validation Failed\n\n**Error:** {error}"
        )

    # =========================================================================
    # Issue Tracking Methods
    # =========================================================================

    def _add_issue(
        self,
        severity: IssueSeverity,
        issue_type: IssueType,
        message: str,
        file: Optional[str] = None,
        details: Optional[dict] = None,
        create_linear_issue: bool = True,
    ) -> QAIssue:
        """Add an issue and optionally create Linear bug."""
        issue = QAIssue(
            severity=severity,
            issue_type=issue_type,
            message=message,
            file=file,
            details=details,
        )
        self.issues.append(issue)

        if create_linear_issue and severity in [IssueSeverity.CRITICAL, IssueSeverity.HIGH]:
            if self.linear_tracker and self.qa_task_id:
                severity_emoji = "🔴" if severity == IssueSeverity.CRITICAL else "🟠"
                bug_issue = linear.create_issue(
                    project_id=self.linear_tracker.project_id,
                    team_id=self.linear_tracker.team_id,
                    title=f"{severity_emoji} [{issue_type.value}] {message[:80]}",
                    description=f"**Severity:** {severity.value}\n**File:** {file or 'N/A'}\n\n{message}",
                    labels=["bug", "qa"],
                    priority=1 if severity == IssueSeverity.CRITICAL else 2,
                    state_name="todo",
                    parent_id=self.qa_task_id,
                )
                if bug_issue:
                    issue.linear_issue_id = bug_issue.get("id")

        return issue

    def _mark_issue_fixed(self, issue: QAIssue, fix_action: str) -> None:
        """Mark an issue as fixed and update Linear."""
        issue.fixed = True
        issue.fix_action = fix_action

        if issue.linear_issue_id and self.linear_tracker:
            linear.add_comment(issue.linear_issue_id, f"✅ Auto-fixed: {fix_action}")
            linear.complete_issue(issue.linear_issue_id, self.linear_tracker.team_id)

    # =========================================================================
    # Validation Methods
    # =========================================================================

    def _fix_gemfile(
        self, files_dict: dict[str, GeneratedFile], state: FactoryState
    ) -> None:
        """Validate and fix Gemfile."""
        gemfile = files_dict.get("Gemfile")
        if not gemfile:
            self._add_issue(
                IssueSeverity.CRITICAL,
                IssueType.MISSING_STRUCTURE,
                "No Gemfile found",
            )
            return

        content = gemfile.content
        modified = False

        for gem, version in self.REQUIRED_GEMS.items():
            gem_pattern = rf'gem\s+["\']{ re.escape(gem)}["\']'
            if not re.search(gem_pattern, content):
                issue = self._add_issue(
                    IssueSeverity.HIGH,
                    IssueType.MISSING_DEPENDENCY,
                    f"Required gem '{gem}' not in Gemfile",
                    file="Gemfile",
                )

                if version:
                    gem_line = f'gem "{gem}", "{version}"'
                else:
                    gem_line = f'gem "{gem}"'

                if 'source "https://rubygems.org"' in content:
                    content = content.replace(
                        'source "https://rubygems.org"',
                        f'source "https://rubygems.org"\n\n{gem_line}'
                    )
                else:
                    content = gem_line + "\n" + content

                modified = True
                self._mark_issue_fixed(issue, f"Added {gem} to Gemfile")

        if modified:
            files_dict["Gemfile"] = GeneratedFile(
                path="Gemfile",
                content=content,
                language="ruby",
            )
            if "Gemfile" not in self.files_modified:
                self.files_modified.append("Gemfile")

    def _fix_missing_structure(
        self, files_dict: dict[str, GeneratedFile], state: FactoryState
    ) -> None:
        """Detect and generate missing structural files."""
        for path, info in self.REQUIRED_FILES.items():
            if path not in files_dict:
                issue = self._add_issue(
                    info["severity"],
                    IssueType.MISSING_STRUCTURE,
                    f"Missing required file: {path} - {info['description']}",
                    file=path,
                )

                content = self._generate_missing_file(path, state)
                if content:
                    files_dict[path] = GeneratedFile(
                        path=path,
                        content=content,
                        language=self._get_language(path),
                    )
                    self.files_modified.append(path)
                    self._mark_issue_fixed(issue, f"Generated {path}")

        for path, info in self.RECOMMENDED_FILES.items():
            if path not in files_dict:
                self._add_issue(
                    info["severity"],
                    IssueType.MISSING_STRUCTURE,
                    f"Missing recommended file: {path} - {info['description']}",
                    file=path,
                    create_linear_issue=False,
                )

    def _get_language(self, path: str) -> str:
        """Get language based on file extension."""
        if path.endswith(".rb"):
            return "ruby"
        elif path.endswith(".erb"):
            return "erb"
        elif path.endswith(".yml") or path.endswith(".yaml"):
            return "yaml"
        elif path.endswith(".html"):
            return "html"
        return "text"

    def _generate_missing_file(
        self, path: str, state: FactoryState
    ) -> Optional[str]:
        """Generate content for a missing file."""
        prd_input = state.handoff.prd_input

        templates = {
            "config/routes.rb": '''Rails.application.routes.draw do
  get "health", to: "health#show"
  devise_for :users
  root "pages#home"
  get "pricing", to: "pages#pricing"
  get "about", to: "pages#about"
  authenticate :user do
    get "dashboard", to: "dashboard#show"
    resource :settings, only: [:show, :update]
  end
  namespace :api do
    namespace :v1 do
    end
  end
  namespace :webhooks do
    post "stripe", to: "stripe#create"
  end
end
''',
            "app/controllers/application_controller.rb": '''class ApplicationController < ActionController::Base
  before_action :configure_permitted_parameters, if: :devise_controller?

  protected

  def configure_permitted_parameters
    devise_parameter_sanitizer.permit(:sign_up, keys: [:name])
    devise_parameter_sanitizer.permit(:account_update, keys: [:name])
  end
end
''',
            "app/models/application_record.rb": '''class ApplicationRecord < ActiveRecord::Base
  primary_abstract_class
end
''',
            "app/views/layouts/application.html.erb": f'''<!DOCTYPE html>
<html>
  <head>
    <title>{prd_input.name}</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <%%= csrf_meta_tags %>
    <%%= csp_meta_tag %>
    <%%= stylesheet_link_tag "tailwind", "inter-font", "data-turbo-track": "reload" %>
    <%%= stylesheet_link_tag "application", "data-turbo-track": "reload" %>
    <%%= javascript_importmap_tags %>
  </head>
  <body class="bg-gray-50">
    <%%= render "layouts/flash" %>
    <%%= yield %>
  </body>
</html>
''',
            "config/database.yml": '''default: &default
  adapter: postgresql
  encoding: unicode
  pool: <%%= ENV.fetch("RAILS_MAX_THREADS") { 5 } %>

development:
  <<: *default
  database: app_development

test:
  <<: *default
  database: app_test

production:
  <<: *default
  url: <%%= ENV["DATABASE_URL"] %>
''',
        }

        return templates.get(path)

    def _verify_routes(
        self, files_dict: dict[str, GeneratedFile], state: FactoryState
    ) -> None:
        """Verify routes.rb has essential routes."""
        routes_file = files_dict.get("config/routes.rb")
        if not routes_file:
            return

        content = routes_file.content

        essential_routes = [
            ("root", "Root route"),
            ("devise_for", "Devise authentication"),
            ("health", "Health check endpoint"),
        ]

        for route, description in essential_routes:
            if route not in content:
                self._add_issue(
                    IssueSeverity.MEDIUM,
                    IssueType.MISSING_ROUTE,
                    f"Routes missing {description} ({route})",
                    file="config/routes.rb",
                    create_linear_issue=False,
                )

    def _push_fixes_to_github(
        self, files_dict: dict[str, GeneratedFile], repo_info: dict
    ) -> None:
        """Push all fixed files to GitHub."""
        files_to_push = []

        for path in self.files_modified:
            if path in files_dict:
                files_to_push.append({
                    "path": path,
                    "content": files_dict[path].content,
                    "message": f"fix(qa): Auto-remediate {path}",
                })

        if not files_to_push:
            return

        self.logger.info(f"Pushing {len(files_to_push)} fixed files to GitHub")

        try:
            created = github.create_files_batch(
                owner=repo_info["owner"],
                repo=repo_info["name"],
                files=files_to_push,
            )

            pushed_paths = set(created)
            for path in self.files_modified:
                if path not in pushed_paths:
                    self._add_issue(
                        IssueSeverity.HIGH,
                        IssueType.PUSH_FAILED,
                        f"Failed to push fix for {path}",
                        file=path,
                    )

            self.logger.info(f"Successfully pushed {len(created)} files")

        except Exception as e:
            self.logger.error(f"Failed to push fixes: {e}")
            self._add_issue(
                IssueSeverity.CRITICAL,
                IssueType.PUSH_FAILED,
                f"Failed to push fixes to GitHub: {e}",
            )

    def _issue_to_dict(self, issue: QAIssue) -> dict:
        """Convert QAIssue to dictionary."""
        return {
            "severity": issue.severity.value,
            "type": issue.issue_type.value,
            "message": issue.message,
            "file": issue.file,
            "details": issue.details,
            "fixed": issue.fixed,
            "fix_action": issue.fix_action,
            "linear_issue_id": issue.linear_issue_id,
        }
