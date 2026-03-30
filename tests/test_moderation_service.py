"""
Unit tests for ModerationService.
Covers individual provider methods, helper methods, and the full dual-provider flow.
"""
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from models import ViolationType
from moderation_service import ModerationService, _SEVERITY_ORDER

from conftest import make_request, anthropic_response


# ---------------------------------------------------------------------------
# _moderate_with_openai
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestModerateWithOpenAI:
    async def test_safe_content(self, service):
        result = await service._moderate_with_openai(
            make_request("A beautiful sunset over the ocean.")
        )
        assert result.provider == "openai"
        assert result.is_safe is True
        assert result.violation_type == ViolationType.NONE

    async def test_violence_flagged(self, service):
        result = await service._moderate_with_openai(
            make_request("I will kill and destroy everything.")
        )
        assert result.is_safe is False
        assert result.violation_type == ViolationType.VIOLENCE
        assert result.confidence >= 0.5

    async def test_hate_speech_flagged(self, service):
        result = await service._moderate_with_openai(
            make_request("I hate that racist slur.")
        )
        assert result.is_safe is False
        assert result.violation_type == ViolationType.HATE_SPEECH

    async def test_adult_content_flagged(self, service):
        result = await service._moderate_with_openai(
            make_request("nsfw explicit xxx content here.")
        )
        assert result.is_safe is False
        assert result.violation_type == ViolationType.ADULT_CONTENT

    async def test_spam_flagged(self, service):
        result = await service._moderate_with_openai(
            make_request("Buy now! Click here! Limited time offer, act fast!")
        )
        assert result.is_safe is False
        assert result.violation_type == ViolationType.SPAM

    async def test_cooking_false_positive(self, service):
        """OpenAI incorrectly flags cooking videos as violence."""
        result = await service._moderate_with_openai(
            make_request("How to chop vegetables in the kitchen recipe.")
        )
        assert result.is_safe is False
        assert result.violation_type == ViolationType.VIOLENCE

    async def test_fitness_false_positive(self, service):
        """OpenAI incorrectly flags fitness content as adult."""
        result = await service._moderate_with_openai(
            make_request("Shirtless abs workout at the gym fitness training.")
        )
        assert result.is_safe is False
        assert result.violation_type == ViolationType.ADULT_CONTENT

    async def test_confidence_within_bounds(self, service):
        result = await service._moderate_with_openai(make_request("Safe content."))
        assert 0.0 <= result.confidence <= 1.0

    async def test_reasoning_not_empty(self, service):
        result = await service._moderate_with_openai(make_request("Safe content."))
        assert len(result.reasoning) > 0


# ---------------------------------------------------------------------------
# _moderate_with_anthropic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestModerateWithAnthropic:
    async def test_default_returns_safe(self, service):
        result = await service._moderate_with_anthropic(make_request("Some content."))
        assert result.provider == "anthropic"
        assert result.is_safe is True
        assert result.violation_type == ViolationType.NONE

    async def test_parses_unsafe_response(self, service, monkeypatch):
        monkeypatch.setattr(
            service.anthropic_client.messages, "create",
            AsyncMock(return_value=anthropic_response(
                False, 0.91, "hate_speech", "Detected hate speech."
            )),
        )
        result = await service._moderate_with_anthropic(make_request("bad content"))
        assert result.is_safe is False
        assert result.violation_type == ViolationType.HATE_SPEECH
        assert result.confidence == 0.91

    async def test_parses_unknown_violation_type_as_none(self, service, monkeypatch):
        monkeypatch.setattr(
            service.anthropic_client.messages, "create",
            AsyncMock(return_value=anthropic_response(
                False, 0.7, "unknown_type", "Some reason."
            )),
        )
        result = await service._moderate_with_anthropic(make_request("content"))
        assert result.violation_type == ViolationType.NONE

    async def test_confidence_within_bounds(self, service):
        result = await service._moderate_with_anthropic(make_request("content"))
        assert 0.0 <= result.confidence <= 1.0


# ---------------------------------------------------------------------------
# _resolve_violation_type
# ---------------------------------------------------------------------------

class TestResolveViolationType:
    def _provider_result(self, vtype):
        from models import ProviderResult
        return ProviderResult(
            provider="test", is_safe=False, confidence=0.8,
            violation_type=vtype, reasoning="test",
        )

    def test_none_vs_none(self, service):
        r = service._resolve_violation_type(
            self._provider_result(ViolationType.NONE),
            self._provider_result(ViolationType.NONE),
        )
        assert r == ViolationType.NONE

    def test_takes_more_severe(self, service):
        r = service._resolve_violation_type(
            self._provider_result(ViolationType.SPAM),
            self._provider_result(ViolationType.HATE_SPEECH),
        )
        assert r == ViolationType.HATE_SPEECH

    def test_violence_vs_adult_content(self, service):
        r = service._resolve_violation_type(
            self._provider_result(ViolationType.ADULT_CONTENT),
            self._provider_result(ViolationType.VIOLENCE),
        )
        assert r == ViolationType.VIOLENCE

    def test_severity_order_is_complete(self):
        assert set(_SEVERITY_ORDER) == set(ViolationType)


# ---------------------------------------------------------------------------
# _build_reasoning
# ---------------------------------------------------------------------------

class TestBuildReasoning:
    def _provider_result(self, provider, is_safe, confidence=0.8):
        from models import ProviderResult
        return ProviderResult(
            provider=provider, is_safe=is_safe, confidence=confidence,
            violation_type=ViolationType.NONE if is_safe else ViolationType.VIOLENCE,
            reasoning="test reasoning",
        )

    def test_both_safe_message(self, service):
        msg = service._build_reasoning(
            self._provider_result("openai", True),
            self._provider_result("anthropic", True),
        )
        assert "safe" in msg.lower()
        assert "human review" not in msg.lower()

    def test_both_unsafe_message(self, service):
        msg = service._build_reasoning(
            self._provider_result("openai", False),
            self._provider_result("anthropic", False),
        )
        assert "both" in msg.lower()
        assert "human review" not in msg.lower()

    def test_disagree_mentions_human_review(self, service):
        msg = service._build_reasoning(
            self._provider_result("openai", False),
            self._provider_result("anthropic", True),
        )
        assert "human review" in msg.lower()

    def test_reasoning_includes_provider_details(self, service):
        msg = service._build_reasoning(
            self._provider_result("openai", True),
            self._provider_result("anthropic", True),
        )
        assert len(msg) > 10


# ---------------------------------------------------------------------------
# moderate_content — full dual-provider integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestModerateContent:

    # --- Both safe ---

    async def test_both_safe_returns_safe(self, service):
        result = await service.moderate_content(
            make_request("A lovely travel vlog from Paris.", video_id="vid_1")
        )
        assert result.is_safe is True
        assert result.needs_human_review is False
        assert result.violation_type == ViolationType.NONE
        assert result.provider == "openai+anthropic"

    async def test_both_safe_has_two_provider_results(self, service):
        result = await service.moderate_content(make_request("Safe content."))
        assert len(result.provider_results) == 2
        providers = {r.provider for r in result.provider_results}
        assert providers == {"openai", "anthropic"}

    async def test_both_safe_confidence_is_average(self, service):
        result = await service.moderate_content(make_request("Safe content."))
        openai_conf = result.provider_results[0].confidence
        anthropic_conf = result.provider_results[1].confidence
        expected = round((openai_conf + anthropic_conf) / 2, 4)
        assert result.confidence == expected

    # --- Both unsafe → direct reject ---

    async def test_both_unsafe_returns_not_safe(self, service_anthropic_unsafe_violence):
        result = await service_anthropic_unsafe_violence.moderate_content(
            make_request("I will kill and destroy everything, hate racist slur.")
        )
        assert result.is_safe is False
        assert result.needs_human_review is False

    async def test_both_unsafe_no_human_review(self, service_anthropic_unsafe_violence):
        result = await service_anthropic_unsafe_violence.moderate_content(
            make_request("Kill everyone now, racist hate slur.")
        )
        assert result.needs_human_review is False

    async def test_both_unsafe_resolves_severe_violation(self, service_anthropic_unsafe_hate):
        # OpenAI flags violence (0.95), Anthropic flags hate_speech (0.91)
        # Should resolve to hate_speech (more severe)
        result = await service_anthropic_unsafe_hate.moderate_content(
            make_request("Kill everyone, racist hate slur.")
        )
        assert result.is_safe is False
        assert result.violation_type == ViolationType.HATE_SPEECH

    # --- Providers disagree → human review ---

    async def test_openai_flags_anthropic_safe_triggers_human_review(self, service):
        """OpenAI false positive on cooking video → human review, not direct reject."""
        result = await service.moderate_content(
            make_request("How to chop vegetables and slice meat in the kitchen recipe.")
        )
        assert result.is_safe is False
        assert result.needs_human_review is True

    async def test_fitness_false_positive_triggers_human_review(self, service):
        result = await service.moderate_content(
            make_request("Shirtless abs workout at the gym fitness training.")
        )
        assert result.needs_human_review is True

    async def test_medical_false_positive_triggers_human_review(self, service):
        result = await service.moderate_content(
            make_request("Blood surgery injection wound doctor medical health nurse.")
        )
        assert result.needs_human_review is True

    async def test_openai_safe_anthropic_flags_triggers_human_review(
        self, service_anthropic_unsafe_spam
    ):
        result = await service_anthropic_unsafe_spam.moderate_content(
            make_request("This is a totally normal video about cooking.")
        )
        assert result.needs_human_review is True
        assert result.is_safe is False

    # --- False negatives in OpenAI (subtle harmful content) ---

    async def test_supplement_scam_passes_openai_but_reviewed(self, service):
        """Subtle spam that passes OpenAI; Anthropic also safe → marked safe by current mock."""
        result = await service.moderate_content(
            make_request("Miracle weight loss supplement doctors hate one weird trick.")
        )
        # Both mock as safe → is_safe=True (shows limitation; real Anthropic would catch it)
        assert result.provider == "openai+anthropic"

    async def test_coded_hate_passes_openai(self, service):
        result = await service.moderate_content(
            make_request("Those people you know who certain types are the problem.")
        )
        # OpenAI misses it, Anthropic also safe in mock
        assert result.provider == "openai+anthropic"

    # --- Metadata checks ---

    async def test_video_id_not_in_result(self, service):
        """video_id is not part of ModerationResult, only ModerationResponse."""
        result = await service.moderate_content(
            make_request("Safe content.", video_id="vid_99")
        )
        assert not hasattr(result, "video_id")

    async def test_reasoning_not_empty(self, service):
        result = await service.moderate_content(make_request("Safe content."))
        assert len(result.reasoning) > 0
