"""Custom MCP tools for Agent SDK-powered factory agents.

These tools are exposed to Claude via the Agent SDK, allowing it to
iteratively generate code, read specs, and manage files.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Module-level state that tools operate on
_generation_state: dict[str, Any] = {}


def reset_state():
    """Reset tool state for a new generation session."""
    global _generation_state
    _generation_state = {
        "files": {},  # path -> {content, language, category}
        "spec": None,
        "design": None,
        "prd_input": None,
        "build_prefs": None,
    }


def set_context(
    spec: Any = None,
    design: Any = None,
    prd_input: Any = None,
    build_prefs: Any = None,
):
    """Set the context data that tools will operate on."""
    if spec is not None:
        _generation_state["spec"] = spec
    if design is not None:
        _generation_state["design"] = design
    if prd_input is not None:
        _generation_state["prd_input"] = prd_input
    if build_prefs is not None:
        _generation_state["build_prefs"] = build_prefs


def get_generated_files() -> dict[str, dict]:
    """Get all generated files."""
    return _generation_state.get("files", {})


def _build_code_gen_tools() -> list:
    """Build MCP tools for code generation agents."""
    from claude_agent_sdk import tool

    @tool(
        name="write_file",
        description="Write a file to the generated project. Use this for every file you generate.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to project root (e.g. 'app/models/user.rb')",
                },
                "content": {
                    "type": "string",
                    "description": "Full file content",
                },
                "language": {
                    "type": "string",
                    "description": "Programming language (ruby, erb, yaml, javascript, etc.)",
                },
                "category": {
                    "type": "string",
                    "description": "File category: project, model, migration, controller, api, service, component, view, layout, stimulus, job, mailer, test, config",
                },
            },
            "required": ["path", "content", "language", "category"],
        },
    )
    async def write_file(input: dict) -> dict[str, Any]:
        path = input["path"].lstrip("./")
        _generation_state.setdefault("files", {})[path] = {
            "content": input["content"],
            "language": input["language"],
            "category": input["category"],
        }
        file_count = len(_generation_state["files"])
        return {"success": True, "path": path, "total_files": file_count}

    @tool(
        name="read_generated_file",
        description="Read a file that was previously generated in this session. Use this to review your own output for consistency.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to read",
                },
            },
            "required": ["path"],
        },
    )
    async def read_generated_file(input: dict) -> dict[str, Any]:
        path = input["path"].lstrip("./")
        files = _generation_state.get("files", {})
        if path in files:
            return {"found": True, "content": files[path]["content"], "language": files[path]["language"]}
        return {"found": False, "available_files": list(files.keys())[:20]}

    @tool(
        name="list_generated_files",
        description="List all files generated so far, organized by category.",
        input_schema={
            "type": "object",
            "properties": {},
        },
    )
    async def list_generated_files(input: dict) -> dict[str, Any]:
        files = _generation_state.get("files", {})
        by_category: dict[str, list[str]] = {}
        for path, info in files.items():
            cat = info.get("category", "unknown")
            by_category.setdefault(cat, []).append(path)
        return {
            "total_files": len(files),
            "by_category": by_category,
        }

    @tool(
        name="get_spec",
        description="Get the technical specification for the project being built. Includes API endpoints, database schema, and task breakdown.",
        input_schema={
            "type": "object",
            "properties": {},
        },
    )
    async def get_spec(input: dict) -> dict[str, Any]:
        from dataclasses import asdict, is_dataclass
        spec = _generation_state.get("spec")
        if spec is None:
            return {"available": False}

        if is_dataclass(spec) and not isinstance(spec, type):
            return {"available": True, "spec": asdict(spec)}
        elif isinstance(spec, dict):
            return {"available": True, "spec": spec}
        return {"available": False}

    @tool(
        name="get_design",
        description="Get the design output including features, user flows, and UI copy.",
        input_schema={
            "type": "object",
            "properties": {},
        },
    )
    async def get_design(input: dict) -> dict[str, Any]:
        from dataclasses import asdict, is_dataclass
        design = _generation_state.get("design")
        if design is None:
            return {"available": False}

        if is_dataclass(design) and not isinstance(design, type):
            return {"available": True, "design": asdict(design)}
        elif isinstance(design, dict):
            return {"available": True, "design": design}
        return {"available": False}

    @tool(
        name="get_project_info",
        description="Get project info: product name, PRD text, build preferences (auth, payments, hosting, database).",
        input_schema={
            "type": "object",
            "properties": {},
        },
    )
    async def get_project_info(input: dict) -> dict[str, Any]:
        from dataclasses import asdict, is_dataclass

        result = {}
        prd = _generation_state.get("prd_input")
        if prd:
            if is_dataclass(prd) and not isinstance(prd, type):
                result["prd_input"] = asdict(prd)
            else:
                result["prd_input"] = prd

        prefs = _generation_state.get("build_prefs")
        if prefs:
            if is_dataclass(prefs) and not isinstance(prefs, type):
                result["build_preferences"] = asdict(prefs)
            else:
                result["build_preferences"] = prefs

        return result if result else {"available": False}

    return [write_file, read_generated_file, list_generated_files, get_spec, get_design, get_project_info]


def _build_qa_tools() -> list:
    """Build MCP tools for QA validation agents."""
    from claude_agent_sdk import tool

    @tool(
        name="run_shell_command",
        description="Run a shell command in the cloned project directory. Use for: bundle install, rubocop, rspec, brakeman, etc.",
        input_schema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to run",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 120)",
                    "default": 120,
                },
            },
            "required": ["command"],
        },
    )
    async def run_shell_command(input: dict) -> dict[str, Any]:
        import subprocess
        cwd = _generation_state.get("project_dir")
        if not cwd:
            return {"error": "No project directory set. Clone the repo first."}

        timeout = input.get("timeout_seconds", 120)
        try:
            result = subprocess.run(
                input["command"],
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout[:5000],
                "stderr": result.stderr[:2000],
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"error": str(e)}

    @tool(
        name="read_project_file",
        description="Read a file from the cloned project directory.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to project root",
                },
            },
            "required": ["path"],
        },
    )
    async def read_project_file(input: dict) -> dict[str, Any]:
        import os
        cwd = _generation_state.get("project_dir")
        if not cwd:
            return {"error": "No project directory set"}

        filepath = os.path.join(cwd, input["path"])
        # Prevent path traversal
        if not os.path.abspath(filepath).startswith(os.path.abspath(cwd)):
            return {"error": "Path traversal not allowed"}

        try:
            with open(filepath, "r") as f:
                content = f.read()
            return {"content": content[:10000], "truncated": len(content) > 10000}
        except FileNotFoundError:
            return {"error": f"File not found: {input['path']}"}
        except Exception as e:
            return {"error": str(e)}

    @tool(
        name="write_project_file",
        description="Write or modify a file in the cloned project directory. Use for fixing issues.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to project root",
                },
                "content": {
                    "type": "string",
                    "description": "Full file content",
                },
            },
            "required": ["path", "content"],
        },
    )
    async def write_project_file(input: dict) -> dict[str, Any]:
        import os
        cwd = _generation_state.get("project_dir")
        if not cwd:
            return {"error": "No project directory set"}

        filepath = os.path.join(cwd, input["path"])
        if not os.path.abspath(filepath).startswith(os.path.abspath(cwd)):
            return {"error": "Path traversal not allowed"}

        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w") as f:
                f.write(input["content"])

            _generation_state.setdefault("files_modified", [])
            if input["path"] not in _generation_state["files_modified"]:
                _generation_state["files_modified"].append(input["path"])

            return {"success": True, "path": input["path"]}
        except Exception as e:
            return {"error": str(e)}

    @tool(
        name="list_project_files",
        description="List files in the project directory. Optionally filter by directory.",
        input_schema={
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Subdirectory to list (default: project root)",
                    "default": ".",
                },
            },
        },
    )
    async def list_project_files(input: dict) -> dict[str, Any]:
        import os
        cwd = _generation_state.get("project_dir")
        if not cwd:
            return {"error": "No project directory set"}

        directory = os.path.join(cwd, input.get("directory", "."))
        if not os.path.abspath(directory).startswith(os.path.abspath(cwd)):
            return {"error": "Path traversal not allowed"}

        try:
            files = []
            for root, dirs, filenames in os.walk(directory):
                # Skip hidden dirs and vendor
                dirs[:] = [d for d in dirs if not d.startswith(".") and d != "vendor" and d != "node_modules"]
                for f in filenames:
                    rel = os.path.relpath(os.path.join(root, f), cwd)
                    files.append(rel)
                if len(files) > 200:
                    break
            return {"files": sorted(files)[:200], "truncated": len(files) > 200}
        except Exception as e:
            return {"error": str(e)}

    @tool(
        name="report_issue",
        description="Report a QA issue found during validation.",
        input_schema={
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low"],
                    "description": "Issue severity",
                },
                "issue_type": {
                    "type": "string",
                    "description": "Type: missing_dependency, build_error, lint_error, test_failure, security_issue, etc.",
                },
                "message": {
                    "type": "string",
                    "description": "Description of the issue",
                },
                "file": {
                    "type": "string",
                    "description": "Affected file path (optional)",
                },
                "fixed": {
                    "type": "boolean",
                    "description": "Whether this issue was auto-fixed",
                    "default": False,
                },
                "fix_action": {
                    "type": "string",
                    "description": "Description of the fix applied (if fixed)",
                },
            },
            "required": ["severity", "message"],
        },
    )
    async def report_issue(input: dict) -> dict[str, Any]:
        issues = _generation_state.setdefault("qa_issues", [])
        issue = {
            "severity": input["severity"],
            "issue_type": input.get("issue_type", "unknown"),
            "message": input["message"],
            "file": input.get("file"),
            "fixed": input.get("fixed", False),
            "fix_action": input.get("fix_action"),
        }
        issues.append(issue)
        return {"recorded": True, "total_issues": len(issues)}

    return [run_shell_command, read_project_file, write_project_file, list_project_files, report_issue]


def get_code_gen_tools() -> list:
    """Get the MCP tools for code generation. Returns empty list if SDK unavailable."""
    try:
        return _build_code_gen_tools()
    except ImportError:
        logger.warning("Agent SDK not available, code gen tools not loaded")
        return []


def get_qa_tools() -> list:
    """Get the MCP tools for QA validation. Returns empty list if SDK unavailable."""
    try:
        return _build_qa_tools()
    except ImportError:
        logger.warning("Agent SDK not available, QA tools not loaded")
        return []
