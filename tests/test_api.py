"""
Integration tests for FastAPI endpoints.
Uses httpx AsyncClient wired to the ASGI app.
"""
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock

from conftest import anthropic_response


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_returns_200(self, async_client):
        response = await async_client.get("/health")
        assert response.status_code == 200

    async def test_returns_healthy(self, async_client):
        response = await async_client.get("/health")
        assert response.json() == {"status": "healthy"}


# ---------------------------------------------------------------------------
# POST /moderate — response structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestModerateResponseStructure:
    async def test_returns_200(self, async_client):
        response = await async_client.post(
            "/moderate",
            json={"content": "A beautiful travel vlog.", "creator_id": "u1"},
        )
        assert response.status_code == 200

    async def test_top_level_fields_present(self, async_client):
        response = await async_client.post(
            "/moderate",
            json={"content": "Safe content.", "creator_id": "u1", "video_id": "vid_1"},
        )
        body = response.json()
        assert "video_id" in body
        assert "moderation" in body
        assert "processing_time_ms" in body

    async def test_video_id_echoed(self, async_client):
        response = await async_client.post(
            "/moderate",
            json={"content": "Safe content.", "creator_id": "u1", "video_id": "vid_42"},
        )
        assert response.json()["video_id"] == "vid_42"

    async def test_video_id_optional(self, async_client):
        response = await async_client.post(
            "/moderate",
            json={"content": "Safe content.", "creator_id": "u1"},
        )
        assert response.json()["video_id"] is None

    async def test_moderation_fields_present(self, async_client):
        response = await async_client.post(
            "/moderate",
            json={"content": "Safe content.", "creator_id": "u1"},
        )
        mod = response.json()["moderation"]
        for field in [
            "is_safe", "needs_human_review", "confidence",
            "violation_type", "reasoning", "provider", "provider_results",
        ]:
            assert field in mod, f"Missing field: {field}"

    async def test_provider_results_has_two_entries(self, async_client):
        response = await async_client.post(
            "/moderate",
            json={"content": "Safe content.", "creator_id": "u1"},
        )
        provider_results = response.json()["moderation"]["provider_results"]
        assert len(provider_results) == 2

    async def test_provider_results_contains_openai_and_anthropic(self, async_client):
        response = await async_client.post(
            "/moderate",
            json={"content": "Safe content.", "creator_id": "u1"},
        )
        providers = {r["provider"] for r in response.json()["moderation"]["provider_results"]}
        assert providers == {"openai", "anthropic"}

    async def test_provider_field_is_dual(self, async_client):
        response = await async_client.post(
            "/moderate",
            json={"content": "Safe content.", "creator_id": "u1"},
        )
        assert response.json()["moderation"]["provider"] == "openai+anthropic"

    async def test_processing_time_is_positive(self, async_client):
        response = await async_client.post(
            "/moderate",
            json={"content": "Safe content.", "creator_id": "u1"},
        )
        assert response.json()["processing_time_ms"] > 0


# ---------------------------------------------------------------------------
# POST /moderate — decision outcomes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestModerateDecisions:
    async def test_safe_content_is_approved(self, async_client):
        response = await async_client.post(
            "/moderate",
            json={"content": "A lovely recipe tutorial.", "creator_id": "chef"},
        )
        mod = response.json()["moderation"]
        # Anthropic (mock) is always safe; OpenAI is safe → both safe
        assert mod["is_safe"] is True
        assert mod["needs_human_review"] is False

    async def test_obvious_violation_triggers_human_review(self, async_client):
        """OpenAI flags violent content; mock Anthropic says safe → disagree → human review."""
        response = await async_client.post(
            "/moderate",
            json={"content": "I will kill and destroy everything.", "creator_id": "u2"},
        )
        mod = response.json()["moderation"]
        assert mod["is_safe"] is False
        assert mod["needs_human_review"] is True

    async def test_cooking_false_positive_goes_to_human_review(self, async_client):
        response = await async_client.post(
            "/moderate",
            json={
                "content": "How to chop vegetables and slice meat in the kitchen recipe.",
                "creator_id": "chef99",
                "video_id": "cooking_vid",
            },
        )
        mod = response.json()["moderation"]
        assert mod["needs_human_review"] is True
        assert mod["is_safe"] is False

    async def test_fitness_false_positive_goes_to_human_review(self, async_client):
        response = await async_client.post(
            "/moderate",
            json={
                "content": "Shirtless abs workout at the gym fitness training.",
                "creator_id": "fitguy",
            },
        )
        mod = response.json()["moderation"]
        assert mod["needs_human_review"] is True

    async def test_medical_content_goes_to_human_review(self, async_client):
        response = await async_client.post(
            "/moderate",
            json={
                "content": "Blood surgery injection wound doctor medical nurse.",
                "creator_id": "doc1",
            },
        )
        mod = response.json()["moderation"]
        assert mod["needs_human_review"] is True

    async def test_violation_type_none_when_safe(self, async_client):
        response = await async_client.post(
            "/moderate",
            json={"content": "Just a normal travel video.", "creator_id": "traveler"},
        )
        assert response.json()["moderation"]["violation_type"] == "none"

    async def test_confidence_between_0_and_1(self, async_client):
        response = await async_client.post(
            "/moderate",
            json={"content": "Any content here.", "creator_id": "u1"},
        )
        confidence = response.json()["moderation"]["confidence"]
        assert 0.0 <= confidence <= 1.0


# ---------------------------------------------------------------------------
# POST /moderate — invalid requests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestModerateValidation:
    async def test_missing_content_returns_422(self, async_client):
        response = await async_client.post(
            "/moderate",
            json={"creator_id": "u1"},
        )
        assert response.status_code == 422

    async def test_empty_content_returns_422(self, async_client):
        response = await async_client.post(
            "/moderate",
            json={"content": "", "creator_id": "u1"},
        )
        assert response.status_code == 422

    async def test_missing_creator_id_returns_422(self, async_client):
        response = await async_client.post(
            "/moderate",
            json={"content": "Some content."},
        )
        assert response.status_code == 422

    async def test_empty_body_returns_422(self, async_client):
        response = await async_client.post("/moderate", json={})
        assert response.status_code == 422

    async def test_non_json_body_returns_422(self, async_client):
        response = await async_client.post(
            "/moderate",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422
