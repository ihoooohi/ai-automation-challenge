"""
Unit tests for Pydantic data models.
Covers field validation, enum values, and model construction.
"""
import pytest
from pydantic import ValidationError

from models import (
    ViolationType,
    ModerationRequest,
    ProviderResult,
    ModerationResult,
    ModerationResponse,
)


# ---------------------------------------------------------------------------
# ViolationType
# ---------------------------------------------------------------------------

class TestViolationType:
    def test_all_values_exist(self):
        values = {v.value for v in ViolationType}
        assert values == {"hate_speech", "violence", "adult_content", "spam", "none"}

    def test_string_coercion(self):
        assert ViolationType("none") == ViolationType.NONE
        assert ViolationType("violence") == ViolationType.VIOLENCE


# ---------------------------------------------------------------------------
# ModerationRequest
# ---------------------------------------------------------------------------

class TestModerationRequest:
    def test_valid_minimal(self):
        req = ModerationRequest(content="hello world", creator_id="u1")
        assert req.video_id is None

    def test_valid_with_video_id(self):
        req = ModerationRequest(content="hello", creator_id="u1", video_id="vid_42")
        assert req.video_id == "vid_42"

    def test_empty_content_rejected(self):
        with pytest.raises(ValidationError):
            ModerationRequest(content="", creator_id="u1")

    def test_missing_creator_id_rejected(self):
        with pytest.raises(ValidationError):
            ModerationRequest(content="hello")


# ---------------------------------------------------------------------------
# ProviderResult
# ---------------------------------------------------------------------------

class TestProviderResult:
    def _valid(self, **overrides):
        base = dict(
            provider="openai",
            is_safe=True,
            confidence=0.9,
            violation_type=ViolationType.NONE,
            reasoning="All good.",
        )
        base.update(overrides)
        return ProviderResult(**base)

    def test_valid_safe(self):
        r = self._valid()
        assert r.provider == "openai"
        assert r.is_safe is True

    def test_valid_unsafe(self):
        r = self._valid(is_safe=False, confidence=0.92, violation_type=ViolationType.VIOLENCE)
        assert r.violation_type == ViolationType.VIOLENCE

    def test_confidence_upper_bound(self):
        with pytest.raises(ValidationError):
            self._valid(confidence=1.1)

    def test_confidence_lower_bound(self):
        with pytest.raises(ValidationError):
            self._valid(confidence=-0.1)

    def test_confidence_boundary_values(self):
        self._valid(confidence=0.0)
        self._valid(confidence=1.0)


# ---------------------------------------------------------------------------
# ModerationResult
# ---------------------------------------------------------------------------

class TestModerationResult:
    def _provider_result(self, provider, is_safe, confidence, vtype):
        return ProviderResult(
            provider=provider,
            is_safe=is_safe,
            confidence=confidence,
            violation_type=vtype,
            reasoning="test",
        )

    def _valid(self, **overrides):
        openai_r = self._provider_result("openai", True, 0.1, ViolationType.NONE)
        anthropic_r = self._provider_result("anthropic", True, 0.85, ViolationType.NONE)
        base = dict(
            is_safe=True,
            needs_human_review=False,
            confidence=0.47,
            violation_type=ViolationType.NONE,
            reasoning="Both safe.",
            provider="openai+anthropic",
            provider_results=[openai_r, anthropic_r],
        )
        base.update(overrides)
        return ModerationResult(**base)

    def test_both_safe(self):
        r = self._valid()
        assert r.is_safe is True
        assert r.needs_human_review is False

    def test_human_review_flag(self):
        r = self._valid(is_safe=False, needs_human_review=True)
        assert r.needs_human_review is True

    def test_provider_results_length(self):
        r = self._valid()
        assert len(r.provider_results) == 2

    def test_provider_field(self):
        r = self._valid()
        assert r.provider == "openai+anthropic"

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            self._valid(confidence=1.5)


# ---------------------------------------------------------------------------
# ModerationResponse
# ---------------------------------------------------------------------------

class TestModerationResponse:
    def _build(self, video_id=None):
        openai_r = ProviderResult(
            provider="openai", is_safe=True, confidence=0.1,
            violation_type=ViolationType.NONE, reasoning="ok",
        )
        anthropic_r = ProviderResult(
            provider="anthropic", is_safe=True, confidence=0.85,
            violation_type=ViolationType.NONE, reasoning="ok",
        )
        mod = ModerationResult(
            is_safe=True, needs_human_review=False, confidence=0.47,
            violation_type=ViolationType.NONE, reasoning="Both safe.",
            provider="openai+anthropic", provider_results=[openai_r, anthropic_r],
        )
        return ModerationResponse(video_id=video_id, moderation=mod, processing_time_ms=12.5)

    def test_with_video_id(self):
        r = self._build(video_id="vid_1")
        assert r.video_id == "vid_1"

    def test_without_video_id(self):
        r = self._build()
        assert r.video_id is None

    def test_processing_time(self):
        r = self._build()
        assert r.processing_time_ms == 12.5
