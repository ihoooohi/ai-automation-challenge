"""
End-to-end scenario tests.

Each scenario maps to a real stakeholder concern:
  - Creator Success: legitimate content should not be auto-rejected
  - Trust & Safety: harmful content should never silently pass
  - Input Guard:    blank/null input should be rejected before any AI call
"""
import pytest
from unittest.mock import AsyncMock

from moderation_service import ModerationService
from models import ModerationRequest, ViolationType
from tests.helpers import make_request, anthropic_response


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def service():
    return ModerationService(openai_key="mock-key", anthropic_key="mock-key")


@pytest.fixture
def service_anthropic_flags_violence(service, monkeypatch):
    monkeypatch.setattr(
        service.anthropic_client.messages, "create",
        AsyncMock(return_value=anthropic_response(False, 0.88, "violence", "Detected violence.")),
    )
    return service


@pytest.fixture
def service_anthropic_flags_hate(service, monkeypatch):
    monkeypatch.setattr(
        service.anthropic_client.messages, "create",
        AsyncMock(return_value=anthropic_response(False, 0.91, "hate_speech", "Detected hate speech.")),
    )
    return service


# ---------------------------------------------------------------------------
# Scenario 1: Creator Success — false positives go to human review, not auto-reject
# ---------------------------------------------------------------------------

class TestCreatorFalsePositiveScenarios:
    """
    OpenAI flags legitimate creator content due to keyword co-occurrence.
    Anthropic disagrees → content should be held for human review, never auto-rejected.
    """

    @pytest.mark.asyncio
    async def test_cooking_video_not_auto_rejected(self, service):
        """Cooking knife tutorial: OpenAI flags violence (0.72), Anthropic says safe."""
        result = await service.moderate_content(
            make_request("How to chop vegetables with a knife, kitchen recipe tutorial")
        )
        assert result.is_safe is False, "Should not approve when OpenAI flags"
        assert result.needs_human_review is True, "Should escalate to human, not auto-reject"
        assert result.violation_type == ViolationType.VIOLENCE

    @pytest.mark.asyncio
    async def test_cooking_video_reasoning_explains_disagreement(self, service):
        """Reasoning should name both providers and explain the conflict."""
        result = await service.moderate_content(
            make_request("How to chop vegetables with a knife, kitchen recipe tutorial")
        )
        assert "human review" in result.reasoning.lower()
        assert "openai" in result.reasoning.lower()
        assert "anthropic" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_fitness_video_not_auto_rejected(self, service):
        """Shirtless gym content: OpenAI flags adult (0.68), Anthropic says safe."""
        result = await service.moderate_content(
            make_request("Shirtless abs workout at the gym, fitness training video")
        )
        assert result.needs_human_review is True
        assert result.violation_type == ViolationType.ADULT_CONTENT

    @pytest.mark.asyncio
    async def test_medical_content_not_auto_rejected(self, service):
        """Medical procedure video: OpenAI flags violence (0.61), Anthropic says safe."""
        result = await service.moderate_content(
            make_request("Blood draw injection by a nurse, medical procedure tutorial")
        )
        assert result.needs_human_review is True

    @pytest.mark.asyncio
    async def test_clearly_safe_content_is_approved(self, service):
        """Generic travel vlog: both providers agree → approved immediately."""
        result = await service.moderate_content(
            make_request("A beautiful sunset over the mountains, travel vlog from Japan")
        )
        assert result.is_safe is True
        assert result.needs_human_review is False
        assert result.violation_type == ViolationType.NONE

    @pytest.mark.asyncio
    async def test_safe_reasoning_includes_scores(self, service):
        """Safe content reasoning should include numeric scores for observability."""
        result = await service.moderate_content(
            make_request("Morning yoga flow for beginners, relaxing stretch routine")
        )
        assert result.is_safe is True
        assert "%" in result.reasoning
        assert "no violation" in result.reasoning.lower()


# ---------------------------------------------------------------------------
# Scenario 2: Trust & Safety — harmful content is never silently passed
# ---------------------------------------------------------------------------

class TestHarmfulContentScenarios:
    """
    Clearly harmful content should be rejected outright (both providers agree).
    If only one provider catches it, the content goes to human review — never passes silently.
    """

    @pytest.mark.asyncio
    async def test_explicit_violence_is_rejected(self, service_anthropic_flags_violence):
        """Both providers flag explicit violence → auto-reject, no human review needed."""
        result = await service_anthropic_flags_violence.moderate_content(
            make_request("I will kill and destroy everyone in this building")
        )
        assert result.is_safe is False
        assert result.needs_human_review is False
        assert result.violation_type == ViolationType.VIOLENCE

    @pytest.mark.asyncio
    async def test_explicit_hate_speech_is_rejected(self, service_anthropic_flags_hate):
        """Both providers flag hate speech → auto-reject."""
        result = await service_anthropic_flags_hate.moderate_content(
            make_request("hate speech racist slur targeting ethnic group")
        )
        assert result.is_safe is False
        assert result.needs_human_review is False
        assert result.violation_type == ViolationType.HATE_SPEECH

    @pytest.mark.asyncio
    async def test_rejection_reasoning_names_violation_and_keywords(self, service_anthropic_flags_violence):
        """Rejection reasoning should identify the category and triggering keywords."""
        result = await service_anthropic_flags_violence.moderate_content(
            make_request("kill and destroy the target")
        )
        assert "violence" in result.reasoning.lower()
        assert "kill" in result.reasoning or "destroy" in result.reasoning

    @pytest.mark.asyncio
    async def test_subtle_harmful_content_caught_by_secondary_provider(
        self, service_anthropic_flags_hate
    ):
        """OpenAI misses coded hate speech (score 0.38); Anthropic catches it → human review."""
        result = await service_anthropic_flags_hate.moderate_content(
            make_request("those people you know who are always the problem")
        )
        assert result.is_safe is False
        assert result.needs_human_review is True, "Disagreement should escalate, not pass"

    @pytest.mark.asyncio
    async def test_severity_resolved_to_most_severe(self, service_anthropic_flags_hate):
        """OpenAI flags violence (0.95), Anthropic flags hate_speech (0.91) → hate_speech wins."""
        result = await service_anthropic_flags_hate.moderate_content(
            make_request("kill and destroy everyone you hate racist slur")
        )
        assert result.is_safe is False
        assert result.violation_type == ViolationType.HATE_SPEECH


# ---------------------------------------------------------------------------
# Scenario 3: Input Guard — blank input rejected before any AI call
# ---------------------------------------------------------------------------

class TestInputGuardScenarios:
    """
    Empty or whitespace-only content should never reach the AI providers.
    Layer 1 (Pydantic) catches it at request parsing; Layer 2 (service) is the safety net.
    """

    def test_pydantic_rejects_empty_string(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ModerationRequest(content="", creator_id="u1")

    def test_pydantic_rejects_whitespace_only(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ModerationRequest(content="   \t\n  ", creator_id="u1")

    def test_pydantic_strips_surrounding_whitespace(self):
        req = ModerationRequest(content="  valid content  ", creator_id="u1")
        assert req.content == "valid content"

    @pytest.mark.asyncio
    async def test_service_guard_rejects_bypassed_empty_content(self, service):
        """Simulate Pydantic bypass — service must still raise ValueError."""
        req = object.__new__(ModerationRequest)
        object.__setattr__(req, "content", "")
        object.__setattr__(req, "creator_id", "u1")
        object.__setattr__(req, "video_id", None)
        with pytest.raises(ValueError, match="empty or whitespace-only"):
            await service.moderate_content(req)

    @pytest.mark.asyncio
    async def test_service_guard_rejects_bypassed_whitespace_content(self, service):
        req = object.__new__(ModerationRequest)
        object.__setattr__(req, "content", "   ")
        object.__setattr__(req, "creator_id", "u1")
        object.__setattr__(req, "video_id", None)
        with pytest.raises(ValueError, match="empty or whitespace-only"):
            await service.moderate_content(req)

    @pytest.mark.asyncio
    async def test_valid_content_passes_both_layers(self, service):
        """Valid content clears both guards and returns a full ModerationResult."""
        req = ModerationRequest(content="A normal cooking channel video", creator_id="u1")
        result = await service.moderate_content(req)
        assert result.provider == "openai+anthropic"
        assert result.reasoning
        assert len(result.provider_results) == 2
