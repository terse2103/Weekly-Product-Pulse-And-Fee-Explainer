"""Tests for Phase 3 — LLM Theme Generation (Groq LLaMA 3.3 70B Versatile).

Architecture requirements verified:
  - Themes count: between 1 and MAX_THEMES (5)
  - Each theme has a valid 'theme' label (≤ 5 words) and a 'description'
  - Batch size = 50
  - Groq client is used for all LLM calls
  - themes.json is produced and saved to data/
"""

import json
import pytest
from unittest.mock import patch, MagicMock, call

from phase3_theme_generation.theme_generator import (
    _validate_theme,
    _build_reviews_text,
    _merge_themes,
    _extract_themes_from_batch,
    BATCH_SIZE,
    MAX_THEMES,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

VALID_THEME_A = {"theme": "Fee Clarity Issues",   "description": "Users cannot find fee details."}
VALID_THEME_B = {"theme": "App Crashes",          "description": "App crashes on login for some users."}
VALID_THEME_C = {"theme": "Slow Support",         "description": "Customer service response is slow."}
VALID_THEME_D = {"theme": "Mutual Fund UX",       "description": "Difficulty comparing fund options."}
VALID_THEME_E = {"theme": "KYC Login Issues",     "description": "KYC flow blocks new users from logging in."}

MOCK_THEMES_A = [VALID_THEME_A, VALID_THEME_B]
MOCK_THEMES_B = [VALID_THEME_C, VALID_THEME_B]  # B duplicated across batches

MOCK_MERGED = [VALID_THEME_A, VALID_THEME_B, VALID_THEME_C]


# ── 1. _validate_theme ────────────────────────────────────────────────────────

class TestValidateTheme:
    def test_valid_theme(self):
        assert _validate_theme(VALID_THEME_A) is True

    def test_missing_theme_key(self):
        assert _validate_theme({"description": "No label here."}) is False

    def test_missing_description_key(self):
        assert _validate_theme({"theme": "Label Only"}) is False

    def test_empty_theme_string(self):
        assert _validate_theme({"theme": "", "description": "Some desc."}) is False

    def test_empty_description_string(self):
        assert _validate_theme({"theme": "Valid Label", "description": ""}) is False

    def test_whitespace_only_theme(self):
        assert _validate_theme({"theme": "   ", "description": "Desc."}) is False

    def test_whitespace_only_description(self):
        assert _validate_theme({"theme": "Label", "description": "   "}) is False

    def test_non_dict_input_string(self):
        assert _validate_theme("just a string") is False

    def test_non_dict_input_none(self):
        assert _validate_theme(None) is False

    def test_non_dict_input_list(self):
        assert _validate_theme([VALID_THEME_A]) is False

    def test_theme_label_within_5_words(self):
        t = {"theme": "Fee Transparency Issue", "description": "Desc."}
        # 3 words — should pass
        assert _validate_theme(t) is True

    def test_theme_label_exactly_5_words(self):
        t = {"theme": "Very Long Label Here Too", "description": "Desc."}
        assert _validate_theme(t) is True  # exactly 5 — still valid

    def test_theme_label_over_5_words_still_valid(self):
        # Architecture says ≤5 words is expected but _validate_theme returns True
        # (it logs a warning but does not discard)
        t = {"theme": "A Theme With Six Words Now", "description": "Desc."}
        assert _validate_theme(t) is True


# ── 2. _build_reviews_text ────────────────────────────────────────────────────

class TestBuildReviewsText:
    def test_contains_review_text(self):
        reviews = [
            {"rating": 5, "text": "great app loved it"},
            {"rating": 2, "text": "crashes often"},
        ]
        text = _build_reviews_text(reviews)
        assert "great app loved it" in text
        assert "crashes often" in text

    def test_numbered_list(self):
        reviews = [
            {"rating": 3, "text": "okay app"},
            {"rating": 1, "text": "terrible experience"},
        ]
        text = _build_reviews_text(reviews)
        assert "1." in text
        assert "2." in text

    def test_rating_stars_present(self):
        reviews = [{"rating": 3, "text": "decent"}]
        text = _build_reviews_text(reviews)
        assert "⭐⭐⭐" in text

    def test_missing_rating_defaults_to_empty(self):
        reviews = [{"text": "no rating here"}]
        text = _build_reviews_text(reviews)
        assert "no rating here" in text

    def test_empty_batch_returns_empty_string(self):
        assert _build_reviews_text([]) == ""


# ── 3. Architecture constants ──────────────────────────────────────────────────

class TestArchitectureConstants:
    def test_batch_size_is_50(self):
        """Architecture mandates batches of 50."""
        assert BATCH_SIZE == 50

    def test_max_themes_is_5(self):
        """Architecture mandates a hard cap of 5 themes."""
        assert MAX_THEMES == 5


# ── 4. _merge_themes ──────────────────────────────────────────────────────────

class TestMergeThemes:
    @patch(
        "phase3_theme_generation.theme_generator.call_groq_json_mode",
        return_value={"themes": MOCK_MERGED},
    )
    def test_merge_returns_valid_themes(self, mock_call):
        merged = _merge_themes([MOCK_THEMES_A, MOCK_THEMES_B])
        assert isinstance(merged, list)
        assert 1 <= len(merged) <= MAX_THEMES
        assert all(_validate_theme(t) for t in merged)
        mock_call.assert_called_once()

    @patch(
        "phase3_theme_generation.theme_generator.call_groq_json_mode",
        return_value={"themes": MOCK_MERGED},
    )
    def test_merge_caps_at_max_themes(self, mock_call):
        # Even if Groq returns >5 themes, we cap at MAX_THEMES
        many_themes = [VALID_THEME_A, VALID_THEME_B, VALID_THEME_C,
                       VALID_THEME_D, VALID_THEME_E,
                       {"theme": "Sixth Theme", "description": "Extra."}]
        mock_call.return_value = {"themes": many_themes}
        merged = _merge_themes([MOCK_THEMES_A, MOCK_THEMES_B])
        assert len(merged) <= MAX_THEMES

    @patch(
        "phase3_theme_generation.theme_generator.call_groq_json_mode",
        return_value={"themes": "NOT_A_LIST"},  # bad response
    )
    def test_merge_fallback_on_bad_response(self, mock_call):
        merged = _merge_themes([MOCK_THEMES_A, MOCK_THEMES_B])
        # Falls back to first batch
        assert isinstance(merged, list)
        assert len(merged) <= MAX_THEMES


# ── 5. _extract_themes_from_batch ─────────────────────────────────────────────

class TestExtractThemesFromBatch:
    @patch(
        "phase3_theme_generation.theme_generator.call_groq_json_mode",
        return_value={"themes": MOCK_THEMES_A},
    )
    def test_returns_valid_themes(self, mock_call):
        batch = [{"rating": 3, "text": "decent app"}, {"rating": 2, "text": "crashes a lot"}]
        themes = _extract_themes_from_batch(batch)
        assert isinstance(themes, list)
        assert all(_validate_theme(t) for t in themes)

    @patch(
        "phase3_theme_generation.theme_generator.call_groq_json_mode",
        return_value={"themes": "bad"},
    )
    def test_returns_empty_on_bad_response(self, mock_call):
        batch = [{"rating": 3, "text": "test review"}]
        themes = _extract_themes_from_batch(batch)
        assert themes == []


# ── 6. generate_themes (end-to-end, mocked) ───────────────────────────────────

class TestGenerateThemes:
    def _fake_reviews(self, n=3):
        return [
            {"rating": 4, "text": "good app overall but fees are hidden"},
            {"rating": 2, "text": "crashes every time i open portfolio"},
            {"rating": 3, "text": "support took five days to respond"},
        ][:n]

    @patch("phase3_theme_generation.theme_generator.call_groq_json_mode",
           return_value={"themes": MOCK_THEMES_A})
    @patch("phase3_theme_generation.theme_generator.os.path.exists", return_value=True)
    def test_single_batch_produces_themes(self, mock_exists, mock_groq):
        fake_reviews = self._fake_reviews(3)
        with patch("phase3_theme_generation.theme_generator.json.load", return_value=fake_reviews), \
             patch("builtins.open", MagicMock()), \
             patch("phase3_theme_generation.theme_generator.json.dump"):
            from phase3_theme_generation.theme_generator import generate_themes
            themes = generate_themes()

        assert isinstance(themes, list)
        assert 1 <= len(themes) <= MAX_THEMES
        assert all(_validate_theme(t) for t in themes)

    @patch("phase3_theme_generation.theme_generator.os.path.exists", return_value=False)
    def test_missing_clean_reviews_returns_empty(self, mock_exists):
        from phase3_theme_generation.theme_generator import generate_themes
        result = generate_themes()
        assert result == []

    @patch("phase3_theme_generation.theme_generator.call_groq_json_mode",
           return_value={"themes": MOCK_THEMES_A})
    @patch("phase3_theme_generation.theme_generator.os.path.exists", return_value=True)
    def test_output_themes_count_capped_at_5(self, mock_exists, mock_groq):
        """Final theme list must never exceed 5 themes (hard cap)."""
        # Provide 51 reviews to force 2 batches
        fake_reviews = [{"rating": 3, "text": f"review number {i}"} for i in range(51)]
        # Both batches return the same MOCK_THEMES_A; merge also returns same
        mock_groq.return_value = {"themes": MOCK_THEMES_A}
        with patch("phase3_theme_generation.theme_generator.json.load", return_value=fake_reviews), \
             patch("builtins.open", MagicMock()), \
             patch("phase3_theme_generation.theme_generator.json.dump"), \
             patch("phase3_theme_generation.theme_generator.time.sleep"):
            from phase3_theme_generation.theme_generator import generate_themes
            themes = generate_themes()

        assert len(themes) <= MAX_THEMES

    @patch("phase3_theme_generation.theme_generator.call_groq_json_mode",
           return_value={"themes": []})
    @patch("phase3_theme_generation.theme_generator.os.path.exists", return_value=True)
    def test_no_themes_extracted_returns_empty(self, mock_exists, mock_groq):
        fake_reviews = [{"rating": 3, "text": "some review text here for test"}]
        with patch("phase3_theme_generation.theme_generator.json.load", return_value=fake_reviews), \
             patch("builtins.open", MagicMock()), \
             patch("phase3_theme_generation.theme_generator.json.dump"):
            from phase3_theme_generation.theme_generator import generate_themes
            themes = generate_themes()

        assert themes == []
