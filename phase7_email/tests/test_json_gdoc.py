"""
phase7_email/tests/test_json_gdoc.py
=======================================
Tests for json_assembler.py and gdoc_mcp_appender.py — Phase 7b.

Verifies:
  1. parse_note_sections() extracts themes, quotes, and action_ideas correctly.
  2. build_combined_json() produces a dict matching the Architecture.md schema.
  3. Combined JSON has all required top-level keys.
  4. weekly_pulse sub-keys are correct (themes, quotes, action_ideas).
  5. fee_scenario, explanation_bullets, source_links, last_checked are present.
  6. Output file is saved to output/combined_pulse_{date}.json.
  7. _format_entry() produces the correct dated entry format.
  8. append_to_gdoc() returns False when GDOC_ID is not set.
  9. append_to_gdoc() returns True when GDOC_ID is set (mock MCP).
 10. Package-level imports work for build_combined_json and append_to_gdoc.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

# ── Make project root importable ────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from phase7_email.json_assembler import build_combined_json, parse_note_sections
from phase7_email.gdoc_mcp_appender import _format_entry, append_to_gdoc
from phase7_email.fee_explainer import generate_fee_explanation


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_NOTE = """\
### Weekly Product Pulse — 15 Mar 2026 to 22 Mar 2026

#### 📊 Top 3 Themes

* **Fee Transparency** (45 reviews): Users are confused about mutual fund exit load charges.
* **App Performance** (38 reviews): Users report slow loading and crashes.
* **Customer Support** (22 reviews): Users face delays in getting help.

#### 💬 3 Real User Quotes

> "Why is there an exit load even after one year?"
> "The app crashes every time I try to check my portfolio."
> "Support took three days to respond to my query."

#### 💡 3 Action Ideas

1. **Add an exit load calculator** to the MF detail page for clarity.
2. **Optimize app startup** time and fix crash on portfolio page.
3. **Set up a 24-hour support** response SLA for billing issues.
"""

SAMPLE_FEE_DATA = {
    "fee_scenario": "Mutual Fund Exit Load",
    "explanation_bullets": [
        "Exit load is a redemption fee charged when mutual fund units are sold before a specified holding period.",
        "Exit load rates vary by fund: equity funds commonly charge 1% if redeemed within 1 year of purchase.",
        "The exit load is deducted from redemption proceeds; all terms are disclosed in the fund's Scheme Information Document (SID).",
    ],
    "source_links": [
        "https://groww.in/p/exit-load-in-mutual-funds",
        "https://mf.nipponindiaim.com/investoreducation/financial-term-of-the-week-exit-load",
    ],
    "last_checked": "2026-03-22",
}


@pytest.fixture
def fee_data():
    return SAMPLE_FEE_DATA.copy()


@pytest.fixture
def combined(tmp_path, fee_data, monkeypatch):
    import phase7_email.json_assembler as _mod
    monkeypatch.setattr(_mod, "_OUTPUT_DIR", tmp_path)
    return build_combined_json(SAMPLE_NOTE, fee_data, date="2026-03-22")


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — parse_note_sections()
# ─────────────────────────────────────────────────────────────────────────────

class TestParseNoteSections:
    def test_returns_dict_with_required_keys(self):
        result = parse_note_sections(SAMPLE_NOTE)
        for key in ("themes", "quotes", "action_ideas"):
            assert key in result, f"Missing key: {key}"

    def test_extracts_up_to_three_themes(self):
        result = parse_note_sections(SAMPLE_NOTE)
        assert 1 <= len(result["themes"]) <= 3, (
            f"Expected 1-3 themes, got {len(result['themes'])}: {result['themes']}"
        )

    def test_first_theme_label_correct(self):
        result = parse_note_sections(SAMPLE_NOTE)
        assert result["themes"][0] == "Fee Transparency", (
            f"Expected 'Fee Transparency', got '{result['themes'][0]}'"
        )

    def test_extracts_up_to_three_quotes(self):
        result = parse_note_sections(SAMPLE_NOTE)
        assert 1 <= len(result["quotes"]) <= 3

    def test_quote_text_content(self):
        result = parse_note_sections(SAMPLE_NOTE)
        joined = " ".join(result["quotes"])
        assert "exit load" in joined.lower() or "crashes" in joined.lower() or "support" in joined.lower()

    def test_extracts_up_to_three_action_ideas(self):
        result = parse_note_sections(SAMPLE_NOTE)
        assert 1 <= len(result["action_ideas"]) <= 3

    def test_action_ideas_are_non_empty(self):
        result = parse_note_sections(SAMPLE_NOTE)
        for idea in result["action_ideas"]:
            assert idea.strip(), "Action idea must not be empty"

    def test_empty_note_returns_empty_lists(self):
        result = parse_note_sections("")
        assert result["themes"] == []
        assert result["quotes"] == []
        assert result["action_ideas"] == []


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — build_combined_json() schema validation
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildCombinedJson:
    REQUIRED_TOP_KEYS = {
        "date",
        "weekly_pulse",
        "fee_scenario",
        "explanation_bullets",
        "source_links",
        "last_checked",
    }

    def test_returns_dict(self, combined):
        assert isinstance(combined, dict)

    def test_has_all_required_top_level_keys(self, combined):
        missing = self.REQUIRED_TOP_KEYS - combined.keys()
        assert not missing, f"Combined JSON is missing keys: {missing}"

    def test_date_field_correct(self, combined):
        assert combined["date"] == "2026-03-22"

    def test_weekly_pulse_has_required_sub_keys(self, combined):
        wp = combined["weekly_pulse"]
        for key in ("themes", "quotes", "action_ideas"):
            assert key in wp, f"weekly_pulse missing key: {key}"

    def test_weekly_pulse_themes_is_list(self, combined):
        assert isinstance(combined["weekly_pulse"]["themes"], list)

    def test_weekly_pulse_quotes_is_list(self, combined):
        assert isinstance(combined["weekly_pulse"]["quotes"], list)

    def test_weekly_pulse_action_ideas_is_list(self, combined):
        assert isinstance(combined["weekly_pulse"]["action_ideas"], list)

    def test_fee_scenario_value(self, combined):
        assert combined["fee_scenario"] == "Mutual Fund Exit Load"

    def test_explanation_bullets_count(self, combined):
        assert len(combined["explanation_bullets"]) == 3

    def test_source_links_count(self, combined):
        assert len(combined["source_links"]) == 2

    def test_source_links_are_approved(self, combined):
        approved = {
            "https://groww.in/p/exit-load-in-mutual-funds",
            "https://mf.nipponindiaim.com/investoreducation/financial-term-of-the-week-exit-load",
        }
        for url in combined["source_links"]:
            assert url in approved, f"Unapproved source URL in combined JSON: {url}"

    def test_last_checked_is_valid_date(self, combined):
        try:
            datetime.strptime(combined["last_checked"], "%Y-%m-%d")
        except ValueError:
            pytest.fail(f"last_checked is not a valid YYYY-MM-DD date: {combined['last_checked']}")

    def test_output_file_saved(self, tmp_path, fee_data, monkeypatch):
        import phase7_email.json_assembler as _mod
        monkeypatch.setattr(_mod, "_OUTPUT_DIR", tmp_path)
        build_combined_json(SAMPLE_NOTE, fee_data, date="2026-03-22")
        expected = tmp_path / "combined_pulse_2026-03-22.json"
        assert expected.exists(), f"Expected {expected} to exist"

    def test_output_file_is_valid_json(self, tmp_path, fee_data, monkeypatch):
        import phase7_email.json_assembler as _mod
        monkeypatch.setattr(_mod, "_OUTPUT_DIR", tmp_path)
        build_combined_json(SAMPLE_NOTE, fee_data, date="2026-03-22")
        path = tmp_path / "combined_pulse_2026-03-22.json"
        with open(path, "r", encoding="utf-8") as fh:
            loaded = json.load(fh)
        assert isinstance(loaded, dict)
        assert "weekly_pulse" in loaded

    def test_defaults_date_to_today(self, tmp_path, fee_data, monkeypatch):
        import phase7_email.json_assembler as _mod
        monkeypatch.setattr(_mod, "_OUTPUT_DIR", tmp_path)
        today = datetime.now().strftime("%Y-%m-%d")
        result = build_combined_json(SAMPLE_NOTE, fee_data)
        assert result["date"] == today


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 — _format_entry() (gdoc_mcp_appender)
# ─────────────────────────────────────────────────────────────────────────────

class TestFormatEntry:
    def test_returns_string(self, combined):
        entry = _format_entry(combined)
        assert isinstance(entry, str)

    def test_contains_date_header(self, combined):
        entry = _format_entry(combined)
        assert "──── 2026-03-22 ────" in entry

    def test_contains_json_fence(self, combined):
        entry = _format_entry(combined)
        assert "```json" in entry
        assert "```" in entry

    def test_contains_valid_json_block(self, combined):
        entry = _format_entry(combined)
        # Extract JSON from the fenced block
        match = re.search(r"```json\n(.+?)\n```", entry, re.DOTALL)
        assert match, "No ```json ... ``` block found in entry"
        json_str = match.group(1)
        loaded = json.loads(json_str)
        assert isinstance(loaded, dict)
        assert "weekly_pulse" in loaded

    def test_date_in_header_matches_combined_date(self, combined):
        entry = _format_entry(combined)
        assert combined["date"] in entry


# ─────────────────────────────────────────────────────────────────────────────
# Test 4 — append_to_gdoc()
# ─────────────────────────────────────────────────────────────────────────────

class TestAppendToGdoc:
    def test_returns_false_when_gdoc_id_not_set(self, combined, monkeypatch):
        monkeypatch.delenv("GDOC_ID", raising=False)
        result = append_to_gdoc(combined, doc_id="")
        assert result is False

    def test_returns_true_when_gdoc_id_provided(self, combined, monkeypatch):
        monkeypatch.setenv("GDOC_ID", "fake-doc-id-12345")
        result = append_to_gdoc(combined, doc_id="fake-doc-id-12345")
        assert result is True

    def test_returns_true_with_env_gdoc_id(self, combined, monkeypatch):
        monkeypatch.setenv("GDOC_ID", "env-doc-id-abc")
        result = append_to_gdoc(combined)
        assert result is True

    def test_logs_warning_when_no_doc_id(self, combined, monkeypatch, caplog):
        monkeypatch.delenv("GDOC_ID", raising=False)
        import logging
        with caplog.at_level(logging.WARNING, logger="phase7_email.gdoc_mcp_appender"):
            append_to_gdoc(combined, doc_id="")
        assert any("GDOC_ID" in record.message for record in caplog.records)

    def test_handles_exception_gracefully(self, combined, monkeypatch):
        monkeypatch.setenv("GDOC_ID", "some-doc-id")
        # Simulate an exception inside the try block
        with patch(
            "phase7_email.gdoc_mcp_appender._format_entry",
            side_effect=RuntimeError("MCP failure"),
        ):
            result = append_to_gdoc(combined, doc_id="some-doc-id")
        assert result is False


# ─────────────────────────────────────────────────────────────────────────────
# Test 5 — Package-level imports
# ─────────────────────────────────────────────────────────────────────────────

class TestPackageImports:
    def test_build_combined_json_importable(self):
        import phase7_email
        assert hasattr(phase7_email, "build_combined_json")
        assert callable(phase7_email.build_combined_json)

    def test_append_to_gdoc_importable(self):
        import phase7_email
        assert hasattr(phase7_email, "append_to_gdoc")
        assert callable(phase7_email.append_to_gdoc)

    def test_all_exports_present(self):
        import phase7_email
        for name in ["send_email", "generate_email_html", "generate_fee_explanation",
                     "build_combined_json", "append_to_gdoc"]:
            assert hasattr(phase7_email, name), f"Missing export: {name}"
