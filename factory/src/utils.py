"""Shared utilities for external API integrations."""


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to max_length, adding suffix if truncated.

    Args:
        text: The text to truncate
        max_length: Maximum allowed length
        suffix: String to append when truncated (default: "...")

    Returns:
        The truncated text with suffix if it exceeded max_length
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


# =============================================================================
# Third-Party API Character Limits
# =============================================================================

# Linear API limits
class LinearLimits:
    PROJECT_DESCRIPTION = 255
    ISSUE_TITLE = 500
    ISSUE_DESCRIPTION = 50000
    COMMENT_BODY = 10000
    LABEL_NAME = 50


# GitHub API limits
class GitHubLimits:
    REPO_DESCRIPTION = 350
    PR_TITLE = 256
    PR_BODY = 65536
    COMMIT_MESSAGE_SUBJECT = 72


# Miro API limits
class MiroLimits:
    BOARD_NAME = 60
    BOARD_DESCRIPTION = 300
    SHAPE_CONTENT = 2000
    STICKY_NOTE_CONTENT = 6000
    FRAME_TITLE = 200


# Slack API limits
class SlackLimits:
    TEXT_LENGTH = 3000
    ERROR_MESSAGE = 500
    BLOCK_TEXT = 3000
