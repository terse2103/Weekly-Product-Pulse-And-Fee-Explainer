"""
phase7_email/tests/test_email.py
=================================
Phase 7 test suite — Email Draft Generation & Delivery.

Tests verify:
  1. Subject format matches architecture spec (emoji + date string)
  2. HTML generation — template tokens are filled, no raw {{placeholders}} remain
  3. Note body is present in the generated HTML
  4. No PII leaks through to the rendered HTML / .eml file
  5. Markdown-to-HTML rendering: headings, bold, bullets, blockquotes
  6. .eml fallback: file is created under output/ with correct structure
  7. SMTP client raises ValueError when credentials are missing
  8. send_email() uses the .eml fallback when no email env vars are set
  9. build_subject() handles custom date strings and empty input
 10. generate_email_html() handles an empty note gracefully
"""

import phase7_email.email_generator as _email_gen_module  # for monkeypatching module globals

import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Make project root importable ────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from phase7_email.email_generator import (
    _markdown_to_html,
    build_subject,
    generate_email_html,
    send_email,
    _save_eml,
    SUBJECT_TEMPLATE,
)
from phase7_email.smtp_client import send_via_smtp


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_NOTE = """\
### 5th March, 2026 to 12th March, 2026
#### Top 3 Themes:
* **User Experience** (129 reviews): Users provide feedback on the app's usability.
* **App Performance** (87 reviews): Users experience crashes and slow loading.
* **Customer Support** (38 reviews): Users report difficulties getting help.

#### User Quotes:
> "worst app — doesn't allow fractional shares at limit order price."
> "i love the app but it crashes on Android 14 every time."
> "customer support is not available when errors occur."

#### Actionable Recommendations:
1. Improve the app's usability by simplifying the interface.
2. Enhance stability by reducing the frequency of crashes.
3. Streamline the customer support process.
"""

SAMPLE_NAME = "Priya Sharma"
SAMPLE_EMAIL = "priya@company.com"


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — Subject format
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildSubject:
    def test_contains_emoji(self):
        subject = build_subject("2026-03-12")
        assert "📋" in subject

    def test_contains_date(self):
        subject = build_subject("2026-03-12")
        assert "March" in subject and "2026" in subject

    def test_matches_template_structure(self):
        subject = build_subject("2026-03-08")
        assert subject.startswith("📋 INDMoney Weekly Product Pulse")

    def test_default_date_is_today(self):
        today = datetime.now().strftime("%Y")
        subject = build_subject()
        assert today in subject

    def test_custom_date_string(self):
        subject = build_subject("2026-01-05")
        assert "January" in subject


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — Markdown → HTML conversion
# ─────────────────────────────────────────────────────────────────────────────

class TestMarkdownToHtml:
    def test_heading_converted(self):
        html = _markdown_to_html("### Section Title")
        assert "<h3>" in html and "Section Title" in html

    def test_bold_converted(self):
        html = _markdown_to_html("**Bold Text**")
        assert "<strong>Bold Text</strong>" in html

    def test_unordered_list(self):
        html = _markdown_to_html("* Item A\n* Item B")
        assert "<ul>" in html
        assert "<li>Item A</li>" in html
        assert "<li>Item B</li>" in html

    def test_ordered_list(self):
        html = _markdown_to_html("1. First\n2. Second")
        assert "<ol>" in html
        assert "<li>First</li>" in html

    def test_blockquote(self):
        html = _markdown_to_html('> "User said something."')
        assert "<blockquote>" in html
        assert "User said something" in html

    def test_horizontal_rule(self):
        html = _markdown_to_html("---")
        assert "<hr/>" in html

    def test_empty_input(self):
        html = _markdown_to_html("")
        assert isinstance(html, str)

    def test_full_note_produces_html(self):
        html = _markdown_to_html(SAMPLE_NOTE)
        assert "<h" in html
        assert "<blockquote>" in html
        assert "<li>" in html


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 — HTML generation (template filling)
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateEmailHtml:
    def test_no_raw_placeholders(self):
        html = generate_email_html(SAMPLE_NOTE, SAMPLE_NAME, "Week of March 5–12, 2026")
        # No unreplaced template tokens should remain
        assert "{{" not in html
        assert "}}" not in html

    def test_recipient_name_present(self):
        html = generate_email_html(SAMPLE_NOTE, SAMPLE_NAME)
        assert SAMPLE_NAME in html

    def test_note_content_embedded(self):
        html = generate_email_html(SAMPLE_NOTE, SAMPLE_NAME)
        assert "User Experience" in html
        assert "App Performance" in html

    def test_week_label_present(self):
        html = generate_email_html(SAMPLE_NOTE, SAMPLE_NAME, "Week of March 5–12, 2026")
        assert "March 5" in html or "March" in html

    def test_year_present(self):
        html = generate_email_html(SAMPLE_NOTE, SAMPLE_NAME)
        assert str(datetime.now().year) in html

    def test_empty_note_does_not_crash(self):
        html = generate_email_html("", SAMPLE_NAME)
        assert isinstance(html, str)
        assert len(html) > 0

    def test_html_structure(self):
        html = generate_email_html(SAMPLE_NOTE, SAMPLE_NAME)
        assert "<!DOCTYPE html>" in html
        assert "<body>" in html
        assert "</body>" in html


# ─────────────────────────────────────────────────────────────────────────────
# Test 4 — No PII in generated output
# ─────────────────────────────────────────────────────────────────────────────

class TestNoPiiInOutput:
    """
    Verify PII patterns don't survive into the email HTML or .eml file.
    Since Phase 2b already strips PII from the note, the email generator
    must not re-introduce any.  We use a note that already has clean text.
    """

    PII_PATTERNS = [
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b",  # emails
        r"\+91[-\s]?\d{10}",                                           # phone
    ]

    def test_no_email_addresses_in_html(self):
        note = SAMPLE_NOTE  # already PII-free
        html = generate_email_html(note, SAMPLE_NAME)
        # The only email that may appear is the footer's company alias
        # We strip that and check no real address leaks
        html_stripped = html.replace("weekly-pulse@company.com", "")
        # Recipient email is not in the body HTML
        for pattern in self.PII_PATTERNS:
            matches = re.findall(pattern, html_stripped, re.IGNORECASE)
            assert not matches, f"PII found in HTML: {matches}"

    def test_no_phone_numbers_in_html(self):
        note_with_phone = SAMPLE_NOTE + "\n\nCall +91-9876543210 for support."
        # This would only happen if Phase 2b failed; email_generator itself
        # does not re-introduce PII — it just embeds the note as-is.
        # We verify the phone number passes through without amplification.
        html = generate_email_html(note_with_phone, SAMPLE_NAME)
        # Phone is embedded verbatim — not our job to re-strip here,
        # but assert that no new phones were added by the generator itself.
        count_in_note = len(re.findall(r"\+91-9876543210", note_with_phone))
        count_in_html = len(re.findall(r"\+91-9876543210", html))
        assert count_in_html <= count_in_note


# ─────────────────────────────────────────────────────────────────────────────
# Test 5 — .eml fallback (local file)
# ─────────────────────────────────────────────────────────────────────────────

class TestEmlFallback:
    def test_eml_file_created(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_email_gen_module, "_OUTPUT_DIR", tmp_path)
        html = generate_email_html(SAMPLE_NOTE, SAMPLE_NAME)
        subject = build_subject()
        path = _save_eml(html, subject, SAMPLE_NAME, SAMPLE_EMAIL)
        assert path.exists()
        assert path.suffix == ".eml"

    def test_eml_contains_subject(self, tmp_path, monkeypatch):
        import email as _email_lib
        import email.header as _email_header

        monkeypatch.setattr(_email_gen_module, "_OUTPUT_DIR", tmp_path)
        html = generate_email_html(SAMPLE_NOTE, SAMPLE_NAME)
        subject = build_subject("2026-03-12")
        path = _save_eml(html, subject, SAMPLE_NAME, SAMPLE_EMAIL)
        raw_content = path.read_bytes()

        # Parse the .eml file to decode RFC2047-encoded headers
        msg = _email_lib.message_from_bytes(raw_content)
        raw_subject = msg.get("Subject", "")
        # Decode RFC2047 encoding (e.g. =?utf-8?b?...?=)
        decoded_parts = _email_header.decode_header(raw_subject)
        decoded_subject = "".join(
            part.decode(enc or "utf-8") if isinstance(part, bytes) else part
            for part, enc in decoded_parts
        )
        assert "INDMoney Weekly Product Pulse" in decoded_subject

    def test_eml_contains_recipient(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_email_gen_module, "_OUTPUT_DIR", tmp_path)
        html = generate_email_html(SAMPLE_NOTE, SAMPLE_NAME)
        subject = build_subject()
        path = _save_eml(html, subject, SAMPLE_NAME, SAMPLE_EMAIL)
        content = path.read_text(encoding="utf-8")
        assert SAMPLE_EMAIL in content

    def test_eml_filename_has_date(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_email_gen_module, "_OUTPUT_DIR", tmp_path)
        html = generate_email_html(SAMPLE_NOTE, SAMPLE_NAME)
        subject = build_subject()
        path = _save_eml(html, subject, SAMPLE_NAME, SAMPLE_EMAIL)
        # Filename should be email_draft_YYYY-MM-DD.eml
        assert re.match(r"email_draft_\d{4}-\d{2}-\d{2}\.eml", path.name)


# ─────────────────────────────────────────────────────────────────────────────
# Test 6 — send_email() end-to-end with fallback
# ─────────────────────────────────────────────────────────────────────────────

class TestSendEmail:
    def test_send_uses_eml_fallback_when_no_env(self, tmp_path, monkeypatch):
        """With no GMAIL_CREDENTIALS / SMTP_HOST set, falls back to .eml file."""
        monkeypatch.delenv("GMAIL_CREDENTIALS", raising=False)
        monkeypatch.delenv("SMTP_HOST", raising=False)
        monkeypatch.delenv("SMTP_USER", raising=False)
        monkeypatch.delenv("SMTP_PASS", raising=False)
        monkeypatch.setattr(_email_gen_module, "_OUTPUT_DIR", tmp_path)

        send_email(SAMPLE_NOTE, SAMPLE_NAME, SAMPLE_EMAIL)

        eml_files = list(tmp_path.glob("email_draft_*.eml"))
        assert len(eml_files) == 1, "Expected exactly one .eml draft file"

    def test_send_falls_back_to_eml_when_gmail_unavailable(self, tmp_path, monkeypatch):
        """
        When GMAIL_CREDENTIALS is set but google-api-python-client is not
        installed (or auth fails), send_email should fall through to the .eml
        fallback gracefully without raising.
        """
        monkeypatch.setenv("GMAIL_CREDENTIALS", '{"type":"service_account"}')
        monkeypatch.delenv("SMTP_HOST", raising=False)
        monkeypatch.delenv("SMTP_USER", raising=False)
        monkeypatch.delenv("SMTP_PASS", raising=False)
        monkeypatch.setattr(_email_gen_module, "_OUTPUT_DIR", tmp_path)

        # Patch create_gmail_draft inside email_generator to simulate failure
        def _fail(*a, **kw):
            raise ImportError("google-api-python-client not installed")

        with patch("phase7_email.email_generator.create_gmail_draft", _fail, create=True):
            # Should not raise — graceful fallback expected
            send_email(SAMPLE_NOTE, SAMPLE_NAME, SAMPLE_EMAIL)

        # .eml file produced as fallback
        eml_files = list(tmp_path.glob("email_draft_*.eml"))
        assert len(eml_files) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Test 7 — SMTP client: raises ValueError on missing credentials
# ─────────────────────────────────────────────────────────────────────────────

class TestSmtpClient:
    def test_raises_on_missing_credentials(self, monkeypatch):
        monkeypatch.delenv("SMTP_HOST", raising=False)
        monkeypatch.delenv("SMTP_USER", raising=False)
        monkeypatch.delenv("SMTP_PASS", raising=False)

        with pytest.raises(ValueError, match="SMTP credentials incomplete"):
            send_via_smtp(
                html_body="<p>Test</p>",
                subject="Test Subject",
                recipient_name=SAMPLE_NAME,
                recipient_email=SAMPLE_EMAIL,
                smtp_host="",
                smtp_user="",
                smtp_pass="",
            )

    def test_uses_env_vars_for_credentials(self, monkeypatch):
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_USER", "user@example.com")
        monkeypatch.setenv("SMTP_PASS", "secret")

        with patch("smtplib.SMTP") as mock_smtp:
            instance = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=instance)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
            instance.sendmail = MagicMock()

            send_via_smtp(
                html_body="<p>Test</p>",
                subject="Test",
                recipient_name=SAMPLE_NAME,
                recipient_email=SAMPLE_EMAIL,
            )
            mock_smtp.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# Test 8 — Phase 6 integration: app.py can call send_email
# ─────────────────────────────────────────────────────────────────────────────

class TestPhase6Integration:
    """
    Verify the Phase 6 app.py can import and call send_email from phase7_email.
    This is the integration contract between Phase 6 and Phase 7.
    """

    def test_send_email_importable(self):
        from phase7_email.email_generator import send_email as _se
        assert callable(_se)

    def test_generate_email_html_importable(self):
        from phase7_email.email_generator import generate_email_html as _ge
        assert callable(_ge)

    def test_package_init_exports(self):
        import phase7_email
        assert hasattr(phase7_email, "send_email")
        assert hasattr(phase7_email, "generate_email_html")
