"""
Tests for reasoning string content — verifies that the reasoning field
contains actionable, human-readable explanations with keywords and scores.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from moderation_service import ModerationService
from models import ModerationRequest


@pytest.fixture
def service():
    return ModerationService(openai_key="mock-key", anthropic_key="mock-key")


def req(content: str) -> ModerationRequest:
    return ModerationRequest(content=content, creator_id="user-1")


# ---------------------------------------------------------------------------
# Reasoning format for flagged content
# ---------------------------------------------------------------------------

class TestFlaggedReasoning:
    @pytest.mark.asyncio
    async def test_reasoning_not_placeholder(self, service):
        result = await service.moderate_content(req("kill and destroy"))
        assert result.reasoning != "Automated moderation check"

    @pytest.mark.asyncio
    async def test_reasoning_mentions_violation_category(self, service):
        result = await service.moderate_content(req("kill and destroy"))
        assert "violence" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_reasoning_includes_score(self, service):
        result = await service.moderate_content(req("kill and destroy"))
        assert "%" in result.reasoning

    @pytest.mark.asyncio
    async def test_reasoning_includes_threshold(self, service):
        result = await service.moderate_content(req("kill and destroy"))
        assert "threshold" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_reasoning_includes_triggering_keywords(self, service):
        result = await service.moderate_content(req("kill and destroy"))
        assert "kill" in result.reasoning or "destroy" in result.reasoning

    @pytest.mark.asyncio
    async def test_hate_reasoning_mentions_hate_category(self, service):
        result = await service.moderate_content(req("hate speech with racist slur"))
        assert "hate" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_hate_reasoning_includes_triggering_keywords(self, service):
        result = await service.moderate_content(req("hate speech with racist slur"))
        assert "hate" in result.reasoning or "racist" in result.reasoning or "slur" in result.reasoning

    @pytest.mark.asyncio
    async def test_spam_reasoning_mentions_spam_category(self, service):
        result = await service.moderate_content(req("buy now click here limited time"))
        assert "spam" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_spam_reasoning_includes_triggering_phrases(self, service):
        result = await service.moderate_content(req("buy now click here limited time"))
        assert any(phrase in result.reasoning for phrase in ["buy now", "click here", "limited time"])

    @pytest.mark.asyncio
    async def test_sexual_reasoning_mentions_adult_content(self, service):
        result = await service.moderate_content(req("nsfw explicit xxx"))
        assert "adult" in result.reasoning.lower() or "sexual" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_sexual_reasoning_includes_triggering_keywords(self, service):
        result = await service.moderate_content(req("nsfw explicit xxx"))
        assert any(w in result.reasoning for w in ["nsfw", "explicit", "xxx"])

    @pytest.mark.asyncio
    async def test_cooking_false_positive_reasoning_mentions_violence(self, service):
        result = await service.moderate_content(
            req("how to chop vegetables with a knife in the kitchen recipe")
        )
        assert "violence" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_cooking_false_positive_reasoning_includes_keywords(self, service):
        result = await service.moderate_content(
            req("how to chop vegetables with a knife in the kitchen recipe")
        )
        assert "chop" in result.reasoning or "knife" in result.reasoning


# ---------------------------------------------------------------------------
# Reasoning format for safe content
# ---------------------------------------------------------------------------

class TestSafeReasoning:
    @pytest.mark.asyncio
    async def test_safe_reasoning_not_placeholder(self, service):
        result = await service.moderate_content(req("I love coding"))
        assert result.reasoning != "Automated moderation check"

    @pytest.mark.asyncio
    async def test_safe_reasoning_says_no_violations(self, service):
        result = await service.moderate_content(req("I love coding"))
        assert "no violation" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_safe_reasoning_includes_threshold(self, service):
        result = await service.moderate_content(req("I love coding"))
        assert "threshold" in result.reasoning.lower() or "50%" in result.reasoning

    @pytest.mark.asyncio
    async def test_safe_reasoning_includes_all_scores(self, service):
        result = await service.moderate_content(req("I love coding"))
        # All four categories should appear in the score summary
        for category in ["hate", "violence", "spam", "adult"]:
            assert category in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_safe_reasoning_includes_percentages(self, service):
        result = await service.moderate_content(req("beautiful sunny day for a walk"))
        assert "%" in result.reasoning

    @pytest.mark.asyncio
    async def test_false_negative_reasoning_says_no_violations(self, service):
        # Supplement scam slips through — reasoning should reflect the score, not lie
        # Note: avoid "hate" — it triggers the clear-violation hate-speech rule
        result = await service.moderate_content(
            req("miracle weight loss supplement try this one weird trick")
        )
        assert "no violation" in result.reasoning.lower()


# ---------------------------------------------------------------------------
# Reasoning is a non-empty string
# ---------------------------------------------------------------------------

class TestReasoningIsAlwaysPresent:
    @pytest.mark.asyncio
    async def test_reasoning_never_empty(self, service):
        cases = [
            "kill destroy",
            "hate racist slur",
            "nsfw explicit xxx",
            "buy now click here",
            "safe content about hiking",
            "miracle weight loss supplement doctors hate",
        ]
        for text in cases:
            result = await service.moderate_content(req(text))
            assert result.reasoning, f"Empty reasoning for: {text!r}"
            assert len(result.reasoning) > 20, f"Reasoning too short for: {text!r}"
