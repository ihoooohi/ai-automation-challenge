import asyncio
import json
from typing import Optional
from models import ModerationRequest, ModerationResult, ProviderResult, ViolationType
from mock_clients import MockOpenAIClient, MockAnthropicClient


# Severity order for resolving conflicting violation types (ascending)
_SEVERITY_ORDER = [
    ViolationType.NONE,
    ViolationType.SPAM,
    ViolationType.ADULT_CONTENT,
    ViolationType.VIOLENCE,
    ViolationType.HATE_SPEECH,
]


class ModerationService:
    """
    Content moderation service using both OpenAI and Anthropic.

    Decision logic:
    - Both safe    → is_safe=True
    - Both unsafe  → is_safe=False
    - Disagree     → needs_human_review=True
    """

    def __init__(self, openai_key: str, anthropic_key: str):
        self.openai_client = MockOpenAIClient(api_key=openai_key)
        self.anthropic_client = MockAnthropicClient(api_key=anthropic_key)
        self.confidence_threshold = 0.5

    async def _moderate_with_openai(self, request: ModerationRequest) -> ProviderResult:
        """Call OpenAI moderation API and return a ProviderResult."""
        response = await self.openai_client.moderations.create(input=request.content)
        result = response.results[0]

        scores = result.category_scores
        categories = ["hate", "violence", "sexual", "spam"]
        max_category = max(categories, key=lambda k: getattr(scores, k))
        max_score = getattr(scores, max_category)

        violation_type = ViolationType.NONE
        if result.flagged:
            category_map = {
                "hate": ViolationType.HATE_SPEECH,
                "violence": ViolationType.VIOLENCE,
                "sexual": ViolationType.ADULT_CONTENT,
                "spam": ViolationType.SPAM,
            }
            violation_type = category_map.get(max_category, ViolationType.NONE)

        return ProviderResult(
            provider="openai",
            is_safe=not result.flagged,
            confidence=max_score,
            violation_type=violation_type,
            reasoning=f"OpenAI flagged category '{max_category}' with score {max_score:.2f}."
                      if result.flagged else "No violations detected.",
        )

    async def _moderate_with_anthropic(self, request: ModerationRequest) -> ProviderResult:
        """Call Anthropic moderation API and return a ProviderResult."""
        response = await self.anthropic_client.messages.create(
            model="claude-opus-4-6",
            max_tokens=256,
            messages=[{"role": "user", "content": request.content}],
        )
        data = json.loads(response.content[0].text)

        violation_str = data.get("violation_type", "none")
        try:
            violation_type = ViolationType(violation_str)
        except ValueError:
            violation_type = ViolationType.NONE

        return ProviderResult(
            provider="anthropic",
            is_safe=data.get("is_safe", True),
            confidence=data.get("confidence", 0.5),
            violation_type=violation_type,
            reasoning=data.get("reasoning", "No reasoning provided."),
        )

    def _resolve_violation_type(
        self, openai_result: ProviderResult, anthropic_result: ProviderResult
    ) -> ViolationType:
        """Return the more severe violation type between the two providers."""
        openai_idx = _SEVERITY_ORDER.index(openai_result.violation_type)
        anthropic_idx = _SEVERITY_ORDER.index(anthropic_result.violation_type)
        return _SEVERITY_ORDER[max(openai_idx, anthropic_idx)]

    def _build_reasoning(
        self, openai_result: ProviderResult, anthropic_result: ProviderResult
    ) -> str:
        """Build a human-readable summary of the two providers' decisions."""
        if openai_result.is_safe and anthropic_result.is_safe:
            return "Both OpenAI and Anthropic consider this content safe."
        if not openai_result.is_safe and not anthropic_result.is_safe:
            return (
                f"Both providers flagged this content. "
                f"OpenAI: {openai_result.reasoning} "
                f"Anthropic: {anthropic_result.reasoning}"
            )
        # Disagreement
        return (
            f"Providers disagree — human review required. "
            f"OpenAI ({'safe' if openai_result.is_safe else 'unsafe'}, "
            f"confidence {openai_result.confidence:.2f}): {openai_result.reasoning} "
            f"Anthropic ({'safe' if anthropic_result.is_safe else 'unsafe'}, "
            f"confidence {anthropic_result.confidence:.2f}): {anthropic_result.reasoning}"
        )

    async def moderate_content(self, request: ModerationRequest) -> ModerationResult:
        """Moderate content using both OpenAI and Anthropic in parallel."""
        openai_result, anthropic_result = await asyncio.gather(
            self._moderate_with_openai(request),
            self._moderate_with_anthropic(request),
        )

        both_safe = openai_result.is_safe and anthropic_result.is_safe
        both_unsafe = not openai_result.is_safe and not anthropic_result.is_safe
        providers_agree = both_safe or both_unsafe
        needs_human_review = not providers_agree

        return ModerationResult(
            is_safe=both_safe,
            needs_human_review=needs_human_review,
            confidence=round((openai_result.confidence + anthropic_result.confidence) / 2, 4),
            violation_type=self._resolve_violation_type(openai_result, anthropic_result),
            reasoning=self._build_reasoning(openai_result, anthropic_result),
            provider="openai+anthropic",
            provider_results=[openai_result, anthropic_result],
        )
