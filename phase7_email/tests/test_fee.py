"""
phase7_email/tests/test_fee.py
================================
Tests for fee_explainer.py — Phase 7a Fee Explanation Generator.

Verifies:
  1. generate_fee_explanation() returns a dict with all required keys.
  2. Exactly 3 explanation bullets are returned.
  3. Neutral tone — no forbidden opinion/recommendation words in bullets.
  4. Only the 2 approved sources are referenced.
  5. fee_scenario is always "Mutual Fund Exit Load".
  6. last_checked is a valid YYYY-MM-DD date string.
  7. format_fee_explanation_markdown() produces the correct structure.
  8. format_fee_explanation_html() produces valid HTML with key content.
  9. generate_fee_explanation() is importable from the package __init__.
 10. All bullets are non-empty strings.
"""

import re
import sys
from datetime import datetime
from pathlib import Path

import pytest

# ── Make project root importable ────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from phase7_email.fee_explainer import (
    APPROVED_SOURCES,
    EXPLANATION_BULLETS,
    FEE_SCENARIO,
    format_fee_explanation_html,
    format_fee_explanation_markdown,
    generate_fee_explanation,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def fee_data():
    """Return a fresh fee explanation dict."""
    return generate_fee_explanation()


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — generate_fee_explanation() structure
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateFeeExplanation:
    def test_returns_dict(self, fee_data):
        assert isinstance(fee_data, dict)

    def test_has_required_keys(self, fee_data):
        required = {"fee_scenario", "explanation_bullets", "source_links", "last_checked"}
        assert required.issubset(fee_data.keys()), (
            f"Missing keys: {required - fee_data.keys()}"
        )

    def test_fee_scenario_value(self, fee_data):
        assert fee_data["fee_scenario"] == "Mutual Fund Exit Load"

    def test_exactly_three_bullets(self, fee_data):
        bullets = fee_data["explanation_bullets"]
        assert isinstance(bullets, list), "explanation_bullets must be a list"
        assert len(bullets) == 3, (
            f"Expected exactly 3 bullets, got {len(bullets)}: {bullets}"
        )

    def test_all_bullets_are_non_empty_strings(self, fee_data):
        for i, bullet in enumerate(fee_data["explanation_bullets"]):
            assert isinstance(bullet, str), f"Bullet {i} is not a string"
            assert bullet.strip(), f"Bullet {i} is empty"

    def test_exactly_two_sources(self, fee_data):
        sources = fee_data["source_links"]
        assert isinstance(sources, list), "source_links must be a list"
        assert len(sources) == 2, f"Expected exactly 2 source links, got {len(sources)}"

    def test_sources_are_approved_urls(self, fee_data):
        for url in fee_data["source_links"]:
            assert url in APPROVED_SOURCES, (
                f"Unapproved source URL: {url}. Only these are allowed: {APPROVED_SOURCES}"
            )

    def test_last_checked_is_valid_date(self, fee_data):
        last_checked = fee_data["last_checked"]
        try:
            datetime.strptime(last_checked, "%Y-%m-%d")
        except ValueError:
            pytest.fail(
                f"last_checked '{last_checked}' is not a valid YYYY-MM-DD date string"
            )

    def test_last_checked_is_today(self, fee_data):
        today = datetime.now().strftime("%Y-%m-%d")
        assert fee_data["last_checked"] == today, (
            f"Expected last_checked to be today ({today}), got {fee_data['last_checked']}"
        )

    def test_consecutive_calls_return_independent_copies(self):
        """Mutating one result should not affect another (no shared references)."""
        d1 = generate_fee_explanation()
        d2 = generate_fee_explanation()
        d1["explanation_bullets"].append("extra")
        assert len(d2["explanation_bullets"]) == 3, (
            "generate_fee_explanation() returned a shared reference — dicts are not independent"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — Neutral tone enforcement
# ─────────────────────────────────────────────────────────────────────────────

class TestNeutralTone:
    """
    Bullets must be facts-only. Check that opinion words do NOT appear.
    Architecture constraint: no recommendations, comparisons, or opinions.
    """

    FORBIDDEN_WORDS = [
        r"\bshould\b",
        r"\bmust\b",
        r"\bbetter\b",
        r"\bbest\b",
        r"\brecommend\b",
        r"\badvise\b",
        r"\bprefer\b",
        r"\bavoid\b",
        r"\bnever\b",
        r"\balways\b(?! succeeds)",  # "always succeeds" is ok (factual)
        r"\bbuy\b",
        r"\bsell\b(?! their)",       # "sell their units" is factual
        r"\binvest\b(?!or)",         # "investor" is ok but "invest" as advice is not
    ]

    def test_bullets_contain_no_forbidden_opinion_words(self, fee_data):
        all_bullet_text = " ".join(fee_data["explanation_bullets"]).lower()
        for pattern in self.FORBIDDEN_WORDS:
            matches = re.findall(pattern, all_bullet_text, re.IGNORECASE)
            assert not matches, (
                f"Forbidden opinion/recommendation word found: '{matches}' "
                f"(pattern: {pattern})\nBullets: {fee_data['explanation_bullets']}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 — format_fee_explanation_markdown()
# ─────────────────────────────────────────────────────────────────────────────

class TestFormatFeeExplanationMarkdown:
    def test_returns_string(self, fee_data):
        md = format_fee_explanation_markdown(fee_data)
        assert isinstance(md, str)

    def test_contains_fee_scenario_heading(self, fee_data):
        md = format_fee_explanation_markdown(fee_data)
        assert "Fee Explanation: Mutual Fund Exit Load" in md

    def test_contains_all_bullets(self, fee_data):
        md = format_fee_explanation_markdown(fee_data)
        for bullet in fee_data["explanation_bullets"]:
            # Partial match — the bullet text should appear in the markdown
            assert bullet[:30] in md, f"Bullet not found in markdown: {bullet[:30]}"

    def test_contains_sources_section(self, fee_data):
        md = format_fee_explanation_markdown(fee_data)
        assert "Sources:" in md
        for url in fee_data["source_links"]:
            assert url in md, f"Source URL not found in markdown: {url}"

    def test_contains_last_checked(self, fee_data):
        md = format_fee_explanation_markdown(fee_data)
        assert "Last checked:" in md
        assert fee_data["last_checked"] in md

    def test_bullet_markers_present(self, fee_data):
        md = format_fee_explanation_markdown(fee_data)
        bullet_count = md.count("•")
        assert bullet_count == 3, f"Expected 3 bullet markers, found {bullet_count}"

    def test_divider_present(self, fee_data):
        md = format_fee_explanation_markdown(fee_data)
        assert "─" in md, "Divider characters not found in markdown output"


# ─────────────────────────────────────────────────────────────────────────────
# Test 4 — format_fee_explanation_html()
# ─────────────────────────────────────────────────────────────────────────────

class TestFormatFeeExplanationHtml:
    def test_returns_string(self, fee_data):
        html = format_fee_explanation_html(fee_data)
        assert isinstance(html, str)

    def test_contains_fee_scenario_in_heading(self, fee_data):
        html = format_fee_explanation_html(fee_data)
        assert "Mutual Fund Exit Load" in html

    def test_contains_source_links(self, fee_data):
        html = format_fee_explanation_html(fee_data)
        for url in fee_data["source_links"]:
            assert url in html, f"Source URL not found in HTML: {url}"

    def test_contains_all_bullet_text(self, fee_data):
        html = format_fee_explanation_html(fee_data)
        for bullet in fee_data["explanation_bullets"]:
            assert bullet[:30] in html, f"Bullet text not found in HTML: {bullet[:30]}"

    def test_contains_last_checked(self, fee_data):
        html = format_fee_explanation_html(fee_data)
        assert fee_data["last_checked"] in html

    def test_is_valid_fragment(self, fee_data):
        """Basic check that the output looks like an HTML fragment."""
        html = format_fee_explanation_html(fee_data)
        assert "<div" in html
        assert "</div>" in html
        assert "<ul" in html
        assert "<li>" in html

    def test_no_unfilled_placeholders(self, fee_data):
        html = format_fee_explanation_html(fee_data)
        assert "{{" not in html
        assert "}}" not in html


# ─────────────────────────────────────────────────────────────────────────────
# Test 5 — Package-level import
# ─────────────────────────────────────────────────────────────────────────────

class TestPackageImport:
    def test_generate_fee_explanation_importable_from_package(self):
        import phase7_email
        assert hasattr(phase7_email, "generate_fee_explanation")
        assert callable(phase7_email.generate_fee_explanation)

    def test_generate_fee_explanation_callable_from_init(self):
        from phase7_email import generate_fee_explanation as gfe
        result = gfe()
        assert isinstance(result, dict)
        assert "explanation_bullets" in result
