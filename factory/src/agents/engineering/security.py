"""Security Agent - Security scanning and recommendations."""

from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import SECURITY_AGENT_PROMPT
from src.models import FactoryState
from src.tools import linear, llm


class SecurityAgent(BaseAgent):
    """Agent for security analysis and recommendations."""

    name = "SecurityAgent"
    domain = "engineering"

    def run(self, state: FactoryState) -> dict[str, Any]:
        """
        Perform security analysis and generate recommendations.
        """
        self.log_start()

        opp = state.handoff.opportunity
        prefs = state.handoff.build_preferences
        build = self.get_previous_output(state, "build")

        files = build.get("files", []) if build else []

        # Perform code security analysis
        code_issues = self._analyze_code_security(files)

        # Check for common vulnerabilities
        vuln_check = self._check_vulnerabilities(prefs)

        # Check dependencies
        dep_issues = self._check_dependencies(prefs)

        # Generate security recommendations
        recommendations = self._generate_recommendations(code_issues, vuln_check, dep_issues)

        # Generate security documentation
        security_doc = self._generate_security_doc(opp, recommendations)

        # Create Linear issues
        linear_issues = self._create_linear_issues(state, recommendations)

        output = {
            "code_issues": code_issues,
            "vulnerability_check": vuln_check,
            "dependency_issues": dep_issues,
            "recommendations": recommendations,
            "security_documentation": security_doc,
            "linear_issues": linear_issues,
        }

        self.log_complete()
        return output

    def _analyze_code_security(self, files) -> list[dict]:
        """Analyze code for security issues."""
        if not files:
            return []

        # Sample a subset of files for analysis
        sample_files = [f for f in files if f.language in ["typescript", "python"]][:5]
        files_content = "\n\n".join(
            [f"### {f.path}\n```{f.language}\n{f.content[:500]}...\n```" for f in sample_files]
        )

        user_prompt = f"""Analyze this code for security issues:

{files_content}

Generate JSON with security findings:
{{
    "issues": [
        {{
            "severity": "high" | "medium" | "low",
            "category": "OWASP category",
            "file": "path/to/file",
            "line": 42,
            "description": "Description of the issue",
            "remediation": "How to fix"
        }}
    ]
}}

Check for:
- SQL injection
- XSS vulnerabilities
- Hardcoded secrets
- Insecure authentication
- Missing input validation
- Information disclosure
"""

        try:
            result = llm.generate_json(SECURITY_AGENT_PROMPT, user_prompt)
            return result.get("issues", [])
        except Exception as e:
            self.logger.error(f"Failed to analyze code security: {e}")
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

    def _check_dependencies(self, prefs) -> list[dict]:
        """Check for dependency security issues."""
        user_prompt = f"""Analyze dependency security for this stack:

FRONTEND: {prefs.tech_stack.get('frontend')}
BACKEND: {prefs.tech_stack.get('backend')}

Generate JSON with dependency recommendations:
{{
    "high_risk_dependencies": [
        {{"package": "...", "reason": "...", "alternative": "..."}}
    ],
    "recommended_security_packages": [
        {{"package": "helmet", "purpose": "HTTP security headers"}}
    ],
    "version_recommendations": [
        {{"package": "...", "min_version": "..."}}
    ]
}}
"""

        try:
            result = llm.generate_json(SECURITY_AGENT_PROMPT, user_prompt)
            return result.get("high_risk_dependencies", [])
        except Exception as e:
            self.logger.error(f"Failed to check dependencies: {e}")
            return []

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

    def _create_linear_issues(
        self, state: FactoryState, recommendations: list
    ) -> list[str]:
        """Create Linear issues for security recommendations."""
        try:
            project = linear.get_project(state.handoff.linear_project_id)
            team_id = project.get("teams", {}).get("nodes", [{}])[0].get("id", "")

            if not team_id:
                return []

            issues = []
            for rec in recommendations[:5]:  # Limit to top 5
                issues.append({
                    "title": f"[Security] {rec.get('title', 'Security Task')}",
                    "description": f"**Priority:** {rec.get('priority', 'P1')}\n\n"
                    f"{rec.get('description', '')}\n\n"
                    f"**Remediation:** {rec.get('remediation', 'See details')}",
                    "labels": ["security"],
                })

            return linear.create_issues_batch(
                state.handoff.linear_project_id, team_id, issues
            )

        except Exception as e:
            self.logger.error(f"Failed to create Linear issues: {e}")
            return []
