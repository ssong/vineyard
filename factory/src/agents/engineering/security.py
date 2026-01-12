"""Security Agent - Ruby on Rails security scanning and recommendations."""

import re
from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import SECURITY_AGENT_PROMPT
from src.models import FactoryState, GeneratedFile
from src.tools import github, llm


class SecurityAgent(BaseAgent):
    """
    Agent for comprehensive security analysis of Rails applications.

    Performs:
    - Pattern-based secret detection
    - OWASP vulnerability scanning (Rails-specific)
    - Dependency security analysis (Bundler audit)
    - Devise authentication review
    - API security assessment
    - Brakeman-style static analysis
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
        r'sk_live_[a-zA-Z0-9]{24,}': "Stripe Live Secret Key",
        r'sk_test_[a-zA-Z0-9]{24,}': "Stripe Test Secret Key",
        r'ghp_[a-zA-Z0-9]{36}': "GitHub Personal Access Token",
        r'gho_[a-zA-Z0-9]{36}': "GitHub OAuth Token",
        r'glpat-[a-zA-Z0-9\-_]{20,}': "GitLab Personal Access Token",
        r'(?:private[_-]?key|privatekey)\s*[=:]\s*["\']-----BEGIN': "Private Key",
        r'mongodb(?:\+srv)?://[^"\'\s]+': "MongoDB Connection String",
        r'postgres(?:ql)?://[^"\'\s]+': "PostgreSQL Connection String",
        r'mysql://[^"\'\s]+': "MySQL Connection String",
        r'redis://[^"\'\s]+': "Redis Connection String",
        r'(?:bearer|token)\s+[a-zA-Z0-9._-]{20,}': "Bearer Token",
        r'Rails\.application\.credentials\.[a-z_]+\s*=': "Credentials Assignment",
    }

    # SQL injection patterns for ActiveRecord
    SQL_INJECTION_PATTERNS = {
        r'\.where\s*\(\s*["\'].*#\{': "String interpolation in where clause",
        r'\.where\s*\(\s*["\'].*\+\s*(?:params|request)': "String concatenation in where clause",
        r'\.order\s*\(\s*["\'].*#\{': "String interpolation in order clause",
        r'\.order\s*\(\s*params\[': "Unsafe params in order clause",
        r'find_by_sql\s*\(\s*["\'].*#\{': "String interpolation in find_by_sql",
        r'execute\s*\(\s*["\'].*#\{': "String interpolation in execute",
        r'\.pluck\s*\(\s*params\[': "Unsafe params in pluck",
        r'\.select\s*\(\s*params\[': "Unsafe params in select",
        r'connection\.execute\s*\(.*#\{': "Unsafe interpolation in raw SQL",
    }

    # XSS patterns for Rails/ERB
    XSS_PATTERNS = {
        r'\.html_safe(?!\s*if)': "Unsafe html_safe usage",
        r'\braw\s*\((?!.*sanitize)': "Unsafe raw() output",
        r'<%==': "Unescaped ERB output (<%==)",
        r'content_tag\s*\([^)]*\.html_safe': "html_safe in content_tag",
        r'render\s+inline:': "Inline render (potential XSS)",
        r'link_to\s*\([^)]*params\[': "User input in link_to",
        r'sanitize\s*\(\s*[^,)]+,\s*tags:\s*\[\]': "Empty sanitize allowlist",
    }

    # Command injection patterns for Ruby
    COMMAND_INJECTION_PATTERNS = {
        r'`[^`]*#\{(?:params|request|session)': "Backticks with user input",
        r'system\s*\([^)]*#\{(?:params|request)': "system() with user input",
        r'exec\s*\([^)]*#\{(?:params|request)': "exec() with user input",
        r'%x\{[^}]*#\{(?:params|request)': "Percent-x with user input",
        r'IO\.popen\s*\([^)]*#\{(?:params|request)': "IO.popen with user input",
        r'Open3\.\w+\s*\([^)]*#\{(?:params|request)': "Open3 with user input",
        r'Kernel\.send\s*\(\s*params\[': "Dynamic method dispatch with params",
        r'\.send\s*\(\s*params\[': "send() with user input",
        r'eval\s*\([^)]*(?:params|request)': "eval() with user input",
        r'instance_eval\s*\([^)]*(?:params|request)': "instance_eval with user input",
        r'class_eval\s*\([^)]*(?:params|request)': "class_eval with user input",
        r'constantize\s*(?:\(\s*)?params\[': "constantize with user input",
    }

    # Auth vulnerability patterns for Devise/Rails
    AUTH_PATTERNS = {
        r'skip_before_action\s*:\s*authenticate': "Authentication skipped",
        r'devise.*:omniauthable.*\bopenid\b': "OpenID (deprecated) in Devise",
        r'config\.secret_key\s*=\s*["\'][^"\']{0,32}["\']': "Weak Devise secret key",
        r'config\.pepper\s*=\s*["\'][^"\']{0,16}["\']': "Weak Devise pepper",
        r'allow_unconfirmed_access_for\s*=\s*nil': "Unlimited unconfirmed access",
        r'config\.password_length\s*=\s*\d\.\.(\d+)': "Check password length",
        r'has_secure_password\s+validations:\s*false': "Password validations disabled",
        r'BCrypt::Password\.create\([^)]*cost:\s*[1-9]\)': "Low BCrypt cost factor",
        r'sign_in\s*\([^)]*bypass:\s*true': "Authentication bypass",
    }

    # Mass assignment patterns
    MASS_ASSIGNMENT_PATTERNS = {
        r'\.update\s*\(\s*params\s*\)': "Mass assignment without permit",
        r'\.create\s*\(\s*params\s*\)': "Mass assignment without permit",
        r'\.new\s*\(\s*params\s*\)': "Mass assignment without permit",
        r'\.assign_attributes\s*\(\s*params\s*\)': "Mass assignment without permit",
        r'attr_accessible': "Deprecated attr_accessible (use strong params)",
        r'params\.permit!': "Permitting all params (dangerous)",
    }

    # File/path traversal patterns
    PATH_TRAVERSAL_PATTERNS = {
        r'File\.read\s*\([^)]*params\[': "File.read with user input",
        r'File\.open\s*\([^)]*params\[': "File.open with user input",
        r'send_file\s*\([^)]*params\[': "send_file with user input",
        r'render\s+file:\s*[^,]*params\[': "render file with user input",
        r'\.join\s*\([^)]*params\[': "Path join with user input",
    }

    def run(self, state: FactoryState) -> dict[str, Any]:
        """
        Perform comprehensive security analysis of Rails application.
        """
        self.log_start()

        opp = state.handoff.opportunity
        prefs = state.handoff.build_preferences
        build = self.get_previous_output(state, "build")

        # BUILD phase stores composite output
        code_output = build.get("code", {}) if isinstance(build, dict) else {}
        files = code_output.get("files", []) if code_output else []

        # Convert to dict for easier lookup
        files_dict = {f.path: f for f in files}

        # Run pattern-based security scans
        self.logger.info(f"Scanning {len(files)} files for security issues...")
        secret_issues = self._scan_for_secrets(files_dict)
        injection_issues = self._scan_for_injection(files_dict)
        auth_issues = self._scan_for_auth_vulnerabilities(files_dict)
        mass_assignment_issues = self._scan_for_mass_assignment(files_dict)
        path_traversal_issues = self._scan_for_path_traversal(files_dict)

        # Perform AI-powered code security analysis
        code_issues = self._analyze_code_security(files)

        # Check for common vulnerabilities based on stack
        vuln_check = self._check_vulnerabilities(prefs)

        # Check dependencies (Gemfile)
        dep_issues = self._check_dependencies(files_dict, prefs)

        # Combine all issues
        all_code_issues = (
            secret_issues +
            injection_issues +
            auth_issues +
            mass_assignment_issues +
            path_traversal_issues +
            code_issues
        )

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
            "mass_assignment_issues": mass_assignment_issues,
            "path_traversal_issues": path_traversal_issues,
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
            if not path.endswith((".rb", ".erb", ".rake", ".yml", ".yaml", ".env")):
                continue
            if "spec/" in path or "test/" in path or "fixtures" in path:
                continue
            # Skip example files
            if path.endswith(".example") or ".example." in path:
                continue
            # Skip Rails credentials files (encrypted)
            if "credentials" in path and path.endswith(".enc"):
                continue

            content = f.content
            lines = content.split("\n")

            for pattern, description in self.SECRET_PATTERNS.items():
                for i, line in enumerate(lines, 1):
                    # Skip comments
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    # Skip ENV references
                    if "ENV[" in line or "ENV.fetch" in line:
                        continue
                    # Skip Rails credentials lookups
                    if "Rails.application.credentials." in line and "=" not in line:
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
                            "remediation": "Move secret to Rails credentials or ENV variable",
                        })

        self.logger.info(f"Found {len(issues)} potential secret issues")
        return issues

    def _scan_for_injection(self, files_dict: dict[str, GeneratedFile]) -> list[dict]:
        """Scan for SQL injection, XSS, and command injection vulnerabilities."""
        issues = []

        for path, f in files_dict.items():
            if not path.endswith((".rb", ".erb")):
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
                            "remediation": "Use ActiveRecord query methods with placeholders: where('column = ?', value)",
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
                            "remediation": "Use sanitize() helper or avoid html_safe/raw with user input",
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
                            "remediation": "Avoid shell commands with user input; use allowlists or Shellwords.escape()",
                        })

        self.logger.info(f"Found {len(issues)} injection vulnerability issues")
        return issues

    def _scan_for_auth_vulnerabilities(self, files_dict: dict[str, GeneratedFile]) -> list[dict]:
        """Scan for authentication and authorization vulnerabilities."""
        issues = []

        for path, f in files_dict.items():
            if not path.endswith(".rb"):
                continue

            content = f.content
            lines = content.split("\n")

            # Check auth vulnerability patterns
            for pattern, description in self.AUTH_PATTERNS.items():
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line, re.IGNORECASE):
                        issues.append({
                            "severity": "high",
                            "category": "A07:2021-Identification and Auth Failures",
                            "type": "auth_vulnerability",
                            "file": path,
                            "line": i,
                            "description": f"Auth issue: {description}",
                            "context": line.strip()[:100],
                            "remediation": "Review authentication configuration",
                        })

            # Check for missing auth on API controllers
            if "controllers/api" in path and "_controller.rb" in path:
                # Check if authentication is present
                has_auth_check = any([
                    "before_action :authenticate" in content,
                    "authenticate_user!" in content,
                    "authenticate_api" in content,
                    "doorkeeper_authorize!" in content,
                    "skip_before_action" not in content or "authenticate" not in content,
                ])

                if not has_auth_check:
                    # Check if it's a public endpoint
                    is_public = any([
                        "health" in path.lower(),
                        "webhook" in path.lower(),
                        "public" in path.lower(),
                        "sessions" in path.lower(),
                        "registrations" in path.lower(),
                    ])

                    if not is_public:
                        issues.append({
                            "severity": "high",
                            "category": "A01:2021-Broken Access Control",
                            "type": "missing_auth",
                            "file": path,
                            "line": 1,
                            "description": "API controller may be missing authentication",
                            "context": f"No authenticate_user! or similar in {path}",
                            "remediation": "Add before_action :authenticate_user! or mark as intentionally public",
                        })

        self.logger.info(f"Found {len(issues)} auth vulnerability issues")
        return issues

    def _scan_for_mass_assignment(self, files_dict: dict[str, GeneratedFile]) -> list[dict]:
        """Scan for mass assignment vulnerabilities."""
        issues = []

        for path, f in files_dict.items():
            if not path.endswith(".rb"):
                continue

            content = f.content
            lines = content.split("\n")

            for pattern, description in self.MASS_ASSIGNMENT_PATTERNS.items():
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line):
                        # Special handling for params.permit!
                        severity = "critical" if "permit!" in line else "high"
                        issues.append({
                            "severity": severity,
                            "category": "A04:2021-Insecure Design",
                            "type": "mass_assignment",
                            "file": path,
                            "line": i,
                            "description": f"Mass assignment risk: {description}",
                            "context": line.strip()[:100],
                            "remediation": "Use strong parameters: params.require(:model).permit(:field1, :field2)",
                        })

        self.logger.info(f"Found {len(issues)} mass assignment issues")
        return issues

    def _scan_for_path_traversal(self, files_dict: dict[str, GeneratedFile]) -> list[dict]:
        """Scan for path traversal vulnerabilities."""
        issues = []

        for path, f in files_dict.items():
            if not path.endswith(".rb"):
                continue

            content = f.content
            lines = content.split("\n")

            for pattern, description in self.PATH_TRAVERSAL_PATTERNS.items():
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line):
                        issues.append({
                            "severity": "critical",
                            "category": "A01:2021-Broken Access Control",
                            "type": "path_traversal",
                            "file": path,
                            "line": i,
                            "description": f"Path traversal risk: {description}",
                            "context": line.strip()[:100],
                            "remediation": "Validate and sanitize file paths; use send_file with :disposition",
                        })

        self.logger.info(f"Found {len(issues)} path traversal issues")
        return issues

    def _analyze_code_security(self, files) -> list[dict]:
        """AI-powered deeper analysis for complex security issues."""
        if not files:
            return []

        # Categorize files for targeted analysis
        controller_files = [f for f in files if "controllers" in f.path and f.language == "ruby"]
        model_files = [f for f in files if "models" in f.path and f.language == "ruby"]
        service_files = [f for f in files if "services" in f.path and f.language == "ruby"]
        config_files = [f for f in files if "config" in f.path or "initializers" in f.path]

        all_issues = []

        # Analyze controller security
        if controller_files:
            controller_issues = self._analyze_controller_security(controller_files[:10])
            all_issues.extend(controller_issues)

        # Analyze model security
        if model_files:
            model_issues = self._analyze_model_security(model_files[:10])
            all_issues.extend(model_issues)

        # Analyze service security
        if service_files:
            service_issues = self._analyze_service_security(service_files[:5])
            all_issues.extend(service_issues)

        # Analyze configuration security
        if config_files:
            config_issues = self._analyze_config_security(config_files[:5])
            all_issues.extend(config_issues)

        return all_issues

    def _analyze_controller_security(self, controller_files) -> list[dict]:
        """Analyze Rails controllers for security issues."""
        files_content = "\n\n".join([
            f"### {f.path}\n```ruby\n{f.content}\n```"
            for f in controller_files
        ])

        user_prompt = f"""Analyze these Rails controllers for security issues:

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
- Missing before_action authentication
- Improper strong parameters (permit!)
- Direct object reference without authorization (IDOR)
- Missing CSRF protection (protect_from_forgery)
- Unsafe redirects (open redirect)
- Information disclosure in error handling
- Missing rate limiting
- Unsafe render/send_file operations
"""

        try:
            result = llm.generate_json(SECURITY_AGENT_PROMPT, user_prompt)
            return result.get("issues", [])
        except Exception as e:
            self.logger.error(f"Failed to analyze controller security: {e}")
            return []

    def _analyze_model_security(self, model_files) -> list[dict]:
        """Analyze Rails models for security issues."""
        files_content = "\n\n".join([
            f"### {f.path}\n```ruby\n{f.content}\n```"
            for f in model_files
        ])

        user_prompt = f"""Analyze these Rails models for security issues:

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
- Missing validations on sensitive fields
- Unsafe serialization (serialize with YAML)
- Weak password requirements (has_secure_password config)
- Missing encrypted attributes for sensitive data
- Scope injection vulnerabilities
- Unsafe callbacks with user data
- Missing uniqueness validations
"""

        try:
            result = llm.generate_json(SECURITY_AGENT_PROMPT, user_prompt)
            return result.get("issues", [])
        except Exception as e:
            self.logger.error(f"Failed to analyze model security: {e}")
            return []

    def _analyze_service_security(self, service_files) -> list[dict]:
        """Analyze service objects for security issues."""
        files_content = "\n\n".join([
            f"### {f.path}\n```ruby\n{f.content}\n```"
            for f in service_files
        ])

        user_prompt = f"""Analyze these Rails service objects for security issues:

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
- Unsafe external API calls (missing SSL verification)
- Logging sensitive data
- Missing input validation
- Unsafe deserialization
- Shell command execution
- Webhook signature verification
- API key handling
"""

        try:
            result = llm.generate_json(SECURITY_AGENT_PROMPT, user_prompt)
            return result.get("issues", [])
        except Exception as e:
            self.logger.error(f"Failed to analyze service security: {e}")
            return []

    def _analyze_config_security(self, config_files) -> list[dict]:
        """Analyze Rails configuration for security issues."""
        files_content = "\n\n".join([
            f"### {f.path}\n```ruby\n{f.content}\n```"
            for f in config_files
        ])

        user_prompt = f"""Analyze these Rails configuration files for security issues:

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
- Weak session configuration
- Missing security headers
- Overly permissive CORS
- Debug mode in production
- Logging level issues
- Insecure cookie settings
- Missing SSL enforcement
- Weak encryption settings
"""

        try:
            result = llm.generate_json(SECURITY_AGENT_PROMPT, user_prompt)
            return result.get("issues", [])
        except Exception as e:
            self.logger.error(f"Failed to analyze config security: {e}")
            return []

    def _check_vulnerabilities(self, prefs) -> dict:
        """Check for common vulnerability patterns in Rails stack."""
        user_prompt = f"""Check for common vulnerabilities in this Rails stack:

FRAMEWORK: Ruby on Rails 7.1
FRONTEND: Hotwire (Turbo + Stimulus)
DATABASE: {prefs.tech_stack.get('database', 'postgresql')}
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

Consider Rails-specific risks:
- Mass assignment (strong parameters)
- CSRF protection
- SQL injection with ActiveRecord
- XSS with html_safe/raw
- Session fixation
- Devise configuration
"""

        try:
            return llm.generate_json(SECURITY_AGENT_PROMPT, user_prompt)
        except Exception as e:
            self.logger.error(f"Failed to check vulnerabilities: {e}")
            return {"overall_risk_level": "unknown"}

    def _check_dependencies(
        self, files_dict: dict[str, GeneratedFile], prefs
    ) -> list[dict]:
        """Check for dependency security issues by analyzing Gemfile."""
        issues = []

        # Known risky or deprecated gems
        RISKY_GEMS = {
            "attr_encrypted": ("deprecated", "Use Rails 7 encrypts or lockbox gem"),
            "cancan": ("deprecated", "Use cancancan instead"),
            "authlogic": ("outdated", "Consider Devise for better maintenance"),
            "therubyracer": ("deprecated", "Use mini_racer or Node.js"),
            "execjs": ("potential_issue", "Ensure secure runtime configured"),
            "safe_yaml": ("deprecated", "YAML.safe_load is now default in Ruby"),
            "json": ("check_version", "Ensure version >= 2.3.0 for CVE fixes"),
            "rails-html-sanitizer": ("check_version", "Ensure version >= 1.4.4"),
            "nokogiri": ("check_version", "Keep updated for CVE patches"),
            "rack": ("check_version", "Ensure version >= 2.2.6.2 for CVE fixes"),
            "loofah": ("check_version", "Keep updated for XSS vulnerability patches"),
            "httparty": ("consider_alternative", "Consider faraday with SSL verification"),
        }

        # Check actual Gemfile
        gemfile = files_dict.get("Gemfile")
        if gemfile:
            content = gemfile.content.lower()

            for gem, (reason, alternative) in RISKY_GEMS.items():
                if f"gem '{gem}'" in content or f'gem "{gem}"' in content:
                    severity = "critical" if reason in ["deprecated", "compromised"] else "medium"
                    issues.append({
                        "package": gem,
                        "reason": reason,
                        "alternative": alternative,
                        "severity": severity,
                    })

            # Check for gems without version constraints
            lines = gemfile.content.split("\n")
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("gem ") and "," not in stripped and "github:" not in stripped:
                    # Extract gem name
                    match = re.search(r'gem\s+["\']([^"\']+)["\']', stripped)
                    if match:
                        gem_name = match.group(1)
                        if gem_name not in ["rails", "pg", "puma"]:  # Skip common ones
                            issues.append({
                                "package": gem_name,
                                "reason": "no_version_constraint",
                                "alternative": f"Pin version: gem '{gem_name}', '~> X.Y'",
                                "severity": "low",
                            })

        # Get AI recommendations for the Rails stack
        user_prompt = f"""Analyze dependency security for this Rails stack:

AUTH: {prefs.auth_preference}
PAYMENTS: {prefs.payments_preference}

Generate JSON with security gem recommendations:
{{
    "recommended_security_gems": [
        {{"gem": "rack-attack", "purpose": "Rate limiting and blocking", "priority": "high"}},
        {{"gem": "brakeman", "purpose": "Static security analysis", "priority": "high"}},
        {{"gem": "bundler-audit", "purpose": "Dependency vulnerability scanning", "priority": "high"}}
    ],
    "version_recommendations": [
        {{"gem": "...", "min_version": "...", "reason": "..."}}
    ]
}}

Recommend gems for:
- Rate limiting (rack-attack)
- Security scanning (brakeman, bundler-audit)
- Secure headers (secure_headers)
- Strong parameters validation
- Input sanitization
"""

        try:
            result = llm.generate_json(SECURITY_AGENT_PROMPT, user_prompt)
            self._security_gems = result.get("recommended_security_gems", [])
        except Exception as e:
            self.logger.error(f"Failed to check dependencies: {e}")
            self._security_gems = []

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
            if dep.get("severity") in ["critical", "high"]:
                recommendations.append({
                    "priority": "P1",
                    "title": f"Update/replace {dep.get('package', 'dependency')}",
                    "description": dep.get("reason", ""),
                    "remediation": dep.get("alternative", ""),
                })

        # Add standard Rails security recommendations
        standard_recommendations = [
            {
                "priority": "P1",
                "title": "Run Brakeman security scan",
                "description": "Brakeman is the standard Rails security scanner",
                "remediation": "bundle exec brakeman -q",
            },
            {
                "priority": "P1",
                "title": "Run bundle audit",
                "description": "Check for known CVEs in dependencies",
                "remediation": "bundle audit --update",
            },
            {
                "priority": "P2",
                "title": "Review Rack::Attack configuration",
                "description": "Ensure rate limiting is properly configured",
                "remediation": "Review config/initializers/rack_attack.rb",
            },
        ]

        # Only add standard recommendations if they're not already covered
        existing_titles = {r.get("title", "").lower() for r in recommendations}
        for rec in standard_recommendations:
            if rec["title"].lower() not in existing_titles:
                recommendations.append(rec)

        return recommendations

    def _generate_security_doc(self, opp, recommendations: list) -> str:
        """Generate security documentation for Rails application."""
        user_prompt = f"""Generate security documentation for this Rails product:

PRODUCT: {opp.name}
FRAMEWORK: Ruby on Rails 7.1
AUTH: Devise
RECOMMENDATIONS: {len(recommendations)} items

Generate a markdown security document with:
1. Security Overview
2. Authentication Model (Devise)
3. Authorization Model (Pundit/CanCanCan)
4. Data Protection (Rails encrypts, ActiveRecord)
5. API Security (rate limiting, CORS)
6. Infrastructure Security (Railway)
7. Security Headers Configuration
8. Monitoring & Incident Response

Include Rails-specific security best practices.
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
**Framework:** Ruby on Rails 7.1

## Summary

- **Critical Issues:** {len(critical)}
- **High Issues:** {len(high)}
- **Medium Issues:** {len(medium)}
- **Total Issues:** {len(issues)}

## Quick Actions

```bash
# Run Brakeman security scan
bundle exec brakeman -q

# Check for vulnerable dependencies
bundle audit --update

# Auto-fix RuboCop security issues
bundle exec rubocop -A --only Security
```

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
*Run `bundle exec brakeman` and `bundle audit` before deploying to production.*
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
