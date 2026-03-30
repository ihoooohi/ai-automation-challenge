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

FastAPI content moderation service. Entry point is `main.py`, which initializes `ModerationService` and exposes two endpoints: `POST /moderate` and `GET /health`.

**Request flow:**
```
ModerationRequest
  → (input validation: Pydantic + service guard)
  → ModerationService.moderate_content()
  → [MockOpenAIClient, MockAnthropicClient] (parallel)
  → _resolve_violation_type() + _build_reasoning()
  → ModerationResult
  → ModerationResponse
```

**Key files:**
- `moderation_service.py` — dual-provider logic: calls OpenAI and Anthropic in parallel, resolves disagreements, builds transparent reasoning
- `mock_clients.py` — simulates OpenAI and Anthropic APIs with intentional false positives and false negatives (see below)
- `models.py` — Pydantic models: `ModerationRequest`, `ModerationResult`, `ModerationResponse`, `ProviderResult`, `ViolationType` enum
- `tests/` — pytest test suite; `tests/helpers.py` provides shared `make_request` / `anthropic_response` utilities

**Decision logic (`ModerationService.moderate_content`):**

| OpenAI | Anthropic | Result |
|---|---|---|
| safe | safe | `is_safe=True`, `needs_human_review=False` |
| unsafe | unsafe | `is_safe=False`, `needs_human_review=False` |
| safe | unsafe | `is_safe=False`, `needs_human_review=True` |
| unsafe | safe | `is_safe=False`, `needs_human_review=True` |

When both providers disagree, the content is held for human review rather than auto-rejected. Violation type is resolved to the more severe of the two providers' results.

## Features

### 1. Dual-provider moderation (`feature/moderation-mechanism`)

`ModerationService` now calls OpenAI and Anthropic **in parallel** via `asyncio.gather`. The response includes a `provider_results` list with each provider's individual decision.

New model: `ProviderResult` — holds `provider`, `is_safe`, `confidence`, `violation_type`, `reasoning` for one provider.

`ModerationResult` now includes:
- `needs_human_review: bool`
- `provider: str` — always `"openai+anthropic"`
- `provider_results: List[ProviderResult]`

### 2. Transparent reasoning (`feature/moderation-transparency`)

`_build_openai_reasoning()` produces actionable reasoning instead of generic placeholders:

- **Flagged:** `Content flagged for violence (score: 95%, threshold: 50%). Triggered by: 'kill', 'destroy'.`
- **Safe:** `No violations detected (all scores below threshold of 50%). Scores: spam: 3%, hate speech: 2%, violence: 1%, adult content: 1%.`

The combined `reasoning` field on `ModerationResult` surfaces per-provider details so operators can understand exactly why a decision was made.

### 3. Null/empty content guard (`feature/null-attack-prevention`)

Two-layer defense against blank input:

- **Layer 1 — Pydantic:** `ModerationRequest.content` has `min_length=1` and a `field_validator` that strips and rejects whitespace-only strings. Returns HTTP 422 before the request reaches the service.
- **Layer 2 — Service:** `moderate_content()` raises `ValueError("content must not be empty or whitespace-only")` as a safeguard against callers that bypass model validation.

Leading/trailing whitespace is stripped at the Pydantic layer so `"  hello  "` is stored as `"hello"`.

## Challenge Context

Three stakeholder requirements were addressed in this iteration:

1. **Creator Success (reduce false positives):** Cooking/fitness/medical content was incorrectly auto-rejected. Now, when OpenAI flags but Anthropic disagrees, content is routed to `needs_human_review=True` instead of auto-rejected — protecting legitimate creators.
2. **Trust & Safety (reduce false negatives):** Subtle violations that pass OpenAI are surfaced through the Anthropic secondary check and the `needs_human_review` escalation path.
3. **Engineering (observability):** The `reasoning` field now includes category scores, threshold values, and triggering keywords so moderators can audit every decision.

## rules

1. use `pip3` to test ranther than `pip`
