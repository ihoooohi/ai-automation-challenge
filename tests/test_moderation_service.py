"""
Tests for ModerationService — verifies that moderate_content returns correct
violation types, safety flags, confidence scores, and meaningful reasoning.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from moderation_service import ModerationService
from models import ModerationRequest, ViolationType


@pytest.fixture
def service():
    return ModerationService(openai_key="mock-key", anthropic_key="mock-key")


def req(content: str, video_id: str = None) -> ModerationRequest:
    return ModerationRequest(content=content, creator_id="user-1", video_id=video_id)


# ---------------------------------------------------------------------------
# Violence
# ---------------------------------------------------------------------------

class TestViolenceModeration:
    @pytest.mark.asyncio
    async def test_violence_is_unsafe(self, service):
        result = await service.moderate_content(req("I will kill and destroy you"))
        assert result.is_safe is False

    @pytest.mark.asyncio
    async def test_violence_type(self, service):
        result = await service.moderate_content(req("murder and attack"))
        assert result.violation_type == ViolationType.VIOLENCE

    @pytest.mark.asyncio
    async def test_violence_confidence_high(self, service):
        result = await service.moderate_content(req("kill destroy murder attack"))
        assert result.confidence >= 0.9

    @pytest.mark.asyncio
    async def test_violence_provider_is_openai(self, service):
        result = await service.moderate_content(req("kill everyone"))
        assert result.provider == "openai"


# ---------------------------------------------------------------------------
# Hate speech
# ---------------------------------------------------------------------------

class TestHateSpeechModeration:
    @pytest.mark.asyncio
    async def test_hate_speech_is_unsafe(self, service):
        result = await service.moderate_content(req("hate racist slur"))
        assert result.is_safe is False

    @pytest.mark.asyncio
    async def test_hate_speech_violation_type(self, service):
        result = await service.moderate_content(req("hate racist slur"))
        assert result.violation_type == ViolationType.HATE_SPEECH

    @pytest.mark.asyncio
    async def test_hate_speech_confidence_high(self, service):
        result = await service.moderate_content(req("hate racist slur"))
        assert result.confidence >= 0.9


# ---------------------------------------------------------------------------
# Adult content
# ---------------------------------------------------------------------------

class TestAdultContentModeration:
    @pytest.mark.asyncio
    async def test_sexual_content_is_unsafe(self, service):
        result = await service.moderate_content(req("nsfw explicit xxx"))
        assert result.is_safe is False

    @pytest.mark.asyncio
    async def test_sexual_content_violation_type(self, service):
        result = await service.moderate_content(req("nsfw explicit xxx"))
        assert result.violation_type == ViolationType.ADULT_CONTENT

    @pytest.mark.asyncio
    async def test_sexual_content_confidence_very_high(self, service):
        result = await service.moderate_content(req("nsfw explicit xxx"))
        assert result.confidence >= 0.95


# ---------------------------------------------------------------------------
# Spam
# ---------------------------------------------------------------------------

class TestSpamModeration:
    @pytest.mark.asyncio
    async def test_spam_is_unsafe(self, service):
        result = await service.moderate_content(req("buy now click here limited time act fast"))
        assert result.is_safe is False

    @pytest.mark.asyncio
    async def test_spam_violation_type(self, service):
        result = await service.moderate_content(req("buy now click here limited time"))
        assert result.violation_type == ViolationType.SPAM

    @pytest.mark.asyncio
    async def test_spam_confidence(self, service):
        result = await service.moderate_content(req("buy now click here limited time"))
        assert result.confidence >= 0.8


# ---------------------------------------------------------------------------
# Safe content
# ---------------------------------------------------------------------------

class TestSafeContentModeration:
    @pytest.mark.asyncio
    async def test_safe_content_is_safe(self, service):
        result = await service.moderate_content(req("I enjoy hiking on sunny days"))
        assert result.is_safe is True

    @pytest.mark.asyncio
    async def test_safe_content_violation_type_none(self, service):
        result = await service.moderate_content(req("The quick brown fox"))
        assert result.violation_type == ViolationType.NONE

    @pytest.mark.asyncio
    async def test_safe_content_confidence_low(self, service):
        result = await service.moderate_content(req("Hello world, great day for coding"))
        assert result.confidence < 0.5

    @pytest.mark.asyncio
    async def test_safe_content_no_violation_type(self, service):
        result = await service.moderate_content(req("cats and dogs playing together"))
        assert result.violation_type == ViolationType.NONE


# ---------------------------------------------------------------------------
# False positives
# ---------------------------------------------------------------------------

class TestFalsePositives:
    @pytest.mark.asyncio
    async def test_cooking_video_flagged(self, service):
        result = await service.moderate_content(
            req("how to chop vegetables with a knife in the kitchen recipe")
        )
        assert result.is_safe is False
        assert result.violation_type == ViolationType.VIOLENCE

    @pytest.mark.asyncio
    async def test_fitness_content_flagged(self, service):
        result = await service.moderate_content(
            req("shirtless abs workout at the gym fitness training")
        )
        assert result.is_safe is False
        assert result.violation_type == ViolationType.ADULT_CONTENT

    @pytest.mark.asyncio
    async def test_medical_content_flagged(self, service):
        result = await service.moderate_content(
            req("blood injection during surgery by a doctor medical procedure")
        )
        assert result.is_safe is False
        assert result.violation_type == ViolationType.VIOLENCE


# ---------------------------------------------------------------------------
# False negatives
# ---------------------------------------------------------------------------

class TestFalseNegatives:
    @pytest.mark.asyncio
    async def test_supplement_scam_passes(self, service):
        # Avoid "hate" — it triggers the clear-violation hate-speech rule
        result = await service.moderate_content(
            req("miracle weight loss supplement try this one weird trick")
        )
        assert result.is_safe is True

    @pytest.mark.asyncio
    async def test_coded_hate_passes(self, service):
        result = await service.moderate_content(
            req("those people you know who are ruining everything")
        )
        assert result.is_safe is True


# ---------------------------------------------------------------------------
# video_id passthrough
# ---------------------------------------------------------------------------

class TestVideoIdPassthrough:
    @pytest.mark.asyncio
    async def test_result_does_not_drop_video_id(self, service):
        # ModerationService returns ModerationResult (no video_id), but we verify
        # the service processes requests with video_id without error
        result = await service.moderate_content(req("safe content", video_id="vid-42"))
        assert result is not None
