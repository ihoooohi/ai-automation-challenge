import asyncio
from typing import Optional
from models import ModerationRequest, ModerationResult, ViolationType
from mock_clients import MockOpenAIClient, MockAnthropicClient


class ModerationService:
    """
    Content moderation service using OpenAI's moderation API.

    Current behavior:
    - Uses OpenAI moderation API
    - Returns binary safe/unsafe decision
    - Threshold is hardcoded
    """

    def __init__(self, openai_key: str, anthropic_key: str):
        self.openai_client = MockOpenAIClient(api_key=openai_key)
        self.anthropic_client = MockAnthropicClient(api_key=anthropic_key)
        self.confidence_threshold = 0.5  # Content flagged if any category > this

    async def moderate_content(self, request: ModerationRequest) -> ModerationResult:
        """Moderate content using OpenAI."""
        response = await self.openai_client.moderations.create(input=request.content)
        result = response.results[0]

        # Get the highest scoring category
        scores = result.category_scores
        categories = ["hate", "violence", "sexual", "spam"]
        max_category = max(categories, key=lambda k: getattr(scores, k))
        max_score = getattr(scores, max_category)

        # Map OpenAI category to our violation type
        violation_type = ViolationType.NONE
        category_map = {
            "hate": ViolationType.HATE_SPEECH,
            "violence": ViolationType.VIOLENCE,
            "sexual": ViolationType.ADULT_CONTENT,
            "spam": ViolationType.SPAM,
        }
        if result.flagged:
            violation_type = category_map.get(max_category, ViolationType.NONE)

        reasoning = self._build_reasoning(result, max_category, max_score)

        return ModerationResult(
            is_safe=not result.flagged,
            confidence=max_score,
            violation_type=violation_type,
            reasoning=reasoning,
            provider="openai"
        )

    def _build_reasoning(self, result, max_category: str, max_score: float) -> str:
        """Build human-readable reasoning from moderation result."""
        category_labels = {
            "hate": "hate speech",
            "violence": "violence",
            "sexual": "adult content",
            "spam": "spam",
        }
        label = category_labels.get(max_category, max_category)

        if result.flagged:
            keywords = getattr(result, "matched_keywords", {}).get(max_category, [])
            keyword_part = (
                f" Triggered by: {', '.join(repr(k) for k in keywords)}."
                if keywords else ""
            )
            return (
                f"Content flagged for {label} (score: {max_score:.0%}, "
                f"threshold: {self.confidence_threshold:.0%}).{keyword_part}"
            )
        else:
            all_scores = {
                cat: getattr(result.category_scores, cat)
                for cat in ["hate", "violence", "sexual", "spam"]
            }
            score_summary = ", ".join(
                f"{category_labels[c]}: {s:.0%}"
                for c, s in sorted(all_scores.items(), key=lambda x: -x[1])
            )
            return (
                f"No violations detected (all scores below threshold of "
                f"{self.confidence_threshold:.0%}). Scores: {score_summary}."
            )
