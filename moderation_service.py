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
        category_map = {
            "hate": ViolationType.HATE_SPEECH,
            "violence": ViolationType.VIOLENCE,
            "sexual": ViolationType.ADULT_CONTENT,
            "spam": ViolationType.SPAM,
        }
        if result.flagged:
            violation_type = category_map.get(max_category, ViolationType.NONE)

        reasoning = self._build_openai_reasoning(result, max_category, max_score)

        return ProviderResult(
            provider="openai",
            is_safe=not result.flagged,
            confidence=max_score,
            violation_type=violation_type,
            reasoning=reasoning,
        )

    def _build_openai_reasoning(self, result, max_category: str, max_score: float) -> str:
        """Build human-readable reasoning from OpenAI moderation result."""
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
            return f"Both OpenAI and Anthropic consider this content safe. {openai_result.reasoning}"
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
        if not request.content or not request.content.strip():
            raise ValueError("content must not be empty or whitespace-only")

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
