"""Security Agent - Security scanning and recommendations."""

import re
from typing import Any, Optional

from src.agents.base import BaseAgent
from src.config.prompts import SECURITY_AGENT_PROMPT
from src.models import FactoryState, GeneratedFile
from src.tools import github, llm


class SecurityAgent(BaseAgent):
    """
    Agent for comprehensive security analysis and recommendations.

    Performs:
    - Pattern-based secret detection
    - OWASP vulnerability scanning
    - Dependency security analysis
    - Authentication/authorization review
    - API security assessment
    """

    name = "SecurityAgent"
    domain = "engineering"

    # Secret patterns to detect (regex -> description)
    SECRET_PATTERNS = {
        r'(?:api[_-]?key|apikey)\s*[=:]\s*["\']?[a-zA-Z0-9_-]{16,}["\']?': "API Key",
        r'(?:secret|password|passwd|pwd)\s*[=:]\s*["\'][^"\']+["\']': "Hardcoded Secret/Password",
        r'(?:aws_access_key_id|aws_secret_access_key)\s*[=:]\s*["\']?[A-Z0-9]{16,}["\']?': "AWS Credentials",
        r'(?:AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}': "AWS Access Key ID",
        r'sk-[a-zA-Z0-9]{24,}': "OpenAI/Stripe Secret Key",
        r'ghp_[a-zA-Z0-9]{36}': "GitHub Personal Access Token",
        r'gho_[a-zA-Z0-9]{36}': "GitHub OAuth Token",
        r'glpat-[a-zA-Z0-9\-_]{20,}': "GitLab Personal Access Token",
        r'(?:private[_-]?key|privatekey)\s*[=:]\s*["\']-----BEGIN': "Private Key",
        r'mongodb(?:\+srv)?://[^"\'\s]+': "MongoDB Connection String",
        r'postgres(?:ql)?://[^"\'\s]+': "PostgreSQL Connection String",
        r'mysql://[^"\'\s]+': "MySQL Connection String",
        r'redis://[^"\'\s]+': "Redis Connection String",
        r'(?:bearer|token)\s+[a-zA-Z0-9._-]{20,}': "Bearer Token",
    }

    # SQL injection patterns
    SQL_INJECTION_PATTERNS = {
        r'\$\{[^}]+\}\s*(?:SELECT|INSERT|UPDATE|DELETE|DROP|CREATE)': "Template literal in SQL",
        r'`\s*(?:SELECT|INSERT|UPDATE|DELETE).*\$\{': "Template literal SQL injection risk",
        r'(?:query|execute)\s*\(\s*["\'].*\+\s*(?:req\.|params\.|body\.)': "String concatenation in SQL",
        r'(?:query|execute)\s*\(\s*`[^`]*\$\{(?:req|params|body)': "Unsafe interpolation in SQL",
    }

    # XSS patterns
    XSS_PATTERNS = {
        r'dangerouslySetInnerHTML\s*=\s*\{\s*\{\s*__html:\s*(?!sanitize)': "Unsafe dangerouslySetInnerHTML",
        r'innerHTML\s*=\s*(?!sanitize)': "Direct innerHTML assignment",
        r'document\.write\s*\(': "document.write usage",
        r'eval\s*\(': "eval() usage",
        r'new\s+Function\s*\(': "new Function() usage",
    }

    # Command injection patterns
    COMMAND_INJECTION_PATTERNS = {
        r'(?:exec|spawn|execSync)\s*\([^)]*(?:req\.|params\.|body\.|query\.)': "Unsanitized command execution",
        r'child_process.*(?:req\.|params\.|body\.)': "User input in child_process",
    }

    # Auth vulnerability patterns
    AUTH_PATTERNS = {
        r'jwt\.(?:sign|verify)\s*\([^)]*algorithm\s*:\s*["\']none["\']': "JWT algorithm 'none' vulnerability",
        r'(?:bcrypt|argon2|scrypt)\.compare[^)]*\btrue\b': "Always-true password comparison",
        r'session\s*=\s*\{\s*secret\s*:\s*["\'][^"\']{0,16}["\']': "Weak session secret",
    }

    def run(self, state: FactoryState) -> dict[str, Any]:
        """
        Perform comprehensive security analysis and generate recommendations.
        """
        self.log_start()

        opp = state.handoff.opportunity
        prefs = state.handoff.build_preferences
        build = self.get_previous_output(state, "build")

        # BUILD phase stores composite output: {"code": {...}, "test": {...}, ...}
        code_output = build.get("code", {}) if isinstance(build, dict) else {}
        files = code_output.get("files", []) if code_output else []

        # Convert to dict for easier lookup
        files_dict = {f.path: f for f in files}

        # Run pattern-based security scans (fast, deterministic)
        self.logger.info(f"Scanning {len(files)} files for security issues...")
        secret_issues = self._scan_for_secrets(files_dict)
        injection_issues = self._scan_for_injection(files_dict)
        auth_issues = self._scan_for_auth_vulnerabilities(files_dict)

        # Perform AI-powered code security analysis (deeper analysis)
        code_issues = self._analyze_code_security(files)

        # Check for common vulnerabilities based on stack
        vuln_check = self._check_vulnerabilities(prefs)

        # Check dependencies (now also covered by QAAgent's npm audit)
        dep_issues = self._check_dependencies(files_dict, prefs)

        # Combine all issues
        all_code_issues = secret_issues + injection_issues + auth_issues + code_issues

        # Generate security recommendations
        recommendations = self._generate_recommendations(all_code_issues, vuln_check, dep_issues)

        # Generate security documentation
        security_doc = self._generate_security_doc(opp, recommendations)

        # Push security findings to GitHub if there are critical issues
        if state.github_repo and any(i.get("severity") == "critical" for i in all_code_issues):
            self._push_security_report(state, all_code_issues)

        output = {
            "secret_issues": secret_issues,
            "injection_issues": injection_issues,
            "auth_issues": auth_issues,
            "code_issues": code_issues,
            "vulnerability_check": vuln_check,
            "dependency_issues": dep_issues,
            "recommendations": recommendations,
            "security_documentation": security_doc,
            "total_issues": len(all_code_issues),
            "critical_issues": len([i for i in all_code_issues if i.get("severity") == "critical"]),
            "high_issues": len([i for i in all_code_issues if i.get("severity") == "high"]),
        }

        self.log_complete()
        return output

    def _scan_for_secrets(self, files_dict: dict[str, GeneratedFile]) -> list[dict]:
        """Scan all files for hardcoded secrets using pattern matching."""
        issues = []

        for path, f in files_dict.items():
            # Skip non-code files and test fixtures
            if not path.endswith((".ts", ".tsx", ".js", ".jsx", ".py", ".env")):
                continue
            if "__tests__" in path or "fixtures" in path:
                continue
            # Skip .env.example files (they're meant to have placeholder values)
            if path.endswith(".env.example") or path.endswith(".env.local.example"):
                continue

            content = f.content
            lines = content.split("\n")

            for pattern, description in self.SECRET_PATTERNS.items():
                for i, line in enumerate(lines, 1):
                    # Skip comments
                    stripped = line.strip()
                    if stripped.startswith("//") or stripped.startswith("#"):
                        continue
                    # Skip env references (process.env.XXX)
                    if "process.env" in line or "os.environ" in line:
                        continue

                    if re.search(pattern, line, re.IGNORECASE):
                        # Redact the actual secret value
                        redacted_line = re.sub(
                            r'["\'][a-zA-Z0-9._\-/+]+["\']',
                            '"[REDACTED]"',
                            line
                        )
                        issues.append({
                            "severity": "critical",
                            "category": "A02:2021-Cryptographic Failures",
                            "type": "secret",
                            "file": path,
                            "line": i,
                            "description": f"Potential {description} detected",
                            "context": redacted_line.strip()[:100],
                            "remediation": "Move secret to environment variable",
                        })

        self.logger.info(f"Found {len(issues)} potential secret issues")
        return issues

    def _scan_for_injection(self, files_dict: dict[str, GeneratedFile]) -> list[dict]:
        """Scan for SQL injection, XSS, and command injection vulnerabilities."""
        issues = []

        for path, f in files_dict.items():
            if not path.endswith((".ts", ".tsx", ".js", ".jsx")):
                continue

            content = f.content
            lines = content.split("\n")

            # Check SQL injection patterns
            for pattern, description in self.SQL_INJECTION_PATTERNS.items():
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line, re.IGNORECASE):
                        issues.append({
                            "severity": "critical",
                            "category": "A03:2021-Injection",
                            "type": "sql_injection",
                            "file": path,
                            "line": i,
                            "description": f"SQL Injection risk: {description}",
                            "context": line.strip()[:100],
                            "remediation": "Use parameterized queries or an ORM",
                        })

            # Check XSS patterns
            for pattern, description in self.XSS_PATTERNS.items():
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line):
                        issues.append({
                            "severity": "high",
                            "category": "A03:2021-Injection",
                            "type": "xss",
                            "file": path,
                            "line": i,
                            "description": f"XSS risk: {description}",
                            "context": line.strip()[:100],
                            "remediation": "Sanitize user input before rendering",
                        })

            # Check command injection patterns
            for pattern, description in self.COMMAND_INJECTION_PATTERNS.items():
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line):
                        issues.append({
                            "severity": "critical",
                            "category": "A03:2021-Injection",
                            "type": "command_injection",
                            "file": path,
                            "line": i,
                            "description": f"Command Injection risk: {description}",
                            "context": line.strip()[:100],
                            "remediation": "Avoid executing user input; use allowlists",
                        })

        self.logger.info(f"Found {len(issues)} injection vulnerability issues")
        return issues

    def _scan_for_auth_vulnerabilities(self, files_dict: dict[str, GeneratedFile]) -> list[dict]:
        """Scan for authentication and authorization vulnerabilities."""
        issues = []

        for path, f in files_dict.items():
            if not path.endswith((".ts", ".tsx", ".js", ".jsx")):
                continue

            content = f.content
            lines = content.split("\n")

            # Check auth vulnerability patterns
            for pattern, description in self.AUTH_PATTERNS.items():
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line, re.IGNORECASE):
                        issues.append({
                            "severity": "critical",
                            "category": "A07:2021-Identification and Auth Failures",
                            "type": "auth_vulnerability",
                            "file": path,
                            "line": i,
                            "description": f"Auth vulnerability: {description}",
                            "context": line.strip()[:100],
                            "remediation": "Review authentication implementation",
                        })

            # Check for missing auth on API routes
            if "/api/" in path and "route.ts" in path:
                # Check if any auth check is present
                has_auth_check = any([
                    "getServerSession" in content,
                    "currentUser" in content,
                    "auth()" in content,
                    "requireAuth" in content,
                    "withAuth" in content,
                    "authMiddleware" in content,
                    "verifyToken" in content,
                    "@clerk" in content,
                ])

                if not has_auth_check:
                    # Check if it's a public endpoint
                    is_public = any([
                        "health" in path.lower(),
                        "webhook" in path.lower(),
                        "public" in path.lower(),
                        "/auth/" in path,
                    ])

                    if not is_public:
                        issues.append({
                            "severity": "high",
                            "category": "A01:2021-Broken Access Control",
                            "type": "missing_auth",
                            "file": path,
                            "line": 1,
                            "description": "API route may be missing authentication",
                            "context": f"No auth check found in {path}",
                            "remediation": "Add authentication check or mark as intentionally public",
                        })

        self.logger.info(f"Found {len(issues)} auth vulnerability issues")
        return issues

    def _analyze_code_security(self, files) -> list[dict]:
        """AI-powered deeper analysis for complex security issues."""
        if not files:
            return []

        # Categorize files for more targeted analysis
        api_files = [f for f in files if "/api/" in f.path and f.language == "typescript"]
        auth_files = [f for f in files if "auth" in f.path.lower()]
        db_files = [f for f in files if any(x in f.path.lower() for x in ["db", "database", "prisma", "drizzle"])]

        all_issues = []

        # Analyze API security (full content, not truncated)
        if api_files:
            api_issues = self._analyze_api_security(api_files[:10])
            all_issues.extend(api_issues)

        # Analyze auth implementation
        if auth_files:
            auth_analysis_issues = self._analyze_auth_implementation(auth_files[:5])
            all_issues.extend(auth_analysis_issues)

        # Analyze database operations
        if db_files:
            db_issues = self._analyze_db_security(db_files[:5])
            all_issues.extend(db_issues)

        return all_issues

    def _analyze_api_security(self, api_files) -> list[dict]:
        """Analyze API routes for security issues."""
        # Prepare full content for analysis (not truncated)
        files_content = "\n\n".join([
            f"### {f.path}\n```typescript\n{f.content}\n```"
            for f in api_files
        ])

        user_prompt = f"""Analyze these API routes for security issues:

{files_content}

Generate JSON with security findings:
{{
    "issues": [
        {{
            "severity": "critical" | "high" | "medium" | "low",
            "category": "OWASP category",
            "file": "path/to/file",
            "line": 42,
            "description": "Description of the issue",
            "remediation": "How to fix"
        }}
    ]
}}

Check for:
- Missing input validation (especially request body/params)
- Missing rate limiting
- Overly permissive CORS
- Information disclosure in error messages
- Missing authorization checks
- Insecure direct object references (IDOR)
- Mass assignment vulnerabilities
"""

        try:
            result = llm.generate_json(SECURITY_AGENT_PROMPT, user_prompt)
            return result.get("issues", [])
        except Exception as e:
            self.logger.error(f"Failed to analyze API security: {e}")
            return []

    def _analyze_auth_implementation(self, auth_files) -> list[dict]:
        """Analyze authentication implementation."""
        files_content = "\n\n".join([
            f"### {f.path}\n```typescript\n{f.content}\n```"
            for f in auth_files
        ])

        user_prompt = f"""Analyze this authentication implementation for security issues:

{files_content}

Generate JSON with security findings:
{{
    "issues": [
        {{
            "severity": "critical" | "high" | "medium" | "low",
            "category": "OWASP category",
            "file": "path/to/file",
            "line": 42,
            "description": "Description of the issue",
            "remediation": "How to fix"
        }}
    ]
}}

Check for:
- Weak password policies
- Missing brute force protection
- Session fixation
- Insecure session handling
- Missing CSRF protection
- JWT vulnerabilities (weak signing, missing expiration)
- OAuth/OIDC misconfigurations
"""

        try:
            result = llm.generate_json(SECURITY_AGENT_PROMPT, user_prompt)
            return result.get("issues", [])
        except Exception as e:
            self.logger.error(f"Failed to analyze auth implementation: {e}")
            return []

    def _analyze_db_security(self, db_files) -> list[dict]:
        """Analyze database operations for security issues."""
        files_content = "\n\n".join([
            f"### {f.path}\n```typescript\n{f.content}\n```"
            for f in db_files
        ])

        user_prompt = f"""Analyze this database code for security issues:

{files_content}

Generate JSON with security findings:
{{
    "issues": [
        {{
            "severity": "critical" | "high" | "medium" | "low",
            "category": "OWASP category",
            "file": "path/to/file",
            "line": 42,
            "description": "Description of the issue",
            "remediation": "How to fix"
        }}
    ]
}}

Check for:
- SQL injection vulnerabilities
- Missing parameterized queries
- Excessive data exposure (selecting more than needed)
- Missing row-level security
- Unsafe deserialization
- Connection string exposure
"""

        try:
            result = llm.generate_json(SECURITY_AGENT_PROMPT, user_prompt)
            return result.get("issues", [])
        except Exception as e:
            self.logger.error(f"Failed to analyze database security: {e}")
            return []

    def _check_vulnerabilities(self, prefs) -> dict:
        """Check for common vulnerability patterns."""
        user_prompt = f"""Check for common vulnerabilities in this stack:

FRONTEND: {prefs.tech_stack.get('frontend')}
BACKEND: {prefs.tech_stack.get('backend')}
DATABASE: {prefs.tech_stack.get('database')}
AUTH: {prefs.auth_preference}
PAYMENTS: {prefs.payments_preference}

Generate JSON with vulnerability assessment:
{{
    "owasp_top_10_coverage": {{
        "A01:2021-Broken Access Control": {{"status": "covered" | "at_risk", "notes": "..."}},
        "A02:2021-Cryptographic Failures": {{"status": "...", "notes": "..."}}
    }},
    "stack_specific_risks": [
        {{"risk": "...", "mitigation": "..."}}
    ],
    "overall_risk_level": "low" | "medium" | "high"
}}
"""

        try:
            return llm.generate_json(SECURITY_AGENT_PROMPT, user_prompt)
        except Exception as e:
            self.logger.error(f"Failed to check vulnerabilities: {e}")
            return {"overall_risk_level": "unknown"}

    def _check_dependencies(
        self, files_dict: dict[str, GeneratedFile], prefs
    ) -> list[dict]:
        """Check for dependency security issues by analyzing actual package.json."""
        import json

        issues = []

        # Known risky or deprecated packages
        RISKY_PACKAGES = {
            "request": ("deprecated", "Use 'node-fetch' or 'axios'"),
            "moment": ("deprecated", "Use 'date-fns' or 'dayjs'"),
            "lodash": ("bloated", "Import individual functions like 'lodash/get'"),
            "colors": ("compromised", "Remove or use 'chalk' at ^4.1.2"),
            "faker": ("compromised", "Use '@faker-js/faker'"),
            "event-stream": ("compromised", "Remove immediately"),
            "flatmap-stream": ("malicious", "Remove immediately"),
            "node-ipc": ("compromised", "Remove or pin to safe version"),
            "ua-parser-js": ("compromised", "Update to ^1.0.33"),
        }

        # Check actual package.json
        pkg_file = files_dict.get("package.json")
        if pkg_file:
            try:
                pkg_data = json.loads(pkg_file.content)
                all_deps = {
                    **pkg_data.get("dependencies", {}),
                    **pkg_data.get("devDependencies", {})
                }

                for pkg, version in all_deps.items():
                    if pkg in RISKY_PACKAGES:
                        reason, alternative = RISKY_PACKAGES[pkg]
                        issues.append({
                            "package": pkg,
                            "version": version,
                            "reason": reason,
                            "alternative": alternative,
                            "severity": "critical" if reason in ["compromised", "malicious"] else "medium",
                        })

            except json.JSONDecodeError:
                self.logger.warning("Failed to parse package.json for security check")

        # Also get AI recommendations for the stack
        user_prompt = f"""Analyze dependency security for this stack:

FRONTEND: {prefs.tech_stack.get('frontend')}
BACKEND: {prefs.tech_stack.get('backend')}
AUTH: {prefs.auth_preference}
PAYMENTS: {prefs.payments_preference}

Generate JSON with security package recommendations:
{{
    "recommended_security_packages": [
        {{"package": "helmet", "purpose": "HTTP security headers", "priority": "high"}}
    ],
    "version_recommendations": [
        {{"package": "...", "min_version": "...", "reason": "..."}}
    ]
}}

Recommend packages for:
- Rate limiting
- Input validation
- CORS configuration
- HTTP security headers
- CSRF protection
"""

        try:
            result = llm.generate_json(SECURITY_AGENT_PROMPT, user_prompt)
            # Store recommendations for later
            self._security_packages = result.get("recommended_security_packages", [])
        except Exception as e:
            self.logger.error(f"Failed to check dependencies: {e}")
            self._security_packages = []

        return issues

    def _generate_recommendations(
        self, code_issues: list, vuln_check: dict, dep_issues: list
    ) -> list[dict]:
        """Generate prioritized security recommendations."""
        recommendations = []

        # Add recommendations from code issues
        for issue in code_issues:
            if issue.get("severity") in ["high", "critical"]:
                recommendations.append({
                    "priority": "P0",
                    "title": f"Fix {issue.get('category', 'security issue')}",
                    "description": issue.get("description", ""),
                    "remediation": issue.get("remediation", ""),
                })

        # Add recommendations from vulnerability check
        if vuln_check.get("overall_risk_level") == "high":
            for risk in vuln_check.get("stack_specific_risks", []):
                recommendations.append({
                    "priority": "P1",
                    "title": risk.get("risk", "Address stack vulnerability"),
                    "description": risk.get("mitigation", ""),
                    "remediation": "",
                })

        # Add dependency recommendations
        for dep in dep_issues:
            recommendations.append({
                "priority": "P1",
                "title": f"Replace {dep.get('package', 'dependency')}",
                "description": dep.get("reason", ""),
                "remediation": f"Use {dep.get('alternative', 'alternative')} instead",
            })

        return recommendations

    def _generate_security_doc(self, opp, recommendations: list) -> str:
        """Generate security documentation."""
        user_prompt = f"""Generate security documentation for this product:

PRODUCT: {opp.name}
RECOMMENDATIONS: {len(recommendations)} items

Generate a markdown security document with:
1. Security Overview
2. Authentication Model
3. Authorization Model
4. Data Protection
5. API Security
6. Infrastructure Security
7. Monitoring & Incident Response
8. Compliance Considerations

Keep it concise but comprehensive.
"""

        try:
            return llm.generate(SECURITY_AGENT_PROMPT, user_prompt)
        except Exception as e:
            self.logger.error(f"Failed to generate security doc: {e}")
            return f"# {opp.name} Security Documentation\n\n[Generation pending]"

    def _push_security_report(self, state: FactoryState, issues: list[dict]) -> None:
        """Push a security report to GitHub when critical issues are found."""
        repo_info = state.github_repo
        if not repo_info or not repo_info.get("owner"):
            return

        # Group issues by severity
        critical = [i for i in issues if i.get("severity") == "critical"]
        high = [i for i in issues if i.get("severity") == "high"]
        medium = [i for i in issues if i.get("severity") == "medium"]

        report = f"""# Security Scan Report

**Generated:** {__import__('datetime').datetime.utcnow().isoformat()}
**Repository:** {repo_info.get('owner')}/{repo_info.get('name')}

## Summary

- **Critical Issues:** {len(critical)}
- **High Issues:** {len(high)}
- **Medium Issues:** {len(medium)}
- **Total Issues:** {len(issues)}

"""

        if critical:
            report += "## Critical Issues (Fix Immediately)\n\n"
            for i, issue in enumerate(critical, 1):
                report += f"""### {i}. {issue.get('description', 'Security Issue')}

- **File:** `{issue.get('file', 'N/A')}`
- **Line:** {issue.get('line', 'N/A')}
- **Category:** {issue.get('category', 'N/A')}
- **Remediation:** {issue.get('remediation', 'Review and fix')}

"""

        if high:
            report += "## High Priority Issues\n\n"
            for i, issue in enumerate(high, 1):
                report += f"- **{issue.get('file', 'N/A')}:{issue.get('line', '?')}** - {issue.get('description', 'Issue')}\n"
            report += "\n"

        if medium:
            report += "## Medium Priority Issues\n\n"
            for i, issue in enumerate(medium[:10], 1):
                report += f"- **{issue.get('file', 'N/A')}:{issue.get('line', '?')}** - {issue.get('description', 'Issue')}\n"
            if len(medium) > 10:
                report += f"\n*...and {len(medium) - 10} more medium issues*\n"

        report += """
---

*This report was generated by the Vineyard Factory SecurityAgent.*
*Review all issues and apply fixes before deploying to production.*
"""

        try:
            github.create_file(
                owner=repo_info["owner"],
                repo=repo_info["name"],
                path="SECURITY_REPORT.md",
                content=report,
                message="docs(security): Add security scan report",
            )
            self.logger.info("Security report pushed to GitHub")
        except Exception as e:
            self.logger.error(f"Failed to push security report: {e}")
