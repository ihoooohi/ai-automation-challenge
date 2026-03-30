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
        if result.flagged:
            category_map = {
                "hate": ViolationType.HATE_SPEECH,
                "violence": ViolationType.VIOLENCE,
                "sexual": ViolationType.ADULT_CONTENT,
                "spam": ViolationType.SPAM,
            }
            violation_type = category_map.get(max_category, ViolationType.NONE)

        return ModerationResult(
            is_safe=not result.flagged,
            confidence=max_score,
            violation_type=violation_type,
            reasoning="Automated moderation check",
            provider="openai"
        )
