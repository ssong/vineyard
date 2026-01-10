"""Miro API client for visual collaboration."""

import logging
from typing import Optional

import httpx

from src.config import settings
from src.utils import truncate_text, MiroLimits

logger = logging.getLogger(__name__)

MIRO_API_URL = "https://api.miro.com/v2"


def _get_headers() -> dict:
    """Get authorization headers."""
    return {
        "Authorization": f"Bearer {settings.miro_access_token}",
        "Content-Type": "application/json",
    }


def _make_request(
    method: str,
    endpoint: str,
    json_data: Optional[dict] = None,
) -> dict:
    """Make a request to Miro API."""
    if not settings.miro_access_token:
        logger.warning("MIRO_ACCESS_TOKEN not configured")
        return {"id": "mock-board", "viewLink": "https://miro.com/mock"}

    url = f"{MIRO_API_URL}{endpoint}"

    with httpx.Client(timeout=30.0) as client:
        if method == "GET":
            response = client.get(url, headers=_get_headers())
        elif method == "POST":
            response = client.post(url, headers=_get_headers(), json=json_data)
        elif method == "PATCH":
            response = client.patch(url, headers=_get_headers(), json=json_data)
        else:
            raise ValueError(f"Unsupported method: {method}")

        response.raise_for_status()
        return response.json()


def create_board(name: str, description: str = "") -> dict:
    """Create a new Miro board."""
    data = {
        "name": truncate_text(name, MiroLimits.BOARD_NAME),
        "description": truncate_text(description, MiroLimits.BOARD_DESCRIPTION),
    }

    result = _make_request("POST", "/boards", data)
    logger.info(f"Created Miro board: {result.get('id')}")
    return result


def create_frame(board_id: str, title: str, x: int = 0, y: int = 0) -> dict:
    """Create a frame on a board."""
    data = {
        "data": {"title": truncate_text(title, MiroLimits.FRAME_TITLE), "format": "custom"},
        "position": {"x": x, "y": y},
        "geometry": {"width": 800, "height": 600},
    }

    return _make_request("POST", f"/boards/{board_id}/frames", data)


def create_shape(
    board_id: str,
    content: str,
    shape_type: str = "rectangle",
    x: int = 0,
    y: int = 0,
    width: int = 200,
    height: int = 100,
    fill_color: str = "#ffffff",
) -> dict:
    """Create a shape on a board."""
    data = {
        "data": {"content": truncate_text(content, MiroLimits.SHAPE_CONTENT), "shape": shape_type},
        "position": {"x": x, "y": y},
        "geometry": {"width": width, "height": height},
        "style": {"fillColor": fill_color},
    }

    return _make_request("POST", f"/boards/{board_id}/shapes", data)


def create_sticky_note(
    board_id: str,
    content: str,
    x: int = 0,
    y: int = 0,
    color: str = "yellow",
) -> dict:
    """Create a sticky note on a board."""
    color_map = {
        "yellow": "#fff9b1",
        "green": "#c9df56",
        "blue": "#6cd8fa",
        "pink": "#f5a9b8",
        "orange": "#f5c27b",
    }

    data = {
        "data": {"content": truncate_text(content, MiroLimits.STICKY_NOTE_CONTENT), "shape": "square"},
        "position": {"x": x, "y": y},
        "style": {"fillColor": color_map.get(color, "#fff9b1")},
    }

    return _make_request("POST", f"/boards/{board_id}/sticky_notes", data)


def create_connector(
    board_id: str,
    start_item_id: str,
    end_item_id: str,
) -> dict:
    """Create a connector between two items."""
    data = {
        "startItem": {"id": start_item_id},
        "endItem": {"id": end_item_id},
    }

    return _make_request("POST", f"/boards/{board_id}/connectors", data)


def create_competitive_landscape(
    board_name: str,
    competitors: list[dict],
) -> str:
    """
    Create a competitive landscape visualization.

    Args:
        board_name: Name for the Miro board
        competitors: List of competitors with name, price_position, feature_score

    Returns:
        URL to the board
    """
    board = create_board(board_name, "Competitive Analysis")
    board_id = board.get("id", "mock-id")

    # Create frame
    create_frame(board_id, "Market Map", 0, 0)

    # Add axis labels
    create_shape(board_id, "Price →", "rectangle", 400, 650, 100, 30, "#f0f0f0")
    create_shape(board_id, "Features ↑", "rectangle", -50, 300, 100, 30, "#f0f0f0")

    # Plot competitors
    shapes = {}
    for i, comp in enumerate(competitors):
        x = int(comp.get("price_position", 50) * 6)  # Scale to 600px width
        y = int(600 - comp.get("feature_score", 50) * 6)  # Invert Y axis

        shape = create_shape(
            board_id,
            comp.get("name", f"Competitor {i}"),
            "rectangle",
            x,
            y,
            150,
            60,
            "#4f46e5" if comp.get("is_target") else "#e0e7ff",
        )
        shapes[comp.get("name")] = shape.get("id")

    return board.get("viewLink", f"https://miro.com/app/board/{board_id}")
