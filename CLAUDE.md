# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (auto-reloads on file changes)
uvicorn main:app --reload

# Health check
curl http://localhost:8000/health

# Test moderation endpoint
curl -X POST "http://localhost:8000/moderate" \
  -H "Content-Type: application/json" \
  -d '{"content": "Check out my cooking tutorial!", "creator_id": "chef123"}'
```

No test suite exists. No linter is configured.

## Architecture

This is a FastAPI content moderation service built as a challenge exercise. The entry point is `main.py`, which initializes `ModerationService` and exposes two endpoints: `POST /moderate` and `GET /health`.

**Request flow:** `ModerationRequest` → `ModerationService.moderate_content()` → `MockOpenAIClient` → `ModerationResult` → `ModerationResponse`

**Key files:**
- `moderation_service.py` — core logic; calls OpenAI moderation API, maps category scores to `ViolationType`, applies a hardcoded `confidence_threshold = 0.5`
- `mock_clients.py` — simulates OpenAI and Anthropic APIs with intentional false positives and false negatives (see below)
- `models.py` — Pydantic models: `ModerationRequest`, `ModerationResult`, `ModerationResponse`, `ViolationType` enum

**`MockAnthropicClient` exists but is not wired into `ModerationService`** — integrating it is the intended challenge.

## Challenge Context

This is a 15-minute Vizzy Labs engineering challenge. The service has three conflicting stakeholder requirements:

1. **Creator Success (reduce false positives):** Cooking/fitness/medical content is incorrectly flagged because keyword co-occurrence triggers scores above 0.5 (e.g., "knife" + "cook" → violence 0.72, "shirtless" + "workout" → adult 0.68)
2. **Trust & Safety (reduce false negatives):** Subtle violations score below the threshold and slip through (supplement scam spam 0.42, coded hate speech 0.38)
3. **Engineering (observability):** The `reasoning` field is generic and doesn't explain why a decision was made

The mock clients encode these failure modes deliberately — changing the threshold, adding secondary provider analysis (Anthropic), or adding context-aware logic are the expected solution directions.

## rules

1. use `pip3` to test ranther than `pip`
