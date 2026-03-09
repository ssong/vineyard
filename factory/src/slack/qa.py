"""Slack Thread Q&A Mechanism for PRD clarification."""

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Global state for tracking Q&A sessions
_qa_sessions: dict[str, dict] = {}
_qa_lock = threading.Lock()


def post_questions(channel_id: str, thread_ts: str, questions: list[str]) -> None:
    """Post formatted questions to a Slack thread.

    Args:
        channel_id: Slack channel ID
        thread_ts: Thread timestamp to reply to
        questions: List of questions to post
    """
    from src.slack.app import app

    # Format questions as numbered list
    question_lines = []
    for i, q in enumerate(questions, 1):
        question_lines.append(f"*{i}.* {q}")

    questions_text = "\n".join(question_lines)

    try:
        app.client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=(
                "I have a few clarifying questions about your PRD. "
                "Please reply in this thread with your answers.\n\n"
                f"{questions_text}\n\n"
                "_Reply with your answers (numbered to match), then click "
                "the button below or type `done` when finished._"
            ),
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            "I have a few clarifying questions about your PRD. "
                            "Please reply in this thread with your answers.\n\n"
                            f"{questions_text}"
                        ),
                    },
                },
                {"type": "divider"},
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "_Reply with your answers, then click the button or type `done` when finished. "
                            "I'll proceed automatically after 30 minutes._",
                        }
                    ],
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Done Answering", "emoji": True},
                            "style": "primary",
                            "value": thread_ts,
                            "action_id": "qa_done",
                        }
                    ],
                },
            ],
        )

        # Register Q&A session
        session_key = f"{channel_id}:{thread_ts}"
        with _qa_lock:
            _qa_sessions[session_key] = {
                "questions": questions,
                "answers": [],
                "done_event": threading.Event(),
                "channel_id": channel_id,
                "thread_ts": thread_ts,
            }

    except Exception as e:
        logger.error(f"Failed to post questions: {e}")
        raise


def wait_for_answers(
    channel_id: str,
    thread_ts: str,
    question_count: int,
    timeout_minutes: int = 30,
) -> list[str]:
    """Wait for user answers in the Slack thread.

    Args:
        channel_id: Slack channel ID
        thread_ts: Thread timestamp
        question_count: Number of questions asked
        timeout_minutes: Maximum wait time in minutes

    Returns:
        List of answer strings (may be shorter than question_count if timeout)
    """
    session_key = f"{channel_id}:{thread_ts}"

    with _qa_lock:
        session = _qa_sessions.get(session_key)

    if not session:
        logger.warning(f"No Q&A session found for {session_key}")
        return []

    done_event = session["done_event"]

    # Wait for done signal or timeout
    done_event.wait(timeout=timeout_minutes * 60)

    # Collect answers
    with _qa_lock:
        session = _qa_sessions.get(session_key, {})
        answers = session.get("answers", [])

        # If no answers collected via event handler, try fetching from thread
        if not answers:
            answers = _fetch_thread_replies(channel_id, thread_ts)

        # Clean up session
        _qa_sessions.pop(session_key, None)

    return answers


def record_answer(channel_id: str, thread_ts: str, answer_text: str) -> None:
    """Record an answer from the Slack thread.

    Called by the thread message event handler.

    Args:
        channel_id: Slack channel ID
        thread_ts: Thread timestamp
        answer_text: The user's answer text
    """
    session_key = f"{channel_id}:{thread_ts}"

    with _qa_lock:
        session = _qa_sessions.get(session_key)
        if session:
            session["answers"].append(answer_text)


def signal_done(channel_id: str, thread_ts: str) -> None:
    """Signal that the user is done answering questions.

    Called by the qa_done button handler or when user types 'done'.

    Args:
        channel_id: Slack channel ID
        thread_ts: Thread timestamp
    """
    session_key = f"{channel_id}:{thread_ts}"

    with _qa_lock:
        session = _qa_sessions.get(session_key)
        if session:
            session["done_event"].set()
            logger.info(f"Q&A session done signal received for {session_key}")


def _fetch_thread_replies(channel_id: str, thread_ts: str) -> list[str]:
    """Fetch replies from a Slack thread as fallback.

    Args:
        channel_id: Slack channel ID
        thread_ts: Thread timestamp

    Returns:
        List of reply texts (excluding bot messages)
    """
    try:
        from src.slack.app import app

        result = app.client.conversations_replies(
            channel=channel_id,
            ts=thread_ts,
            limit=50,
        )

        messages = result.get("messages", [])
        answers = []

        for msg in messages[1:]:  # Skip the parent message
            # Skip bot messages
            if msg.get("bot_id") or msg.get("subtype") == "bot_message":
                continue

            text = msg.get("text", "").strip()
            if text and text.lower() != "done":
                answers.append(text)

        return answers

    except Exception as e:
        logger.error(f"Failed to fetch thread replies: {e}")
        return []
