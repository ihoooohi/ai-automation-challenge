<div align="center">

# AI Automation Challenge - Content Moderation Service

[![License](https://img.shields.io/badge/License-Unspecified-lightgrey.svg)]()
[![Python](https://img.shields.io/badge/python-3.10+-00ADD8.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-009688.svg)](https://fastapi.tiangolo.com/)

[**English**](./README.md) | [**中文**](./README_CN.md)

</div>

---

## Overview

A FastAPI-based dual-provider content moderation service that calls both OpenAI and Anthropic in parallel for safety detection. When providers disagree, content is routed to human review instead of auto-rejection, protecting legitimate creators while maintaining safety.

## Problems Solved

| Problem | Solution |
|---------|----------|
| **High False Positives** | Dual-provider with human review: cooking/fitness content no longer auto-rejected |
| **False Negatives Risk** | Cross-validation catches subtle violations that single providers miss |
| **Lack of Transparency** | Detailed reasoning with scores, thresholds, and triggering keywords |

## Key Features

### 1. Dual-Provider Parallel Moderation

Calls OpenAI and Anthropic in parallel via `asyncio.gather`. When providers disagree, content goes to human review.

**Decision Matrix:**

| OpenAI | Anthropic | Result |
|--------|-----------|--------|
| safe | safe | Auto-approve |
| unsafe | unsafe | Auto-reject |
| safe | unsafe | Human review |
| unsafe | safe | Human review |

### 2. Transparent Reasoning

Before: `"Automated moderation check"` (useless)

After:
```
Content flagged for violence (score: 95%, threshold: 50%). Triggered by: 'kill', 'destroy'.

No violations detected (all scores below threshold of 50%). Scores: spam: 3%, hate speech: 2%, violence: 1%, adult content: 1%.
```

### 3. Null/Empty Content Guard

Two-layer defense: Pydantic validation (HTTP 422) + Service layer guard (ValueError).

## Quick Start

```bash
# Install dependencies
pip3 install -r requirements.txt

# Start service
uvicorn main:app --reload

# Health check
curl http://localhost:8000/health

# Test moderation
curl -X POST "http://localhost:8000/moderate" \
  -H "Content-Type: application/json" \
  -d '{"content": "Knife skills: cut vegetable", "creator_id": "chef123"}'
```

**Example Response (safe content):**

```json
{
  "moderation": {
    "is_safe": true,
    "needs_human_review": false,
    "confidence": 0.785,
    "violation_type": "none",
    "reasoning": "Both OpenAI and Anthropic consider this content safe. No violations detected...",
    "provider": "openai+anthropic",
    "provider_results": [
      {"provider": "openai", "is_safe": true, "confidence": 0.72, "violation_type": "none", "reasoning": "No violations detected..."},
      {"provider": "anthropic", "is_safe": true, "confidence": 0.85, "violation_type": "none", "reasoning": "Content appears to be within community guidelines."}
    ]
  },
  "processing_time_ms": 15.34
}
```

**Example Response (provider disagreement - human review required):**

```json
{
  "moderation": {
    "is_safe": false,
    "needs_human_review": true,
    "confidence": 0.9,
    "violation_type": "violence",
    "reasoning": "Providers disagree — human review required. OpenAI (unsafe, confidence 0.95): Content flagged for violence. Anthropic (safe, confidence 0.85): Content appears to be within community guidelines.",
    "provider": "openai+anthropic",
    "provider_results": [
      {"provider": "openai", "is_safe": false, "confidence": 0.95, "violation_type": "violence", "reasoning": "..."},
      {"provider": "anthropic", "is_safe": true, "confidence": 0.85, "violation_type": "none", "reasoning": "..."}
    ]
  },
  "processing_time_ms": 1.39
}
```

## Project Structure

```
ai-automation-challenge/
├── main.py                  # FastAPI entry point
├── moderation_service.py    # Dual-provider logic
├── models.py                # Pydantic models
├── mock_clients.py          # Mock APIs with false positives/negatives
├── requirements.txt
└── tests/                   # pytest test suite
```

## Violation Types

| Type | Description |
|------|-------------|
| `hate_speech` | Hate speech |
| `violence` | Violent content |
| `adult_content` | Adult content |
| `spam` | Spam |
| `none` | No violation |

## Architecture

```
ModerationRequest
  → Pydantic validation
  → ModerationService.moderate_content()
  → asyncio.gather([OpenAI, Anthropic])
  → _resolve_violation_type() + _build_reasoning()
  → ModerationResult
  → ModerationResponse
```

## Mock Client Behavior

The mock clients simulate real-world challenges:

**False Positives (legitimate content incorrectly flagged):**
- `chop, knife, slice` + `cook, recipe` → violence
- `shirtless, abs, workout` + `fitness, gym` → adult_content
- `blood, surgery` + `medical, doctor` → violence

**False Negatives (harmful content that passes):**
- `miracle, doctors hate` + `weight loss, supplement` → passes (spam 0.42 < 0.5)
- `those people, you know who` → passes (hate 0.38 < 0.5)

## License

Unspecified
