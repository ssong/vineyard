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
# Sources verified January 2026
# =============================================================================

# Linear API limits (from API validation errors)
class LinearLimits:
    PROJECT_DESCRIPTION = 255  # Confirmed via API error
    ISSUE_TITLE = 500
    ISSUE_DESCRIPTION = 50000
    COMMENT_BODY = 10000
    LABEL_NAME = 50


# GitHub API limits
# Source: https://github.com/dead-claudia/github-limits
class GitHubLimits:
    REPO_NAME = 100
    REPO_DESCRIPTION = 350
    ISSUE_TITLE = 256
    ISSUE_BODY = 65536
    PR_TITLE = 256  # Same as issue title
    PR_BODY = 65536
    ISSUE_COMMENT = 65536  # 262,144 bytes, ~65K UTF-8 chars
    COMMIT_MESSAGE_SUBJECT = 72  # Conventional limit


# Slack API limits
# Source: https://docs.slack.dev/reference/block-kit/blocks/section-block/
class SlackLimits:
    MESSAGE_TEXT = 4000  # Recommended for best results
    MESSAGE_TEXT_MAX = 40000  # Hard limit before truncation
    SECTION_BLOCK_TEXT = 3000
    SECTION_FIELD_TEXT = 2000  # Each field in fields array
    MAX_BLOCKS_PER_MESSAGE = 50
    ERROR_MESSAGE = 500  # Our internal limit for error summaries
