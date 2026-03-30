"""
Shared helper utilities for tests (importable as a regular module).
"""
import json
from unittest.mock import MagicMock

from models import ModerationRequest


def anthropic_response(is_safe: bool, confidence: float, violation_type: str, reasoning: str):
    """Build a mock Anthropic MockMessage-style object."""
    content = MagicMock()
    content.text = json.dumps({
        "is_safe": is_safe,
        "confidence": confidence,
        "violation_type": violation_type,
        "reasoning": reasoning,
    })
    msg = MagicMock()
    msg.content = [content]
    return msg


def make_request(content: str, creator_id: str = "user_test", video_id: str = None):
    return ModerationRequest(content=content, creator_id=creator_id, video_id=video_id)
