from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from enum import Enum

class ViolationType(str, Enum):
    HATE_SPEECH = "hate_speech"
    VIOLENCE = "violence"
    ADULT_CONTENT = "adult_content"
    SPAM = "spam"
    NONE = "none"

class ModerationRequest(BaseModel):
    """Request model for content moderation"""
    content: str = Field(..., min_length=1)
    creator_id: str
    video_id: Optional[str] = None

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("content must not be empty or whitespace-only")
        return v.strip()

class ModerationResult(BaseModel):
    """Structured AI moderation result"""
    is_safe: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    violation_type: ViolationType
    reasoning: str
    provider: str  # "openai" or "anthropic"

class ModerationResponse(BaseModel):
    """API response model"""
    video_id: Optional[str]
    moderation: ModerationResult
    processing_time_ms: float
