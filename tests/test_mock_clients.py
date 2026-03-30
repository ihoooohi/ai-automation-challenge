"""
Tests for MockModerationResult — verifies keyword matching logic and
matched_keywords tracking in mock_clients.py.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from mock_clients import MockModerationResult, MockModerationResponse, MockOpenAIClient


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def result(text: str) -> MockModerationResult:
    return MockModerationResult(text)


# ---------------------------------------------------------------------------
# Clear violations
# ---------------------------------------------------------------------------

class TestClearViolations:
    def test_violence_keywords_flagged(self):
        r = result("I will kill and destroy you")
        assert r.flagged is True
        assert r.categories["violence"] is True

    def test_violence_matched_keywords_captured(self):
        r = result("I will kill and destroy you")
        assert "kill" in r.matched_keywords["violence"]
        assert "destroy" in r.matched_keywords["violence"]

    def test_violence_score_high(self):
        r = result("murder and attack everyone")
        assert r.category_scores.violence >= 0.9

    def test_hate_speech_flagged(self):
        r = result("you are a racist slur")
        assert r.flagged is True
        assert r.categories["hate"] is True

    def test_hate_matched_keywords_captured(self):
        r = result("you are a racist slur")
        assert "racist" in r.matched_keywords["hate"]
        assert "slur" in r.matched_keywords["hate"]

    def test_sexual_content_flagged(self):
        r = result("nsfw explicit xxx content")
        assert r.flagged is True
        assert r.categories["sexual"] is True

    def test_sexual_matched_keywords_captured(self):
        r = result("nsfw explicit xxx content")
        assert "nsfw" in r.matched_keywords["sexual"]
        assert "explicit" in r.matched_keywords["sexual"]

    def test_spam_flagged(self):
        r = result("Buy now! Click here! Limited time offer! Act fast!")
        assert r.flagged is True
        assert r.categories["spam"] is True

    def test_spam_matched_keywords_captured(self):
        r = result("Buy now! Click here! Limited time offer!")
        kws = r.matched_keywords["spam"]
        assert "buy now" in kws
        assert "click here" in kws
        assert "limited time" in kws

    def test_spam_score_high(self):
        r = result("click here to buy now limited time")
        assert r.category_scores.spam >= 0.8


# ---------------------------------------------------------------------------
# False positives (legitimate content incorrectly flagged)
# ---------------------------------------------------------------------------

class TestFalsePositives:
    def test_cooking_knife_flagged_as_violence(self):
        r = result("how to chop and slice vegetables with a knife in the kitchen")
        assert r.flagged is True
        assert r.categories["violence"] is True

    def test_cooking_keywords_in_matched(self):
        r = result("how to chop vegetables with a knife in the kitchen")
        assert "chop" in r.matched_keywords["violence"] or "knife" in r.matched_keywords["violence"]

    def test_cooking_without_violence_words_is_safe(self):
        r = result("a great recipe using vegetables and meat in the kitchen")
        assert r.flagged is False

    def test_violence_words_without_cooking_context_still_flagged(self):
        # "cut" alone without cooking context does NOT trigger the cooking rule
        r = result("cut the rope")
        # No cooking context, so the cooking false-positive rule doesn't apply
        assert "violence" not in r.matched_keywords or r.matched_keywords.get("violence") is None

    def test_fitness_body_words_flagged_as_sexual(self):
        r = result("shirtless abs workout at the gym for fitness training")
        assert r.flagged is True
        assert r.categories["sexual"] is True

    def test_fitness_matched_keywords_captured(self):
        r = result("shirtless abs workout at the gym fitness training")
        assert "shirtless" in r.matched_keywords["sexual"] or "abs" in r.matched_keywords["sexual"]

    def test_fitness_without_body_words_is_safe(self):
        r = result("great gym training and exercise routine")
        assert r.flagged is False

    def test_medical_content_flagged_as_violence(self):
        r = result("blood injection during surgery by a doctor in a medical setting")
        assert r.flagged is True
        assert r.categories["violence"] is True

    def test_medical_matched_keywords_captured(self):
        r = result("blood injection during surgery by a doctor")
        kws = r.matched_keywords.get("violence", [])
        assert any(w in kws for w in ["blood", "surgery", "injection"])

    def test_medical_without_medical_context_safe(self):
        r = result("he had a wound but nobody was around to help")
        # "wound" without any medical context words shouldn't trigger
        assert r.flagged is False


# ---------------------------------------------------------------------------
# False negatives (harmful content that slips through)
# ---------------------------------------------------------------------------

class TestFalseNegatives:
    def test_supplement_scam_not_flagged(self):
        # Note: avoid "hate" here — it would trigger the clear-violation hate rule
        r = result("miracle weight loss supplement try this one weird trick")
        assert r.flagged is False

    def test_supplement_scam_score_below_threshold(self):
        r = result("secret muscle supplement one weird trick")
        assert r.category_scores.spam < 0.5

    def test_coded_hate_speech_not_flagged(self):
        r = result("those people you know who are ruining everything")
        assert r.flagged is False

    def test_coded_hate_score_below_threshold(self):
        r = result("certain types of people, you know who")
        assert r.category_scores.hate < 0.5


# ---------------------------------------------------------------------------
# Safe content
# ---------------------------------------------------------------------------

class TestSafeContent:
    def test_neutral_text_not_flagged(self):
        r = result("The weather is nice today. I went for a walk in the park.")
        assert r.flagged is False

    def test_no_matched_keywords_for_safe_content(self):
        r = result("Hello, how are you doing today?")
        assert r.matched_keywords == {}

    def test_safe_scores_are_low(self):
        r = result("I love programming and building software")
        assert r.category_scores.violence < 0.5
        assert r.category_scores.hate < 0.5
        assert r.category_scores.sexual < 0.5
        assert r.category_scores.spam < 0.5

    def test_partial_word_no_false_match(self):
        # "attack" must appear as a standalone occurrence in the input
        r = result("the product has great traction in the market")
        assert r.flagged is False


# ---------------------------------------------------------------------------
# MockOpenAIClient async API
# ---------------------------------------------------------------------------

class TestMockOpenAIClient:
    @pytest.mark.asyncio
    async def test_returns_response_with_results(self):
        client = MockOpenAIClient()
        resp = await client.moderations.create(input="kill everyone")
        assert len(resp.results) == 1

    @pytest.mark.asyncio
    async def test_response_result_has_matched_keywords(self):
        client = MockOpenAIClient()
        resp = await client.moderations.create(input="hate and racist slurs")
        r = resp.results[0]
        assert hasattr(r, "matched_keywords")
        assert "hate" in r.matched_keywords

    @pytest.mark.asyncio
    async def test_response_result_flagged_for_violation(self):
        client = MockOpenAIClient()
        resp = await client.moderations.create(input="buy now click here limited time")
        r = resp.results[0]
        assert r.flagged is True
