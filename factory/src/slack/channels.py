"""Slack channel management for factory opportunities.

Creates and manages project-specific Slack channels with proper permissions.
"""

import logging
import re
from typing import Optional

from slack_sdk.errors import SlackApiError

from src.config import settings
from src.slack.app import app

logger = logging.getLogger(__name__)

# Slack channel name limits
MAX_CHANNEL_NAME_LENGTH = 80


def slugify_channel_name(name: str) -> str:
    """Convert opportunity name to valid Slack channel name.
    
    Slack channel names must:
    - Be lowercase
    - Contain only letters, numbers, hyphens, underscores
    - Be max 80 characters
    - Not start with # or contain spaces
    """
    # Lowercase and replace spaces with hyphens
    slug = name.lower().strip()
    slug = re.sub(r'\s+', '-', slug)
    
    # Remove invalid characters (keep only alphanumeric, hyphens, underscores)
    slug = re.sub(r'[^a-z0-9\-_]', '', slug)
    
    # Collapse multiple hyphens
    slug = re.sub(r'-+', '-', slug)
    
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    
    # Truncate to max length
    if len(slug) > MAX_CHANNEL_NAME_LENGTH:
        slug = slug[:MAX_CHANNEL_NAME_LENGTH].rstrip('-')
    
    return slug


def get_or_create_channel(
    name: str,
    description: str = "",
    is_private: bool = False,
) -> Optional[str]:
    """Get existing channel by name or create a new one.
    
    Args:
        name: Channel name (will be slugified)
        description: Channel description/topic
        is_private: Whether to create a private channel
        
    Returns:
        Channel ID if successful, None otherwise
    """
    channel_name = slugify_channel_name(name)
    
    if not channel_name:
        logger.error(f"Invalid channel name after slugification: {name}")
        return None
    
    try:
        # Try to create the channel
        if is_private:
            response = app.client.conversations_create(
                name=channel_name,
                is_private=True,
            )
        else:
            response = app.client.conversations_create(
                name=channel_name,
            )
        
        channel_id = response["channel"]["id"]
        logger.info(f"Created channel: {channel_name} ({channel_id})")
        
        # Set topic/description if provided
        if description:
            try:
                app.client.conversations_setTopic(
                    channel=channel_id,
                    topic=description[:250],  # Slack topic limit
                )
            except SlackApiError as e:
                logger.warning(f"Failed to set channel topic: {e}")
        
        return channel_id
        
    except SlackApiError as e:
        if e.response.get("error") == "name_taken":
            # Channel already exists, find it
            logger.info(f"Channel {channel_name} already exists, looking it up...")
            return _find_channel_by_name(channel_name)
        else:
            logger.error(f"Failed to create channel {channel_name}: {e}")
            return None


def _find_channel_by_name(name: str) -> Optional[str]:
    """Find a channel ID by name."""
    try:
        # Search public channels
        cursor = None
        while True:
            response = app.client.conversations_list(
                types="public_channel,private_channel",
                limit=200,
                cursor=cursor,
            )
            
            for channel in response.get("channels", []):
                if channel["name"] == name:
                    return channel["id"]
            
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        
        return None
        
    except SlackApiError as e:
        logger.error(f"Failed to list channels: {e}")
        return None


def add_user_to_channel(channel_id: str, user_id: str) -> bool:
    """Add a user to a channel.
    
    Args:
        channel_id: Slack channel ID
        user_id: Slack user ID
        
    Returns:
        True if successful or user already in channel
    """
    try:
        app.client.conversations_invite(
            channel=channel_id,
            users=user_id,
        )
        logger.info(f"Added user {user_id} to channel {channel_id}")
        return True
        
    except SlackApiError as e:
        if e.response.get("error") == "already_in_channel":
            logger.debug(f"User {user_id} already in channel {channel_id}")
            return True
        elif e.response.get("error") == "cant_invite_self":
            logger.debug(f"Bot cannot invite itself to channel {channel_id}")
            return True
        else:
            logger.error(f"Failed to add user to channel: {e}")
            return False


def join_channel(channel_id: str) -> bool:
    """Have the bot join a public channel.
    
    Args:
        channel_id: Slack channel ID
        
    Returns:
        True if successful or already in channel
    """
    try:
        app.client.conversations_join(channel=channel_id)
        return True
    except SlackApiError as e:
        if e.response.get("error") == "already_in_channel":
            return True
        logger.error(f"Failed to join channel: {e}")
        return False


def create_opportunity_channels(
    opportunity_slug: str,
    opportunity_name: str,
) -> dict[str, str]:
    """Create Slack channels for a factory opportunity.
    
    Creates:
    - {slug} - Main channel for the opportunity
    - {slug}-alerts - Automated notifications channel
    
    Adds the operator to all channels.
    
    Args:
        opportunity_slug: URL-safe slug for the opportunity
        opportunity_name: Human-readable opportunity name
        
    Returns:
        Dict mapping channel type to channel ID:
        {"main": "C...", "alerts": "C..."}
    """
    channels = {}
    operator_id = settings.operator_slack_user_id
    
    # Main opportunity channel (just the slug)
    main_channel_id = get_or_create_channel(
        name=opportunity_slug,
        description=f"🏭 {opportunity_name} - Factory Discussion",
    )
    if main_channel_id:
        channels["main"] = main_channel_id
        join_channel(main_channel_id)
        if operator_id:
            add_user_to_channel(main_channel_id, operator_id)
    
    # Alerts channel for automated notifications
    alerts_channel_id = get_or_create_channel(
        name=f"{opportunity_slug}-alerts",
        description=f"🔔 {opportunity_name} - Automated Alerts",
    )
    if alerts_channel_id:
        channels["alerts"] = alerts_channel_id
        join_channel(alerts_channel_id)
        if operator_id:
            add_user_to_channel(alerts_channel_id, operator_id)
    
    logger.info(f"Created opportunity channels for {opportunity_slug}: {channels}")
    
    return channels
