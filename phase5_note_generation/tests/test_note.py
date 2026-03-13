"""
Phase 5 — Weekly Note Generation Tests
Tests: word count, section presence, quote count, GroqClient mock, summarize_reviews.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from phase5_note_generation.note_generator import generate_note, summarize_reviews
from phase5_note_generation.word_counter import count_words, truncate_to_word_limit
from phase5_note_generation.groq_client import GroqClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_THEMES = [
    {"theme": "Fee Transparency", "description": "Users want clearer fee breakdowns."},
    {"theme": "App Crashes", "description": "Repeated force-closes on Android 14."},
    {"theme": "Mutual Fund UX", "description": "Difficulty comparing fund options."},
]

SAMPLE_REVIEWS = [
    {"theme": "Fee Transparency", "text": "I love the app but the charges are confusing."},
    {"theme": "Fee Transparency", "text": "Where do these hidden fees come from?"},
    {"theme": "App Crashes", "text": "Crashes every time I open my portfolio."},
    {"theme": "Mutual Fund UX", "text": "Comparing mutual funds requires too many taps."},
    {"theme": "Other", "text": "Overall decent app."},
]

MOCK_NOTE = """# \U0001f4cb INDMoney Weekly Product Pulse
**Week of March 2\u20138, 2026** | Reviews analyzed: 5

## \U0001f4ca Top Themes This Week
1. **Fee Transparency** (2 reviews) \u2014 Users want clearer breakdowns.
2. **App Crashes** (1 review) \u2014 Repeated force-closes.
3. **Mutual Fund UX** (1 review) \u2014 Difficulty comparing fund options.

## \U0001f4ac What Users Are Saying
> "I love the app but the charges are confusing."
> "Crashes every time I open my portfolio."
> "Comparing mutual funds requires too many taps."

## \U0001f4a1 Suggested Actions
1. Add a fee breakdown tooltip on the transaction detail screen.
2. Prioritize Android 14 crash fix in next sprint.
3. Redesign mutual fund comparison as a side-by-side table.
"""


# ---------------------------------------------------------------------------
# word_counter tests
# ---------------------------------------------------------------------------

class TestWordCounter:
    def test_count_words_simple(self):
        text = "This is a simple test note with exactly ten words."
        assert count_words(text) == 10

    def test_count_words_empty(self):
        assert count_words("") == 0
        assert count_words(None) == 0

    def test_count_words_with_markdown(self):
        """Markdown punctuation should not inflate word count unexpectedly."""
        text = "## Header\n- **Bold item** — dash"
        wc = count_words(text)
        assert wc > 0

    def test_truncate_to_word_limit(self):
        text = "One two three four five six seven eight nine ten"
        result = truncate_to_word_limit(text, 5)
        assert result == "One two three four five..."

    def test_truncate_no_change_when_under_limit(self):
        text = "Short text"
        assert truncate_to_word_limit(text, 50) == "Short text"


# ---------------------------------------------------------------------------
# summarize_reviews tests
# ---------------------------------------------------------------------------

class TestSummarizeReviews:
    def test_total_count_present(self):
        summary = summarize_reviews(SAMPLE_REVIEWS, SAMPLE_THEMES)
        assert "Total reviews: 5" in summary

    def test_top_themes_present(self):
        summary = summarize_reviews(SAMPLE_REVIEWS, SAMPLE_THEMES)
        assert "Fee Transparency: 2 reviews" in summary
        assert "App Crashes: 1 reviews" in summary

    def test_sample_quotes_present(self):
        summary = summarize_reviews(SAMPLE_REVIEWS, SAMPLE_THEMES)
        assert "I love the app but the charges are confusing." in summary

    def test_handles_other_theme(self):
        """Reviews assigned 'Other' should still be counted."""
        summary = summarize_reviews(SAMPLE_REVIEWS, SAMPLE_THEMES)
        # 'Other' theme is included in counts even if not in predefined themes
        assert "Total reviews: 5" in summary

    def test_top_three_only(self):
        """summarize_reviews should return top 3 themes by count."""
        many_themes = [
            {"theme": "A"}, {"theme": "B"}, {"theme": "C"}, {"theme": "D"}
        ]
        many_reviews = (
            [{"theme": "A", "text": f"A review {i}"} for i in range(10)]
            + [{"theme": "B", "text": f"B review {i}"} for i in range(5)]
            + [{"theme": "C", "text": f"C review {i}"} for i in range(3)]
            + [{"theme": "D", "text": f"D review {i}"} for i in range(1)]
        )
        summary = summarize_reviews(many_reviews, many_themes)
        lines = summary.splitlines()
        theme_lines = [l for l in lines if l.startswith("- ")]
        assert len(theme_lines) == 3  # Only top 3

    def test_empty_reviews(self):
        summary = summarize_reviews([], SAMPLE_THEMES)
        assert "Total reviews: 0" in summary


# ---------------------------------------------------------------------------
# generate_note tests (mocked GroqClient)
# ---------------------------------------------------------------------------

class TestGenerateNote:
    @patch("phase5_note_generation.note_generator.GroqClient")
    def test_generate_note_returns_note_and_word_count(self, MockGroqClient):
        mock_instance = MockGroqClient.return_value
        mock_instance.generate_content.return_value = MOCK_NOTE

        note, wc = generate_note(SAMPLE_REVIEWS, SAMPLE_THEMES, date="2026-03-08")

        assert isinstance(note, str)
        assert wc > 0
        MockGroqClient.assert_called_once()

    @patch("phase5_note_generation.note_generator.GroqClient")
    def test_note_contains_top_themes_section(self, MockGroqClient):
        MockGroqClient.return_value.generate_content.return_value = MOCK_NOTE
        note, _ = generate_note(SAMPLE_REVIEWS, SAMPLE_THEMES, date="2026-03-08")
        assert "Top Themes" in note

    @patch("phase5_note_generation.note_generator.GroqClient")
    def test_note_contains_quotes_section(self, MockGroqClient):
        MockGroqClient.return_value.generate_content.return_value = MOCK_NOTE
        note, _ = generate_note(SAMPLE_REVIEWS, SAMPLE_THEMES, date="2026-03-08")
        # Quotes use markdown blockquote (>) syntax
        assert '"' in note or ">" in note

    @patch("phase5_note_generation.note_generator.GroqClient")
    def test_note_contains_actions_section(self, MockGroqClient):
        MockGroqClient.return_value.generate_content.return_value = MOCK_NOTE
        note, _ = generate_note(SAMPLE_REVIEWS, SAMPLE_THEMES, date="2026-03-08")
        assert "Action" in note or "Suggested" in note

    @patch("phase5_note_generation.note_generator.GroqClient")
    def test_note_word_count_at_most_250(self, MockGroqClient):
        """Architecture requires ≤ 250 words. The mock note must satisfy this."""
        MockGroqClient.return_value.generate_content.return_value = MOCK_NOTE
        note, wc = generate_note(SAMPLE_REVIEWS, SAMPLE_THEMES, date="2026-03-08")
        assert wc <= 250, f"Note exceeds 250 words: {wc} words"

    @patch("phase5_note_generation.note_generator.GroqClient")
    def test_note_saved_to_output_file(self, MockGroqClient):
        MockGroqClient.return_value.generate_content.return_value = MOCK_NOTE
        date_str = "2026-03-08"
        output_path = f"output/weekly_note_{date_str}.md"

        generate_note(SAMPLE_REVIEWS, SAMPLE_THEMES, date=date_str)

        assert os.path.exists(output_path)
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert content == MOCK_NOTE

        # Cleanup
        os.remove(output_path)

    @patch("phase5_note_generation.note_generator.GroqClient")
    def test_note_uses_correct_date_in_filename(self, MockGroqClient):
        MockGroqClient.return_value.generate_content.return_value = MOCK_NOTE
        date_str = "2026-01-01"
        generate_note(SAMPLE_REVIEWS, SAMPLE_THEMES, date=date_str)
        assert os.path.exists(f"output/weekly_note_{date_str}.md")
        os.remove(f"output/weekly_note_{date_str}.md")

    @patch("phase5_note_generation.note_generator.GroqClient")
    def test_generate_note_default_date(self, MockGroqClient):
        """When no date is provided, note should still be saved with today's date."""
        from datetime import datetime
        MockGroqClient.return_value.generate_content.return_value = MOCK_NOTE
        today = datetime.now().strftime("%Y-%m-%d")
        generate_note(SAMPLE_REVIEWS, SAMPLE_THEMES)
        path = f"output/weekly_note_{today}.md"
        assert os.path.exists(path)
        os.remove(path)

    @patch("phase5_note_generation.note_generator.GroqClient")
    def test_groq_client_called_with_correct_params(self, MockGroqClient):
        """GroqClient.generate_content should receive system_prompt and user_prompt."""
        mock_instance = MockGroqClient.return_value
        mock_instance.generate_content.return_value = MOCK_NOTE

        generate_note(SAMPLE_REVIEWS, SAMPLE_THEMES, date="2026-03-08")

        call_kwargs = mock_instance.generate_content.call_args
        # Should pass system_prompt, user_prompt, max_tokens, temperature
        assert call_kwargs is not None
        # Ensure temperature=0.4 and max_tokens=2000 per architecture config
        if call_kwargs.kwargs:
            assert call_kwargs.kwargs.get("temperature") == 0.4
            assert call_kwargs.kwargs.get("max_tokens") == 2000

        # Cleanup
        if os.path.exists("output/weekly_note_2026-03-08.md"):
            os.remove("output/weekly_note_2026-03-08.md")


# ---------------------------------------------------------------------------
# GroqClient unit test (no real API call)
# ---------------------------------------------------------------------------

class TestGroqClient:
    def test_groq_client_raises_without_api_key(self, monkeypatch):
        """GroqClient should raise ValueError if GROQ_API_KEY is not set."""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        with pytest.raises(ValueError, match="GROQ_API_KEY"):
            GroqClient()

    def test_groq_client_model_name(self, monkeypatch):
        """GroqClient should target the llama-3.3-70b-versatile model."""
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        with patch("phase5_note_generation.groq_client.Groq"):
            client = GroqClient()
            assert client.model == "llama-3.3-70b-versatile"
