"""
Shared fixtures and helpers for all test modules.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from httpx import AsyncClient, ASGITransport

from moderation_service import ModerationService
from tests.helpers import anthropic_response, make_request


# ---------------------------------------------------------------------------
# Pytest-asyncio config
# ---------------------------------------------------------------------------

pytest_plugins = ("pytest_asyncio",)


# ---------------------------------------------------------------------------
# Pre-built Anthropic mock responses
# ---------------------------------------------------------------------------

ANTHROPIC_SAFE = anthropic_response(True, 0.85, "none", "Content appears safe.")
ANTHROPIC_HATE = anthropic_response(False, 0.91, "hate_speech", "Anthropic detected hate speech.")
ANTHROPIC_VIOLENCE = anthropic_response(False, 0.88, "violence", "Anthropic detected violence.")
ANTHROPIC_ADULT = anthropic_response(False, 0.82, "adult_content", "Anthropic detected adult content.")
ANTHROPIC_SPAM = anthropic_response(False, 0.79, "spam", "Anthropic detected spam.")


# ---------------------------------------------------------------------------
# Service fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def service():
    """ModerationService with real mock clients (Anthropic always safe)."""
    return ModerationService(openai_key="mock-key", anthropic_key="mock-key")


@pytest.fixture
def service_anthropic_unsafe_violence(service, monkeypatch):
    """ModerationService where Anthropic returns violence."""
    monkeypatch.setattr(
        service.anthropic_client.messages, "create",
        AsyncMock(return_value=ANTHROPIC_VIOLENCE),
    )
    return service


@pytest.fixture
def service_anthropic_unsafe_hate(service, monkeypatch):
    """ModerationService where Anthropic returns hate_speech."""
    monkeypatch.setattr(
        service.anthropic_client.messages, "create",
        AsyncMock(return_value=ANTHROPIC_HATE),
    )
    return service


@pytest.fixture
def service_anthropic_unsafe_spam(service, monkeypatch):
    """ModerationService where Anthropic returns spam."""
    monkeypatch.setattr(
        service.anthropic_client.messages, "create",
        AsyncMock(return_value=ANTHROPIC_SPAM),
    )
    return service


@pytest.fixture
def service_anthropic_unsafe_adult(service, monkeypatch):
    """ModerationService where Anthropic returns adult_content."""
    monkeypatch.setattr(
        service.anthropic_client.messages, "create",
        AsyncMock(return_value=ANTHROPIC_ADULT),
    )
    return service


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def async_client():
    """Async HTTP client wired to the FastAPI app.

    Directly initializes _service to bypass lifespan, which is not triggered
    by ASGITransport in httpx 0.23+.
    """
    import main
    main._service = ModerationService(openai_key="mock-key", anthropic_key="mock-key")
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        yield client
