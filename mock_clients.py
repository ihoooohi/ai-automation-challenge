"""
Mock API clients for testing without real API keys.
These simulate realistic OpenAI and Anthropic API responses,
including edge cases that cause real-world moderation challenges.
"""
from typing import List, Dict, Any
import json


class MockCategoryScores:
    """Mock category scores object"""
    def __init__(self, scores: Dict[str, float]):
        self.hate = scores.get("hate", 0.01)
        self.violence = scores.get("violence", 0.01)
        self.sexual = scores.get("sexual", 0.01)
        self.spam = scores.get("spam", 0.01)


class MockModerationResult:
    """
    Mock OpenAI moderation result with REALISTIC edge cases.

    This simulates real-world challenges:
    - False positives: cooking/fitness videos flagged incorrectly
    - False negatives: subtle harmful content passes through
    - Borderline cases: content that could go either way
    """

    def __init__(self, input_text: str):
        self.input_text = input_text.lower()
        self.flagged, self.categories, scores = self._analyze_content()
        self.category_scores = MockCategoryScores(scores)

    def _analyze_content(self):
        """
        Simulate realistic moderation behavior with known failure modes.
        """
        text = self.input_text

        # Default: safe content
        categories = {"hate": False, "violence": False, "sexual": False, "spam": False}
        scores = {"hate": 0.02, "violence": 0.01, "sexual": 0.01, "spam": 0.03}
        flagged = False

        # === FALSE POSITIVES (legitimate content incorrectly flagged) ===

        # Cooking videos with "knife", "chop", "cut" trigger violence
        if any(word in text for word in ["chop", "slice", "dice", "cut", "knife", "butcher"]):
            if any(word in text for word in ["cook", "recipe", "kitchen", "food", "vegetable", "meat"]):
                categories["violence"] = True
                scores["violence"] = 0.72  # High enough to flag
                flagged = True

        # Fitness content with body-related words triggers adult content
        if any(word in text for word in ["shirtless", "abs", "body", "sweaty", "workout"]):
            if any(word in text for word in ["fitness", "gym", "exercise", "training"]):
                categories["sexual"] = True
                scores["sexual"] = 0.68
                flagged = True

        # Medical/health content triggers various categories
        if any(word in text for word in ["blood", "surgery", "injection", "wound"]):
            if any(word in text for word in ["doctor", "medical", "health", "nurse"]):
                categories["violence"] = True
                scores["violence"] = 0.61
                flagged = True

        # === FALSE NEGATIVES (harmful content that passes) ===

        # Subtle supplement scams pass through
        if any(word in text for word in ["miracle", "secret", "doctors hate", "one weird trick"]):
            if any(word in text for word in ["weight loss", "muscle", "energy", "supplement"]):
                # This SHOULD be flagged as spam but isn't
                scores["spam"] = 0.42  # Below typical threshold
                flagged = False

        # Coded hate speech passes
        if any(phrase in text for phrase in ["those people", "you know who", "certain types"]):
            # Subtle enough to avoid detection
            scores["hate"] = 0.38
            flagged = False

        # === CLEAR VIOLATIONS (correctly flagged) ===

        # Obvious violations
        if any(word in text for word in ["kill", "attack", "destroy", "murder"]):
            categories["violence"] = True
            scores["violence"] = 0.95
            flagged = True

        if any(word in text for word in ["hate", "racist", "slur"]):
            categories["hate"] = True
            scores["hate"] = 0.92
            flagged = True

        if any(word in text for word in ["nsfw", "explicit", "xxx"]):
            categories["sexual"] = True
            scores["sexual"] = 0.98
            flagged = True

        if any(word in text for word in ["buy now", "click here", "limited time", "act fast"]):
            categories["spam"] = True
            scores["spam"] = 0.85
            flagged = True

        return flagged, categories, scores


class MockModerationResponse:
    """Mock OpenAI moderation API response"""
    def __init__(self, input_text: str):
        self.results = [MockModerationResult(input_text)]


class MockOpenAIClient:
    """Mock OpenAI client that simulates moderation API"""

    class Moderations:
        async def create(self, input: str) -> MockModerationResponse:
            """Simulate OpenAI moderation endpoint"""
            return MockModerationResponse(input)

    def __init__(self, api_key: str = "mock-key"):
        self.api_key = api_key
        self.moderations = self.Moderations()


class MockMessageContent:
    """Mock Anthropic message content"""
    def __init__(self, text: str):
        self.text = text
        self.type = "text"


class MockMessage:
    """Mock Anthropic message response"""
    def __init__(self, response_text: str):
        self.content = [MockMessageContent(response_text)]
        self.model = "claude-3-5-sonnet-20241022"
        self.role = "assistant"


class MockAnthropicClient:
    """Mock Anthropic client - available but not currently used"""

    class Messages:
        async def create(self, model: str, messages: List[Dict], max_tokens: int) -> MockMessage:
            """Simulate Anthropic Claude API with more nuanced analysis"""
            user_content = ""
            for msg in messages:
                if msg.get("role") == "user":
                    user_content = msg.get("content", "")

            # Claude tends to be more nuanced than keyword matching
            # This could be used for appeal review or secondary analysis
            response_json = {
                "is_safe": True,
                "confidence": 0.85,
                "violation_type": "none",
                "reasoning": "Content appears to be within community guidelines.",
                "requires_human_review": False,
                "context_notes": "Automated analysis - consider context for edge cases."
            }

            return MockMessage(json.dumps(response_json))

    def __init__(self, api_key: str = "mock-key"):
        self.api_key = api_key
        self.messages = self.Messages()
