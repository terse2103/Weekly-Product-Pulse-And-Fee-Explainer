"""
phase6_web_ui/tests/test_web.py
================================
Pytest test suite for Phase 6 — FastAPI Backend.

Tests cover:
  • GET  /api/note     → returns note JSON when note exists; 404 when not
  • POST /api/send     → happy-path and validation-error cases
  • GET  /api/status   → returns expected status fields
  • POST /api/run      → start background pipeline
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

import api_server
api_server._run_pipeline_task = lambda: None  # mock background logic to prevent tests hanging

import os
if "SMTP_HOST" in os.environ:
    del os.environ["SMTP_HOST"]

from api_server import api, get_latest_note, OUTPUT_DIR, _status

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Return a TestClient wrapping the FastAPI app."""
    return TestClient(api, raise_server_exceptions=True)

@pytest.fixture(autouse=True)
def reset_status():
    _status["status"] = "idle"
    _status["last_run"] = None
    _status["last_note_file"] = None
    _status["sent_count"] = 0
    yield

@pytest.fixture()
def sample_note_file(tmp_path, monkeypatch):
    """
    Create a temporary weekly note file and redirect OUTPUT_DIR to tmp_path.
    """
    note_content = (
        "### 5th March, 2026 to 12th March, 2026\n"
        "#### Top 3 Themes\n"
        "* **User Experience** (129 reviews): Users love the interface.\n"
        "\n"
        "#### User Quotes\n"
        '> "Great app overall!"\n'
    )
    note_file = tmp_path / "weekly_note_2026-03-12.md"
    note_file.write_text(note_content, encoding="utf-8")

    import api_server as app_module
    monkeypatch.setattr(app_module, "OUTPUT_DIR", tmp_path)

    yield note_file

# ---------------------------------------------------------------------------
# 1. GET /api/note
# ---------------------------------------------------------------------------

class TestGetNote:

    def test_returns_note_json_when_note_exists(self, client, sample_note_file):
        response = client.get("/api/note")
        assert response.status_code == 200
        data = response.json()
        assert "markdown" in data
        assert "date" in data
        assert "filename" in data
        assert "word_count" in data

    def test_404_when_no_note_exists(self, client, monkeypatch):
        import api_server as app_module
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
        with patch("phase7_email.email_generator.send_email", return_value=("smtp", "Email sent via SMTP to priya@company.com.")):
            response = client.post("/api/send", json=self.VALID_PAYLOAD)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "sent"
            assert "Email delivered" in data["message"]

    def test_fallback_returns_502_error(self, client, sample_note_file):
        with patch("phase7_email.email_generator.send_email", return_value=("fallback", "Draft saved locally due to timeout.")):
            response = client.post("/api/send", json=self.VALID_PAYLOAD)
            assert response.status_code == 502
            data = response.json()
            assert "Draft saved locally" in data["detail"]

    def test_invalid_email_returns_422(self, client, sample_note_file):
        response = client.post("/api/send", json={
            "recipient_name": "Test User",
            "recipient_email": "not-an-email",
        })
        assert response.status_code == 422

# ---------------------------------------------------------------------------
# 4. GET /api/status — Pipeline status
# ---------------------------------------------------------------------------

class TestGetStatus:

    def test_returns_200(self, client):
        response = client.get("/api/status")
        assert response.status_code == 200

    def test_status_field_valid_value(self, client):
        data = client.get("/api/status").json()
        assert data["status"] in {"idle", "running", "error"}

class TestRunPipeline:
    def test_trigger_run(self, client):
        response = client.post("/api/run")
        assert response.status_code == 200
        assert response.json()["status"] == "started"

    def test_trigger_run_conflict(self, client):
        _status["status"] = "running"
        response = client.post("/api/run")
        assert response.status_code == 409
