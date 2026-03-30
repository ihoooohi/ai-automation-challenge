# Content Moderation Service

A FastAPI-based dual-provider content moderation service that calls both OpenAI and Anthropic in parallel for safety detection.

## Background

The original system had the following issues:

| Issue | Description |
|-------|-------------|
| **High False Positives** | Cooking videos flagged as violence (chop/knife), fitness videos flagged as adult content |
| **False Negatives Risk** | Hidden spam ads and borderline hate speech slipped through |
| **Lack of Transparency** | Moderation decisions couldn't be explained to legal team |

## Key Transformations

### 1. Dual-Provider Parallel Moderation

`ModerationService` now calls both OpenAI and Anthropic in parallel using `asyncio.gather`:

```
OpenAI  ─┐
         ├─→ Decision Logic ─→ ModerationResult
Anthropic─┘
```

**Decision Matrix:**

| OpenAI | Anthropic | Result |
|--------|-----------|--------|
| safe | safe | `is_safe=True`, `needs_human_review=False` |
| unsafe | unsafe | `is_safe=False`, `needs_human_review=False` |
| safe | unsafe | `is_safe=False`, `needs_human_review=True` |
| unsafe | safe | `is_safe=False`, `needs_human_review=True` |

When providers disagree, content is flagged for human review instead of auto-rejection, protecting legitimate creators.

### 2. Transparent Reasoning

Before: `"Automated moderation check"` (meaningless)

Now:
```
Content flagged for violence (score: 95%, threshold: 50%). Triggered by: 'kill', 'destroy'.

No violations detected (all scores below threshold of 50%). Scores: spam: 3%, hate speech: 2%, violence: 1%, adult content: 1%.
```

Response includes each provider's individual decision and reasoning for auditability.

### 3. Null/Empty Content Guard

**Two-layer defense:**

- **Pydantic Layer**: `content` field has `min_length=1` + `field_validator` rejects whitespace-only strings, returns HTTP 422
- **Service Layer**: `moderate_content()` checks again and raises `ValueError` to prevent bypass

### 4. ProviderResult Model

Each provider returns independent results:

```python
{
    "provider": "openai",           # or "anthropic"
    "is_safe": false,
    "confidence": 0.95,
    "violation_type": "violence",
    "reasoning": "Content flagged for violence..."
}
```

Final response includes `provider_results` list with both providers' analysis.

## Quick Start

### 1. Install Dependencies

```bash
cd ai-automation-challenge
pip3 install -r requirements.txt
```

### 2. Start Service

```bash
uvicorn main:app --reload
```

Service runs at `http://localhost:8000`

### 3. Health Check

```bash
curl http://localhost:8000/health
```

### 4. Test Moderation Endpoint

```bash
curl -X POST "http://localhost:8000/moderate" \
  -H "Content-Type: application/json" \
  -d '{"content": "Check out my cooking tutorial!", "creator_id": "chef123"}'
```

**Example Response (safe content):**

```json
{
  "video_id": null,
  "moderation": {
    "is_safe": true,
    "needs_human_review": false,
    "confidence": 0.785,
    "violation_type": "none",
    "reasoning": "Both OpenAI and Anthropic consider this content safe. No violations detected...",
    "provider": "openai+anthropic",
    "provider_results": [
      {
        "provider": "openai",
        "is_safe": true,
        "confidence": 0.72,
        "violation_type": "none",
        "reasoning": "No violations detected..."
      },
      {
        "provider": "anthropic",
        "is_safe": true,
        "confidence": 0.85,
        "violation_type": "none",
        "reasoning": "Content appears to be within community guidelines."
      }
    ]
  },
  "processing_time_ms": 15.34
}
```

**Example Response (provider disagreement - human review required):**

```bash
curl -X POST "http://localhost:8000/moderate" \
  -H "Content-Type: application/json" \
  -d '{"content": "Knife skills: cut vegetable", "creator_id": "chef123"}'
```

```json
{
  "video_id": null,
  "moderation": {
    "is_safe": false,
    "needs_human_review": true,
    "confidence": 0.9,
    "violation_type": "violence",
    "reasoning": "Providers disagree — human review required. OpenAI (unsafe, confidence 0.95): Content flagged for violence (score: 95%, threshold: 50%). Triggered by: 'kill'. Anthropic (safe, confidence 0.85): Content appears to be within community guidelines.",
    "provider": "openai+anthropic",
    "provider_results": [
      {
        "provider": "openai",
        "is_safe": false,
        "confidence": 0.95,
        "violation_type": "violence",
        "reasoning": "Content flagged for violence (score: 95%, threshold: 50%). Triggered by: 'kill'."
      },
      {
        "provider": "anthropic",
        "is_safe": true,
        "confidence": 0.85,
        "violation_type": "none",
        "reasoning": "Content appears to be within community guidelines."
      }
    ]
  },
  "processing_time_ms": 1.39
}
```

In this case, OpenAI flagged "knife skills" as violence (false positive), while Anthropic correctly identified it as safe cooking content. The system routes this to human review instead of auto-rejecting the creator's content.

## Project Structure

```
ai-automation-challenge/
├── main.py                  # FastAPI entry point, /moderate and /health endpoints
├── moderation_service.py    # Core moderation logic: dual-provider parallel calls, decision aggregation
├── models.py                # Pydantic data models
├── mock_clients.py          # Mock OpenAI/Anthropic APIs (includes false positive/negative scenarios)
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

## Mock Client Behavior

`mock_clients.py` simulates real-world moderation challenges:

**False Positives:**
- `chop, knife, slice` + `cook, recipe` → violence
- `shirtless, abs, workout` + `fitness, gym` → adult_content
- `blood, surgery` + `medical, doctor` → violence

**False Negatives:**
- `miracle, doctors hate` + `weight loss, supplement` → passes (spam 0.42 < 0.5)
- `those people, you know who` → passes (hate 0.38 < 0.5)

This tests how the dual-provider system catches these issues through cross-validation.
