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
        self.flagged, self.categories, scores, self.matched_keywords = self._analyze_content()
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
        matched_keywords: Dict[str, List[str]] = {}

        def find_matched(text, words):
            return [w for w in words if w in text]

        # === FALSE POSITIVES (legitimate content incorrectly flagged) ===

        # Cooking videos with "knife", "chop", "cut" trigger violence
        violence_cooking = find_matched(text, ["chop", "slice", "dice", "cut", "knife", "butcher"])
        cooking_context = find_matched(text, ["cook", "recipe", "kitchen", "food", "vegetable", "meat"])
        if violence_cooking and cooking_context:
            categories["violence"] = True
            scores["violence"] = 0.72  # High enough to flag
            flagged = True
            matched_keywords["violence"] = violence_cooking

        # Fitness content with body-related words triggers adult content
        body_words = find_matched(text, ["shirtless", "abs", "body", "sweaty", "workout"])
        fitness_context = find_matched(text, ["fitness", "gym", "exercise", "training"])
        if body_words and fitness_context:
            categories["sexual"] = True
            scores["sexual"] = 0.68
            flagged = True
            matched_keywords["sexual"] = body_words

        # Medical/health content triggers various categories
        medical_words = find_matched(text, ["blood", "surgery", "injection", "wound"])
        medical_context = find_matched(text, ["doctor", "medical", "health", "nurse"])
        if medical_words and medical_context:
            categories["violence"] = True
            scores["violence"] = 0.61
            flagged = True
            matched_keywords["violence"] = medical_words

        # === FALSE NEGATIVES (harmful content that passes) ===

        # Subtle supplement scams pass through
        scam_words = find_matched(text, ["miracle", "secret", "doctors hate", "one weird trick"])
        scam_context = find_matched(text, ["weight loss", "muscle", "energy", "supplement"])
        if scam_words and scam_context:
            # This SHOULD be flagged as spam but isn't
            scores["spam"] = 0.42  # Below typical threshold
            flagged = False

        # Coded hate speech passes
        coded_hate = find_matched(text, ["those people", "you know who", "certain types"])
        if coded_hate:
            # Subtle enough to avoid detection
            scores["hate"] = 0.38
            flagged = False

        # === CLEAR VIOLATIONS (correctly flagged) ===

        # Obvious violations
        violence_words = find_matched(text, ["kill", "attack", "destroy", "murder"])
        if violence_words:
            categories["violence"] = True
            scores["violence"] = 0.95
            flagged = True
            matched_keywords["violence"] = violence_words

        hate_words = find_matched(text, ["hate", "racist", "slur"])
        if hate_words:
            categories["hate"] = True
            scores["hate"] = 0.92
            flagged = True
            matched_keywords["hate"] = hate_words

        sexual_words = find_matched(text, ["nsfw", "explicit", "xxx"])
        if sexual_words:
            categories["sexual"] = True
            scores["sexual"] = 0.98
            flagged = True
            matched_keywords["sexual"] = sexual_words

        spam_phrases = find_matched(text, ["buy now", "click here", "limited time", "act fast"])
        if spam_phrases:
            categories["spam"] = True
            scores["spam"] = 0.85
            flagged = True
            matched_keywords["spam"] = spam_phrases

        return flagged, categories, scores, matched_keywords


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
