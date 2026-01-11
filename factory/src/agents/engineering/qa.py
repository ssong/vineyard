"""QA Agent - Validates, remediates, and tracks code quality issues."""

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from src.agents.base import BaseAgent
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
    MALICIOUS_PACKAGE = "malicious_package"
    MISSING_STRUCTURE = "missing_structure"
    IMPORT_MISMATCH = "import_mismatch"
    AUTH_INCONSISTENCY = "auth_inconsistency"
    BUILD_ERROR = "build_error"
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
    Agent that validates generated code, auto-remediates issues,
    and tracks progress in Linear.

    Features:
    - Creates bug issues in Linear for each problem found
    - Updates subtask status as work progresses
    - Tags operator (@sang) when decisions are needed
    - Refers to design docs for self-remediation
    - Waits for operator input on ambiguous decisions
    """

    name = "QAAgent"
    domain = "engineering"

    # Known vulnerable/malicious packages
    KNOWN_VULNERABLE = {
        "event-stream": "Contained malware in v3.3.6",
        "flatmap-stream": "Malicious package",
        "ua-parser-js": "Compromised in Oct 2021",
        "coa": "Compromised in Nov 2021",
        "rc": "Compromised in Nov 2021",
        "node-ipc": "Contained protestware in v10.1.1+",
        "colors": "Corrupted in v1.4.1+",
        "faker": "Corrupted in v6.6.6",
    }

    # Minimum secure versions for packages with known CVEs
    MIN_SECURE_VERSIONS = {
        "axios": "^1.6.0",
        "jsonwebtoken": "^9.0.0",
        "lodash": "^4.17.21",
        "minimist": "^1.2.8",
        "node-fetch": "^2.7.0",
        "qs": "^6.11.0",
        "semver": "^7.5.4",
        "word-wrap": "^1.2.5",
        "xml2js": "^0.6.0",
        "tough-cookie": "^4.1.3",
        "postcss": "^8.4.31",
        "yaml": "^2.3.2",
        "undici": "^5.26.3",
    }

    # Known good versions for common packages
    KNOWN_VERSIONS = {
        "bcryptjs": "^2.4.3",
        "jsonwebtoken": "^9.0.0",
        "@types/bcryptjs": "^2.4.6",
        "@types/jsonwebtoken": "^9.0.5",
        "ws": "^8.16.0",
        "@types/ws": "^8.5.10",
        "@neondatabase/serverless": "^0.9.0",
        "@prisma/client": "^5.10.0",
        "@prisma/adapter-neon": "^5.10.0",
        "stripe": "^14.14.0",
        "@stripe/stripe-js": "^2.4.0",
        "@clerk/nextjs": "^4.29.0",
        "next": "^14.1.0",
        "react": "^18.2.0",
        "react-dom": "^18.2.0",
        "typescript": "^5.3.0",
        "tailwindcss": "^3.4.0",
        "zod": "^3.22.0",
    }

    def __init__(self):
        super().__init__()
        self.issues: list[QAIssue] = []
        self.files_modified: list[str] = []
        self.linear_tracker: Optional[linear.FactoryLinearTracker] = None
        self.qa_task_id: Optional[str] = None
        self.subtasks: dict[str, str] = {}  # task_key -> linear_issue_id

    def run(self, state: FactoryState) -> dict[str, Any]:
        """
        Validate and remediate generated code.

        Creates Linear issues for tracking, auto-fixes what it can,
        and requests operator input for decisions it can't make.
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
                "dependency_check",
                "Check and fix dependencies",
                lambda: self._fix_missing_dependencies(files_dict, state)
            )

            self._run_validation_with_tracking(
                "vulnerability_check",
                "Check and fix vulnerable packages",
                lambda: self._fix_vulnerable_dependencies(files_dict, state)
            )

            self._run_validation_with_tracking(
                "structure_check",
                "Check and fix project structure",
                lambda: self._fix_missing_structure(files_dict, state)
            )

            self._run_validation_with_tracking(
                "import_check",
                "Check and fix import/export mismatches",
                lambda: self._fix_import_mismatches(files_dict, state)
            )

            self._run_validation_with_tracking(
                "auth_check",
                "Check auth system consistency",
                lambda: self._fix_auth_consistency(files_dict, state)
            )

            # Push fixes to GitHub
            if self.files_modified:
                self._run_validation_with_tracking(
                    "push_fixes",
                    "Push fixes to GitHub",
                    lambda: self._push_fixes_to_github(files_dict, repo_info)
                )

            # Verify build
            self._run_validation_with_tracking(
                "verify_build",
                "Verify build passes",
                lambda: self._verify_build(repo_info, state)
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

    def _init_linear_tracking(self, state: FactoryState) -> None:
        """Initialize Linear tracker from state."""
        if state.linear_phase_issues and state.linear_team_id:
            # We'll use the existing phase tracking
            self.linear_tracker = linear.FactoryLinearTracker(
                project_id=state.handoff.linear_project_id,
                product_name=state.handoff.opportunity.name,
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

        # Create QA parent task
        qa_issue = linear.create_issue(
            project_id=state.handoff.linear_project_id,
            team_id=self.linear_tracker.team_id,
            title="🔍 QA Validation & Auto-Remediation",
            description="""## QA Validation

Automated quality assurance that:
1. Validates dependencies are complete
2. Checks for vulnerable packages
3. Ensures required files exist
4. Verifies import/export consistency
5. Checks auth system consistency
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

        # Create subtask in Linear
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
                self.subtasks[task_key] = subtask_id

        try:
            # Run the validation
            validation_fn()

            # Mark subtask complete
            if subtask_id and self.linear_tracker:
                linear.complete_issue(subtask_id, self.linear_tracker.team_id)

        except Exception as e:
            # Mark subtask failed
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

### Fixed Issues
"""
        for issue in self.issues:
            if issue.fixed:
                summary += f"- ✅ {issue.message}"
                if issue.fix_action:
                    summary += f" → {issue.fix_action}"
                summary += "\n"

        if unfixed_count > 0:
            summary += "\n### Remaining Issues\n"
            for issue in self.issues:
                if not issue.fixed:
                    emoji = "⚠️" if issue.severity == IssueSeverity.WARNING else "❌"
                    summary += f"- {emoji} [{issue.severity.value}] {issue.message}\n"

        linear.add_comment(self.qa_task_id, summary)
        linear.complete_issue(self.qa_task_id, self.linear_tracker.team_id)

    def _fail_qa_task(self, state: FactoryState, error: str) -> None:
        """Mark QA task as failed and notify operator."""
        if not self.qa_task_id or not self.linear_tracker:
            return

        linear.mention_user_in_comment(
            self.qa_task_id,
            "sang",
            f"""## ❌ QA Validation Failed

**Error:** {error}

**Issues Found:** {len(self.issues)}
**Fixed:** {len([i for i in self.issues if i.fixed])}

Please review and address the issues above.
"""
        )

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

        # Create Linear issue for high/critical issues
        if create_linear_issue and severity in [IssueSeverity.CRITICAL, IssueSeverity.HIGH]:
            if self.linear_tracker and self.qa_task_id:
                severity_emoji = "🔴" if severity == IssueSeverity.CRITICAL else "🟠"
                bug_issue = linear.create_issue(
                    project_id=self.linear_tracker.project_id,
                    team_id=self.linear_tracker.team_id,
                    title=f"{severity_emoji} [{issue_type.value}] {message[:80]}",
                    description=f"""## QA Issue

**Severity:** {severity.value}
**Type:** {issue_type.value}
**File:** {file or 'N/A'}

{message}

### Details
```json
{json.dumps(details or {}, indent=2)}
```
""",
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

        # Update Linear issue if exists
        if issue.linear_issue_id and self.linear_tracker:
            linear.add_comment(issue.linear_issue_id, f"✅ Auto-fixed: {fix_action}")
            linear.complete_issue(issue.linear_issue_id, self.linear_tracker.team_id)

    def _request_operator_decision(
        self,
        state: FactoryState,
        question: str,
        options: list[dict],
        context: str,
        timeout_seconds: int = 300,
    ) -> Optional[str]:
        """
        Request a decision from the operator via Linear comment.

        Args:
            state: Factory state
            question: The question to ask
            options: List of {"key": str, "label": str, "description": str}
            context: Additional context about why the decision is needed
            timeout_seconds: How long to wait for a response

        Returns:
            The chosen option key, or None if timeout/error
        """
        if not self.qa_task_id or not self.linear_tracker:
            self.logger.warning("Cannot request decision - no Linear tracking")
            return None

        # Format options
        options_text = "\n".join([
            f"**{i+1}. {opt['label']}**\n   {opt['description']}"
            for i, opt in enumerate(options)
        ])

        comment_body = f"""## 🤔 Decision Required

{question}

### Context
{context}

### Options
{options_text}

---
**Please reply with the number (1, 2, etc.) or option key to continue.**
"""

        # Tag the operator
        linear.mention_user_in_comment(self.qa_task_id, "sang", comment_body)

        # Also add blocked label
        if self.linear_tracker.team_id:
            labels = linear.ensure_labels(self.linear_tracker.team_id, ["blocked", "needs-decision"])
            if "needs-decision" in labels:
                linear._add_label_to_issue(self.qa_task_id, labels["needs-decision"])

        # Poll for response
        start_time = time.time()
        last_check = datetime.utcnow().isoformat()

        self.logger.info(f"Waiting for operator decision (timeout: {timeout_seconds}s)")

        while time.time() - start_time < timeout_seconds:
            time.sleep(10)  # Check every 10 seconds

            # Get recent comments
            comments = linear.get_issue_comments(self.qa_task_id)

            # Look for a response after our question
            for comment in comments:
                comment_time = comment.get("createdAt", "")
                if comment_time <= last_check:
                    continue

                user = comment.get("user", {})
                user_name = user.get("name", "").lower()

                # Skip our own comments (from vineyard)
                if "vineyard" in user_name:
                    continue

                body = comment.get("body", "").strip().lower()

                # Check for option selection
                for i, opt in enumerate(options):
                    if (
                        body == str(i + 1) or
                        body == opt["key"].lower() or
                        opt["label"].lower() in body
                    ):
                        self.logger.info(f"Operator selected option: {opt['key']}")

                        # Acknowledge the decision
                        linear.add_comment(
                            self.qa_task_id,
                            f"✅ Decision received: **{opt['label']}**\n\nContinuing with selected option..."
                        )

                        return opt["key"]

        self.logger.warning(f"Timed out waiting for operator decision")
        return None

    def _check_design_docs_for_decision(
        self,
        state: FactoryState,
        question_type: str,
    ) -> Optional[str]:
        """
        Check design docs (PRD, spec) to find guidance for a decision.

        Args:
            state: Factory state with design/spec outputs
            question_type: Type of decision needed (e.g., "auth_system")

        Returns:
            Decision value if found in docs, None otherwise
        """
        design_output = self.get_previous_output(state, "design")
        spec_output = self.get_previous_output(state, "spec")
        prefs = state.handoff.build_preferences

        if question_type == "auth_system":
            # Check build preferences first
            auth_pref = prefs.auth_preference
            if auth_pref:
                self.logger.info(f"Found auth preference in build prefs: {auth_pref}")
                return auth_pref

            # Check PRD for auth mentions
            prd = design_output.get("prd", "") if design_output else ""
            if isinstance(prd, str):
                if "clerk" in prd.lower():
                    return "clerk"
                elif "jwt" in prd.lower() or "custom auth" in prd.lower():
                    return "custom"

        elif question_type == "database":
            db_pref = prefs.database_preference
            if db_pref:
                return db_pref

        return None

    # =========================================================================
    # Validation Methods
    # =========================================================================

    def _fix_missing_dependencies(
        self, files_dict: dict[str, GeneratedFile], state: FactoryState
    ) -> None:
        """Detect and fix missing dependencies in package.json."""
        pkg_file = files_dict.get("package.json")
        if not pkg_file:
            self._add_issue(
                IssueSeverity.CRITICAL,
                IssueType.MISSING_STRUCTURE,
                "No package.json found",
            )
            return

        try:
            pkg_data = json.loads(pkg_file.content)
        except json.JSONDecodeError as e:
            self._add_issue(
                IssueSeverity.CRITICAL,
                IssueType.BUILD_ERROR,
                f"Invalid package.json: {e}",
            )
            return

        declared_deps = set(pkg_data.get("dependencies", {}).keys())
        declared_deps.update(pkg_data.get("devDependencies", {}).keys())

        # Extract all imports from TS/JS files
        missing_deps: dict[str, list[str]] = {}

        for path, f in files_dict.items():
            if not path.endswith((".ts", ".tsx", ".js", ".jsx")):
                continue
            if "node_modules" in path:
                continue

            imports = self._extract_imports(f.content)
            for imp in imports:
                pkg_name = self._get_package_name(imp)
                if pkg_name and pkg_name not in declared_deps:
                    if not self._is_builtin_module(pkg_name):
                        if pkg_name not in missing_deps:
                            missing_deps[pkg_name] = []
                        missing_deps[pkg_name].append(path)

        if not missing_deps:
            self.logger.info("No missing dependencies found")
            return

        # Record and fix each missing dependency
        for pkg, used_in_files in missing_deps.items():
            issue = self._add_issue(
                IssueSeverity.CRITICAL,
                IssueType.MISSING_DEPENDENCY,
                f"Package '{pkg}' imported but not in package.json",
                details={"package": pkg, "used_in": used_in_files[:3]},
            )

            # Get appropriate version
            version = self.KNOWN_VERSIONS.get(pkg, "latest")

            # Add to dependencies
            if "dependencies" not in pkg_data:
                pkg_data["dependencies"] = {}
            pkg_data["dependencies"][pkg] = version

            self._mark_issue_fixed(issue, f"Added {pkg}@{version} to package.json")

        # Update the file
        new_content = json.dumps(pkg_data, indent=2) + "\n"
        files_dict["package.json"] = GeneratedFile(
            path="package.json",
            content=new_content,
            language="json",
        )

        if "package.json" not in self.files_modified:
            self.files_modified.append("package.json")

    def _fix_vulnerable_dependencies(
        self, files_dict: dict[str, GeneratedFile], state: FactoryState
    ) -> None:
        """Detect and fix vulnerable dependencies."""
        pkg_file = files_dict.get("package.json")
        if not pkg_file:
            return

        try:
            pkg_data = json.loads(pkg_file.content)
        except json.JSONDecodeError:
            return

        modified = False

        for dep_type in ["dependencies", "devDependencies"]:
            deps = pkg_data.get(dep_type, {})

            for pkg in list(deps.keys()):
                # Check for malicious packages
                if pkg in self.KNOWN_VULNERABLE:
                    issue = self._add_issue(
                        IssueSeverity.CRITICAL,
                        IssueType.MALICIOUS_PACKAGE,
                        f"Known malicious package: {pkg} - {self.KNOWN_VULNERABLE[pkg]}",
                        details={"package": pkg, "reason": self.KNOWN_VULNERABLE[pkg]},
                    )

                    del deps[pkg]
                    modified = True

                    self._mark_issue_fixed(issue, f"Removed malicious package {pkg}")

                # Check for vulnerable versions
                elif pkg in self.MIN_SECURE_VERSIONS:
                    current = deps[pkg]
                    secure = self.MIN_SECURE_VERSIONS[pkg]

                    if not self._version_satisfies(current, secure):
                        issue = self._add_issue(
                            IssueSeverity.HIGH,
                            IssueType.VULNERABLE_DEPENDENCY,
                            f"{pkg}@{current} has known vulnerabilities",
                            details={
                                "package": pkg,
                                "current": current,
                                "secure": secure,
                            },
                        )

                        deps[pkg] = secure
                        modified = True

                        self._mark_issue_fixed(
                            issue, f"Upgraded {pkg} from {current} to {secure}"
                        )

        if modified:
            new_content = json.dumps(pkg_data, indent=2) + "\n"
            files_dict["package.json"] = GeneratedFile(
                path="package.json",
                content=new_content,
                language="json",
            )

            if "package.json" not in self.files_modified:
                self.files_modified.append("package.json")

    def _fix_missing_structure(
        self, files_dict: dict[str, GeneratedFile], state: FactoryState
    ) -> None:
        """Detect and generate missing structural files."""
        prefs = state.handoff.build_preferences
        frontend = prefs.tech_stack.get("frontend", "nextjs")

        if frontend != "nextjs":
            return

        required_files = {
            "app/layout.tsx": {
                "severity": IssueSeverity.CRITICAL,
                "description": "Root layout required for Next.js App Router",
            },
        }

        recommended_files = {
            "app/error.tsx": {
                "severity": IssueSeverity.WARNING,
                "description": "Error boundary for better error handling",
            },
            "app/not-found.tsx": {
                "severity": IssueSeverity.WARNING,
                "description": "Custom 404 page",
            },
            "middleware.ts": {
                "severity": IssueSeverity.MEDIUM,
                "description": "Auth middleware for route protection",
            },
        }

        # Check required files
        for path, info in required_files.items():
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
                        language="typescript",
                    )
                    self.files_modified.append(path)
                    self._mark_issue_fixed(issue, f"Generated {path}")

        # Check recommended files
        for path, info in recommended_files.items():
            if path not in files_dict:
                issue = self._add_issue(
                    info["severity"],
                    IssueType.MISSING_STRUCTURE,
                    f"Missing recommended file: {path} - {info['description']}",
                    file=path,
                    create_linear_issue=False,  # Don't create bugs for warnings
                )

                content = self._generate_missing_file(path, state)
                if content:
                    files_dict[path] = GeneratedFile(
                        path=path,
                        content=content,
                        language="typescript",
                    )
                    self.files_modified.append(path)
                    self._mark_issue_fixed(issue, f"Generated {path}")

    def _generate_missing_file(
        self, path: str, state: FactoryState
    ) -> Optional[str]:
        """Generate content for a missing file."""
        opp = state.handoff.opportunity
        prefs = state.handoff.build_preferences

        templates = {
            "app/layout.tsx": f'''import type {{ Metadata }} from "next";
import {{ Inter }} from "next/font/google";
import "./globals.css";

const inter = Inter({{ subsets: ["latin"] }});

export const metadata: Metadata = {{
  title: "{opp.name}",
  description: "{opp.one_liner[:150] if opp.one_liner else opp.name}",
}};

export default function RootLayout({{
  children,
}}: {{
  children: React.ReactNode;
}}) {{
  return (
    <html lang="en">
      <body className={{inter.className}}>{{children}}</body>
    </html>
  );
}}
''',
            "app/error.tsx": '''\'use client\';

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center">
      <h2 className="text-2xl font-bold mb-4">Something went wrong!</h2>
      <button
        className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        onClick={() => reset()}
      >
        Try again
      </button>
    </div>
  );
}
''',
            "app/not-found.tsx": '''import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center">
      <h2 className="text-2xl font-bold mb-4">Page Not Found</h2>
      <p className="text-gray-600 mb-4">Could not find the requested resource</p>
      <Link
        href="/"
        className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
      >
        Return Home
      </Link>
    </div>
  );
}
''',
            "middleware.ts": self._generate_middleware(prefs),
        }

        return templates.get(path)

    def _generate_middleware(self, prefs) -> str:
        """Generate middleware based on auth preference."""
        if prefs.auth_preference == "clerk":
            return '''import { authMiddleware } from "@clerk/nextjs";

export default authMiddleware({
  publicRoutes: ["/", "/pricing", "/api/v1/health"],
});

export const config = {
  matcher: ["/((?!.+\\\\.[\\\\w]+$|_next).*)", "/", "/(api|trpc)(.*)"],
};
'''
        else:
            return '''import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  // Add your auth logic here
  // Example: Check for session token
  const token = request.cookies.get("session_token");

  // Protect dashboard routes
  if (request.nextUrl.pathname.startsWith("/dashboard")) {
    if (!token) {
      return NextResponse.redirect(new URL("/login", request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/api/v1/:path*"],
};
'''

    def _fix_import_mismatches(
        self, files_dict: dict[str, GeneratedFile], state: FactoryState
    ) -> None:
        """Detect and fix import/export mismatches."""
        # Build export map: file -> [exported symbols]
        export_map: dict[str, list[str]] = {}

        for path, f in files_dict.items():
            if path.endswith((".ts", ".tsx", ".js", ".jsx")):
                if "node_modules" not in path:
                    export_map[path] = self._extract_exports(f.content)

        # Check imports match exports
        for path, f in files_dict.items():
            if not path.endswith((".ts", ".tsx", ".js", ".jsx")):
                continue
            if "node_modules" in path:
                continue

            import_details = self._extract_import_details(f.content)

            for imp in import_details:
                if not imp["source"].startswith("."):
                    continue  # Skip node_modules imports

                # Resolve relative import to file path
                target_path = self._resolve_import_path(path, imp["source"], files_dict)
                if not target_path or target_path not in export_map:
                    continue

                available_exports = export_map[target_path]

                for symbol in imp["symbols"]:
                    if symbol == "default":
                        if "default" not in available_exports:
                            self._add_issue(
                                IssueSeverity.HIGH,
                                IssueType.IMPORT_MISMATCH,
                                f"No default export in {imp['source']}",
                                file=path,
                                details={"import": "default", "from": imp["source"]},
                            )
                    elif symbol not in available_exports:
                        self._add_issue(
                            IssueSeverity.HIGH,
                            IssueType.IMPORT_MISMATCH,
                            f"'{symbol}' not exported from {imp['source']}",
                            file=path,
                            details={
                                "import": symbol,
                                "from": imp["source"],
                                "available": available_exports[:5],
                            },
                        )

    def _fix_auth_consistency(
        self, files_dict: dict[str, GeneratedFile], state: FactoryState
    ) -> None:
        """Detect and fix auth system inconsistencies."""
        clerk_files: list[str] = []
        jwt_files: list[str] = []

        for path, f in files_dict.items():
            if "node_modules" in path:
                continue

            content = f.content
            if "@clerk" in content:
                clerk_files.append(path)
            if "jsonwebtoken" in content or re.search(r'\bjwt\b', content.lower()):
                jwt_files.append(path)

        # If using both, check if it's intentional
        if clerk_files and jwt_files:
            # First check design docs for guidance
            intended_auth = self._check_design_docs_for_decision(state, "auth_system")

            if intended_auth:
                self.logger.info(f"Design docs specify auth system: {intended_auth}")
                # Don't flag as issue if it matches the design
                if intended_auth == "clerk" and jwt_files:
                    self._add_issue(
                        IssueSeverity.MEDIUM,
                        IssueType.AUTH_INCONSISTENCY,
                        f"JWT used in {len(jwt_files)} files but design specifies Clerk",
                        details={"jwt_files": jwt_files[:3]},
                        create_linear_issue=False,
                    )
                elif intended_auth == "custom" and clerk_files:
                    self._add_issue(
                        IssueSeverity.MEDIUM,
                        IssueType.AUTH_INCONSISTENCY,
                        f"Clerk used in {len(clerk_files)} files but design specifies custom auth",
                        details={"clerk_files": clerk_files[:3]},
                        create_linear_issue=False,
                    )
            else:
                # No clear guidance - request operator decision
                self._add_issue(
                    IssueSeverity.MEDIUM,
                    IssueType.AUTH_INCONSISTENCY,
                    f"Mixed auth: Clerk in {len(clerk_files)} files, JWT in {len(jwt_files)} files",
                    details={
                        "clerk_files": clerk_files[:3],
                        "jwt_files": jwt_files[:3],
                    },
                )

                # Request decision from operator
                decision = self._request_operator_decision(
                    state,
                    question="Mixed authentication systems detected. Which should be the primary auth system?",
                    options=[
                        {
                            "key": "clerk",
                            "label": "Clerk (Recommended)",
                            "description": "Use Clerk for all auth. Simpler setup, managed service.",
                        },
                        {
                            "key": "jwt",
                            "label": "Custom JWT",
                            "description": "Use custom JWT auth. More control, self-managed.",
                        },
                        {
                            "key": "hybrid",
                            "label": "Keep Hybrid",
                            "description": "Keep both: Clerk for UI, JWT for API. More complex but flexible.",
                        },
                    ],
                    context=f"""The codebase currently uses:
- Clerk auth in: {', '.join(clerk_files[:3])}
- JWT auth in: {', '.join(jwt_files[:3])}

This might be intentional (Clerk for frontend, JWT for API) or accidental.""",
                    timeout_seconds=300,
                )

                if decision:
                    self.logger.info(f"Operator chose auth system: {decision}")
                    # TODO: Implement auth system normalization based on decision

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

            # Verify all files were pushed
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

    def _verify_build(
        self, repo_info: dict, state: FactoryState
    ) -> None:
        """Clone repo and verify it builds."""
        import subprocess
        import tempfile

        self.logger.info("Verifying build...")

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Clone
                clone_url = f"https://github.com/{repo_info['owner']}/{repo_info['name']}.git"
                clone_result = subprocess.run(
                    ["git", "clone", "--depth=1", clone_url, tmpdir],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if clone_result.returncode != 0:
                    self._add_issue(
                        IssueSeverity.CRITICAL,
                        IssueType.BUILD_ERROR,
                        f"Failed to clone repo: {clone_result.stderr[:200]}",
                    )
                    return

                # npm install
                self.logger.info("Running npm install...")
                install_result = subprocess.run(
                    ["npm", "install"],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )

                if install_result.returncode != 0:
                    self._add_issue(
                        IssueSeverity.CRITICAL,
                        IssueType.BUILD_ERROR,
                        "npm install failed",
                        details={"stderr": install_result.stderr[:500]},
                    )
                    return

                # npm run build
                self.logger.info("Running npm run build...")
                build_result = subprocess.run(
                    ["npm", "run", "build"],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

                if build_result.returncode != 0:
                    # Parse build errors
                    errors = self._parse_build_errors(build_result.stderr + build_result.stdout)

                    for error in errors:
                        self._add_issue(
                            IssueSeverity.CRITICAL,
                            IssueType.BUILD_ERROR,
                            error.get("message", "Build error"),
                            file=error.get("file"),
                            details=error,
                        )

                    if not errors:
                        self._add_issue(
                            IssueSeverity.CRITICAL,
                            IssueType.BUILD_ERROR,
                            "Build failed",
                            details={"output": build_result.stderr[:1000]},
                        )
                    return

                self.logger.info("Build verification passed!")

        except subprocess.TimeoutExpired:
            self._add_issue(
                IssueSeverity.WARNING,
                IssueType.BUILD_ERROR,
                "Build verification timed out",
            )
        except Exception as e:
            self._add_issue(
                IssueSeverity.WARNING,
                IssueType.BUILD_ERROR,
                f"Build verification error: {e}",
            )

    def _parse_build_errors(self, output: str) -> list[dict]:
        """Parse build output to extract error details."""
        errors = []

        # TypeScript errors: src/file.ts(10,5): error TS2304
        ts_pattern = r'([^\s]+\.tsx?)\((\d+),(\d+)\):\s*error\s+(TS\d+):\s*(.+)'
        for match in re.finditer(ts_pattern, output):
            errors.append({
                "file": match.group(1),
                "line": int(match.group(2)),
                "column": int(match.group(3)),
                "code": match.group(4),
                "message": match.group(5),
            })

        # Next.js errors: Error: ... at /path/to/file.tsx
        next_pattern = r'Error:\s*(.+?)(?:\n|$)'
        for match in re.finditer(next_pattern, output):
            if not any(e.get("message") == match.group(1) for e in errors):
                errors.append({"message": match.group(1)})

        return errors[:10]  # Limit to 10 errors

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _extract_imports(self, content: str) -> list[str]:
        """Extract import paths from TypeScript/JavaScript."""
        patterns = [
            r'import\s+.*?\s+from\s+["\']([^"\']+)["\']',
            r'import\s+["\']([^"\']+)["\']',
            r'require\s*\(\s*["\']([^"\']+)["\']\s*\)',
        ]
        imports = []
        for pattern in patterns:
            imports.extend(re.findall(pattern, content))
        return imports

    def _extract_exports(self, content: str) -> list[str]:
        """Extract exported symbols from TypeScript/JavaScript."""
        exports = []

        # export const/let/var/function/class name
        exports.extend(re.findall(
            r'export\s+(?:const|let|var|function|class|type|interface)\s+(\w+)',
            content
        ))

        # export { name, name2 }
        bracket_exports = re.findall(r'export\s*\{([^}]+)\}', content)
        for group in bracket_exports:
            for item in group.split(','):
                name = item.strip().split(' as ')[0].strip()
                if name:
                    exports.append(name)

        # export default
        if re.search(r'export\s+default', content):
            exports.append('default')

        return exports

    def _extract_import_details(self, content: str) -> list[dict]:
        """Extract detailed import information."""
        imports = []

        # import { a, b } from "module"
        named_pattern = r'import\s*\{([^}]+)\}\s*from\s*["\']([^"\']+)["\']'
        for match in re.finditer(named_pattern, content):
            symbols = [s.strip().split(' as ')[0].strip()
                      for s in match.group(1).split(',')]
            imports.append({
                "symbols": [s for s in symbols if s],
                "source": match.group(2),
            })

        # import Default from "module"
        default_pattern = r'import\s+(\w+)\s+from\s*["\']([^"\']+)["\']'
        for match in re.finditer(default_pattern, content):
            if match.group(1) not in ['type', 'typeof']:
                imports.append({
                    "symbols": ["default"],
                    "source": match.group(2),
                })

        return imports

    def _get_package_name(self, import_path: str) -> Optional[str]:
        """Extract package name from import path."""
        if import_path.startswith(".") or import_path.startswith("/"):
            return None

        # Handle scoped packages (@org/pkg)
        if import_path.startswith("@"):
            parts = import_path.split("/")
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1]}"

        # Regular package
        return import_path.split("/")[0]

    def _is_builtin_module(self, name: str) -> bool:
        """Check if a module is a Node.js builtin."""
        builtins = {
            'assert', 'buffer', 'child_process', 'cluster', 'console',
            'constants', 'crypto', 'dgram', 'dns', 'domain', 'events',
            'fs', 'http', 'https', 'module', 'net', 'os', 'path',
            'process', 'punycode', 'querystring', 'readline', 'repl',
            'stream', 'string_decoder', 'timers', 'tls', 'tty', 'url',
            'util', 'v8', 'vm', 'zlib', 'react', 'react-dom', 'next',
        }
        return name in builtins or name.startswith('node:')

    def _resolve_import_path(
        self,
        from_file: str,
        import_source: str,
        files_dict: dict[str, GeneratedFile],
    ) -> Optional[str]:
        """Resolve a relative import to an absolute file path."""
        import os

        if not import_source.startswith("."):
            return None

        # Get directory of importing file
        from_dir = os.path.dirname(from_file)

        # Resolve relative path
        resolved = os.path.normpath(os.path.join(from_dir, import_source))

        # Try common extensions
        for ext in ["", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx"]:
            candidate = resolved + ext
            if candidate in files_dict:
                return candidate

        return None

    def _version_satisfies(self, current: str, required: str) -> bool:
        """Check if current version satisfies required minimum."""
        current_clean = current.lstrip("^~>=<")
        required_clean = required.lstrip("^~>=<")

        try:
            current_parts = [int(x) for x in current_clean.split(".")[:3]]
            required_parts = [int(x) for x in required_clean.split(".")[:3]]

            while len(current_parts) < 3:
                current_parts.append(0)
            while len(required_parts) < 3:
                required_parts.append(0)

            return current_parts >= required_parts
        except (ValueError, IndexError):
            return False

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
