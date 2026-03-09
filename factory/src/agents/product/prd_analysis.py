"""PRD Analysis Agent - Analyze PRD, identify gaps, Q&A, and enrich."""

import logging
from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import PRD_ANALYSIS_AGENT_PROMPT
from src.models import FactoryState, PRDAnalysisOutput
from src.tools import llm

logger = logging.getLogger(__name__)


class PRDAnalysisAgent(BaseAgent):
    """Agent for analyzing and enriching user-submitted PRDs."""

    name = "PRDAnalysisAgent"
    domain = "product"

    def run(self, state: FactoryState) -> PRDAnalysisOutput:
        """
        Analyze PRD, identify gaps, ask clarifying questions, and produce enriched PRD.
        """
        self.log_start()

        prd_input = state.handoff.prd_input
        prd_text = prd_input.prd_text
        product_name = prd_input.name

        # Step 1: Analyze PRD and identify gaps
        analysis = self._analyze_prd(product_name, prd_text, prd_input.additional_context)

        identified_gaps = analysis.get("identified_gaps", [])
        questions = analysis.get("clarifying_questions", [])

        # Step 2: Post questions to Slack and wait for answers (if questions exist)
        qa_pairs = []
        if questions and state.slack_channels.get("main"):
            qa_pairs = self._run_qa_flow(state, questions)

        # Step 3: Enrich PRD with answers
        enrichment = self._enrich_prd(product_name, prd_text, qa_pairs, prd_input.additional_context)

        output = PRDAnalysisOutput(
            product_name=product_name,
            product_summary=enrichment.get("product_summary", f"Building {product_name}"),
            enriched_prd_markdown=enrichment.get("enriched_prd_markdown", prd_text),
            identified_gaps=identified_gaps,
            clarification_qa=qa_pairs,
            target_users=enrichment.get("target_users", []),
            core_problem=enrichment.get("core_problem", ""),
            mvp_scope_notes=enrichment.get("mvp_scope_notes", ""),
        )

        self.log_complete()
        return output

    def _analyze_prd(self, product_name: str, prd_text: str, additional_context: str | None) -> dict:
        """Analyze the PRD and identify gaps and questions."""
        context_section = ""
        if additional_context:
            context_section = f"\nADDITIONAL CONTEXT: {additional_context}"

        user_prompt = f"""Analyze this PRD and identify gaps and clarifying questions:

PRODUCT NAME: {product_name}
PRD TEXT:
{prd_text}
{context_section}

Generate JSON with your analysis:
{{
    "identified_gaps": [
        "Missing user personas",
        "No success metrics defined"
    ],
    "clarifying_questions": [
        "Who is the primary target user for this product?",
        "What does success look like in the first 3 months?"
    ],
    "initial_assessment": {{
        "prd_quality": "sparse|moderate|detailed",
        "core_problem_clear": true,
        "target_users_clear": false,
        "scope_clear": false
    }}
}}

Guidelines:
- For sparse PRDs (1-2 sentences): Ask 5-8 questions
- For moderate PRDs: Ask 3-5 questions
- For detailed PRDs: Ask 0-2 questions
- Focus on the most impactful gaps first
- Questions should be answerable in 1-2 sentences
"""

        try:
            return llm.generate_json(
                PRD_ANALYSIS_AGENT_PROMPT, user_prompt, model=llm.MODEL_OPUS
            )
        except Exception as e:
            self.logger.error(f"Failed to analyze PRD: {e}")
            return {"identified_gaps": ["Analysis failed"], "clarifying_questions": []}

    def _run_qa_flow(self, state: FactoryState, questions: list[str]) -> list[dict]:
        """Post questions to Slack and wait for answers."""
        try:
            from src.slack.qa import post_questions, wait_for_answers

            channel_id = state.slack_channels.get("main")
            if not channel_id:
                self.logger.warning("No main Slack channel for Q&A")
                return [{"question": q, "answer": "(no answer - no channel)"} for q in questions]

            thread_ts = state.slack_qa_thread_ts
            if not thread_ts:
                self.logger.warning("No Q&A thread timestamp")
                return [{"question": q, "answer": "(no answer - no thread)"} for q in questions]

            # Post questions
            post_questions(channel_id, thread_ts, questions)

            # Wait for answers
            answers = wait_for_answers(
                channel_id, thread_ts,
                question_count=len(questions),
                timeout_minutes=30,
            )

            # Pair questions with answers
            qa_pairs = []
            for i, question in enumerate(questions):
                answer = answers[i] if i < len(answers) else "(no answer provided)"
                qa_pairs.append({"question": question, "answer": answer})

            return qa_pairs

        except Exception as e:
            self.logger.error(f"Q&A flow failed: {e}")
            return [{"question": q, "answer": "(Q&A flow failed)"} for q in questions]

    def _enrich_prd(
        self,
        product_name: str,
        prd_text: str,
        qa_pairs: list[dict],
        additional_context: str | None,
    ) -> dict:
        """Enrich the PRD with Q&A answers and fill gaps."""
        qa_section = ""
        if qa_pairs:
            qa_lines = []
            for qa in qa_pairs:
                qa_lines.append(f"Q: {qa['question']}")
                qa_lines.append(f"A: {qa['answer']}")
            qa_section = "\n".join(qa_lines)

        context_section = ""
        if additional_context:
            context_section = f"\nADDITIONAL CONTEXT: {additional_context}"

        user_prompt = f"""Enrich this PRD into a comprehensive product document:

PRODUCT NAME: {product_name}

ORIGINAL PRD:
{prd_text}
{context_section}

CLARIFICATION Q&A:
{qa_section if qa_section else "(No Q&A - enrich based on best judgment)"}

Generate JSON with the enriched PRD:
{{
    "product_summary": "One paragraph summary of the product",
    "core_problem": "The core problem this product solves",
    "target_users": ["User type 1", "User type 2"],
    "mvp_scope_notes": "Notes on what should and shouldn't be in MVP",
    "enriched_prd_markdown": "# Full enriched PRD in markdown\\n\\n## Problem Statement\\n..."
}}

The enriched PRD markdown should include:
1. Problem Statement
2. Target Users
3. Goals and Success Metrics
4. Core Features (P0 MVP, P1 post-launch, P2 future)
5. User Stories
6. Out of Scope for MVP
7. Technical Considerations
8. Open Questions / Assumptions

Where answers were not provided, make reasonable assumptions and mark them as [ASSUMPTION].
"""

        try:
            return llm.generate_json(
                PRD_ANALYSIS_AGENT_PROMPT, user_prompt, model=llm.MODEL_OPUS
            )
        except Exception as e:
            self.logger.error(f"Failed to enrich PRD: {e}")
            return {
                "product_summary": f"Building {product_name}",
                "core_problem": "",
                "target_users": [],
                "mvp_scope_notes": "",
                "enriched_prd_markdown": prd_text,
            }
