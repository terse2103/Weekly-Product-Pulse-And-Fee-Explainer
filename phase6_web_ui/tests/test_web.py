"""
phase6_web_ui/tests/test_web.py
================================
Pytest test suite for Phase 6 — Web UI & Backend.

Tests cover:
  • GET  /             → returns HTML UI page
  • GET  /api/note     → returns note JSON when note exists; 404 when not
  • POST /api/send     → happy-path and validation-error cases
  • GET  /api/status   → returns expected status fields
  • Form validation    → handled via API-layer Pydantic errors
"""

import os
import json
import glob
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Ensure we can import from the project root
# ---------------------------------------------------------------------------
import sys
ROOT = Path(__file__).resolve().parents[2]  # …/Weekly Product Pulse and Fee Explainer
sys.path.insert(0, str(ROOT))

from phase6_web_ui.app import app, _get_latest_note, OUTPUT_DIR


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Return a TestClient wrapping the FastAPI app."""
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def sample_note_file(tmp_path, monkeypatch):
    """
    Create a temporary weekly note file and redirect OUTPUT_DIR to tmp_path.
    Yields the Path to the created note file.
    """
    note_content = (
        "### 5th March, 2026 to 12th March, 2026\n"
        "#### Top 3 Themes\n"
        "* **User Experience** (129 reviews): Users love the interface.\n"
        "* **App Performance** (87 reviews): Fast loading times praised.\n"
        "* **Customer Support** (38 reviews): Quick responses valued.\n"
        "\n"
        "#### User Quotes\n"
        '> "Great app overall!"\n'
        '> "Blazing fast UI, well done."\n'
        '> "Support resolved my issue in 10 minutes."\n'
        "\n"
        "#### Actionable Recommendations\n"
        "* **Improve** onboarding flow.\n"
        "* **Optimise** background sync.\n"
        "* **Expand** support team hours.\n"
    )
    note_file = tmp_path / "weekly_note_2026-03-12.md"
    note_file.write_text(note_content, encoding="utf-8")

    # Patch the module-level OUTPUT_DIR so _get_latest_note reads from tmp_path
    import phase6_web_ui.app as app_module
    monkeypatch.setattr(app_module, "OUTPUT_DIR", tmp_path)

    yield note_file


# ---------------------------------------------------------------------------
# 1. GET / — Serve static HTML UI
# ---------------------------------------------------------------------------

class TestServeUI:

    def test_serves_html_page(self, client):
        """GET / should return 200 with HTML content."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_html_contains_key_elements(self, client):
        """The served HTML must contain the core UI elements."""
        response = client.get("/")
        body = response.text
        assert "INDMoney Weekly Product Pulse" in body, "Page title missing"
        assert "send-form" in body,   "Send form element missing"
        assert "recipient-name" in body,  "Recipient name field missing"
        assert "recipient-email" in body, "Recipient email field missing"
        assert "btn-send" in body,    "Send button missing"
        assert "/static/script.js" in body, "script.js reference missing"
        assert "/static/style.css" in body, "style.css reference missing"

    def test_swagger_docs_accessible(self, client):
        """Auto-generated /docs must return 200."""
        response = client.get("/docs")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# 2. GET /api/note — Return latest weekly note
# ---------------------------------------------------------------------------

class TestGetNote:

    def test_returns_note_json_when_note_exists(self, client, sample_note_file):
        """Should return 200 with note fields when a note file exists."""
        response = client.get("/api/note")
        assert response.status_code == 200
        data = response.json()
        assert "markdown" in data,    "'markdown' field missing"
        assert "date" in data,        "'date' field missing"
        assert "filename" in data,    "'filename' field missing"
        assert "word_count" in data,  "'word_count' field missing"

    def test_note_markdown_is_non_empty(self, client, sample_note_file):
        """Markdown content must be a non-empty string."""
        response = client.get("/api/note")
        assert response.status_code == 200
        assert len(response.json()["markdown"]) > 0

    def test_note_date_matches_filename(self, client, sample_note_file):
        """Date extracted from filename should match the 'date' field."""
        response = client.get("/api/note")
        assert response.status_code == 200
        assert response.json()["date"] == "2026-03-12"

    def test_note_filename_returned_correctly(self, client, sample_note_file):
        """Filename field should match the fixture file name."""
        response = client.get("/api/note")
        assert response.json()["filename"] == "weekly_note_2026-03-12.md"

    def test_word_count_is_positive_integer(self, client, sample_note_file):
        """Word count should be a positive integer."""
        response = client.get("/api/note")
        wc = response.json()["word_count"]
        assert isinstance(wc, int)
        assert wc > 0

    def test_404_when_no_note_exists(self, client, monkeypatch):
        """Should return 404 when no note file is present."""
        import phase6_web_ui.app as app_module
        # Point OUTPUT_DIR to a location with no files
        monkeypatch.setattr(app_module, "OUTPUT_DIR", Path("/non/existent/path"))
        response = client.get("/api/note")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# 3. POST /api/send — Trigger email delivery
# ---------------------------------------------------------------------------

class TestSendNote:

    VALID_PAYLOAD = {
        "recipient_name": "Priya Sharma",
        "recipient_email": "priya@company.com",
    }

    def test_happy_path_returns_sent_status(self, client, sample_note_file):
        """Valid payload should return status='sent' and a descriptive message."""
        response = client.post("/api/send", json=self.VALID_PAYLOAD)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sent"
        assert "priya@company.com" in data["message"] or "sent" in data["message"].lower()

    def test_response_contains_recipient_email(self, client, sample_note_file):
        """The response message should reference the recipient's email."""
        response = client.post("/api/send", json=self.VALID_PAYLOAD)
        assert "priya@company.com" in response.json()["message"]

    def test_invalid_email_returns_422(self, client, sample_note_file):
        """Pydantic should reject a malformed email address with 422."""
        response = client.post("/api/send", json={
            "recipient_name": "Test User",
            "recipient_email": "not-an-email",
        })
        assert response.status_code == 422

    def test_missing_name_returns_422(self, client, sample_note_file):
        """Missing recipient_name should cause a 422 validation error."""
        response = client.post("/api/send", json={
            "recipient_email": "priya@company.com",
        })
        assert response.status_code == 422

    def test_missing_email_returns_422(self, client, sample_note_file):
        """Missing recipient_email should cause a 422 validation error."""
        response = client.post("/api/send", json={
            "recipient_name": "Priya Sharma",
        })
        assert response.status_code == 422

    def test_missing_body_returns_422(self, client, sample_note_file):
        """Completely missing body should cause a 422 validation error."""
        response = client.post("/api/send")
        assert response.status_code == 422

    def test_404_when_no_note_to_send(self, client, monkeypatch):
        """Should return 404 if no note has been generated yet."""
        import phase6_web_ui.app as app_module
        monkeypatch.setattr(app_module, "OUTPUT_DIR", Path("/non/existent/path"))
        response = client.post("/api/send", json=self.VALID_PAYLOAD)
        assert response.status_code == 404

    def test_different_recipients_accepted(self, client, sample_note_file):
        """Multiple different recipients should each return 200."""
        recipients = [
            {"recipient_name": "Alice", "recipient_email": "alice@example.com"},
            {"recipient_name": "Bob",   "recipient_email": "bob@example.com"},
        ]
        for payload in recipients:
            res = client.post("/api/send", json=payload)
            assert res.status_code == 200, f"Failed for {payload['recipient_email']}"


# ---------------------------------------------------------------------------
# 4. GET /api/status — Pipeline status
# ---------------------------------------------------------------------------

class TestGetStatus:

    def test_returns_200(self, client):
        """Status endpoint must always return 200."""
        response = client.get("/api/status")
        assert response.status_code == 200

    def test_response_contains_required_fields(self, client):
        """Status response must include the four documented fields."""
        data = client.get("/api/status").json()
        assert "status" in data
        assert "last_run" in data
        assert "last_note_file" in data
        assert "sent_count" in data

    def test_status_field_valid_value(self, client):
        """The 'status' field must be one of the accepted values."""
        data = client.get("/api/status").json()
        assert data["status"] in {"idle", "running", "completed", "failed"}

    def test_sent_count_increments_after_send(self, client, sample_note_file):
        """sent_count should increase after a successful /api/send call."""
        initial = client.get("/api/status").json()["sent_count"]
        client.post("/api/send", json={
            "recipient_name": "Test User",
            "recipient_email": "test@example.com",
        })
        updated = client.get("/api/status").json()["sent_count"]
        assert updated == initial + 1

    def test_last_note_file_reflects_note_presence(self, client, sample_note_file):
        """After loading a note, last_note_file should be populated."""
        client.get("/api/note")  # trigger the note to be cached
        data = client.get("/api/status").json()
        assert data["last_note_file"] == "weekly_note_2026-03-12.md"


# ---------------------------------------------------------------------------
# 5. Static file serving
# ---------------------------------------------------------------------------

class TestStaticFiles:

    def test_stylesheet_is_served(self, client):
        """style.css must be accessible at /static/style.css."""
        response = client.get("/static/style.css")
        assert response.status_code == 200
        assert "text/css" in response.headers.get("content-type", "")

    def test_javascript_is_served(self, client):
        """script.js must be accessible at /static/script.js."""
        response = client.get("/static/script.js")
        assert response.status_code == 200
        ct = response.headers.get("content-type", "")
        assert "javascript" in ct or "text" in ct
