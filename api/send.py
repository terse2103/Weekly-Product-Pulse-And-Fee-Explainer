"""
api/send.py — Vercel Serverless Function (Python)
==================================================
Handles POST /api/send requests from the Vercel static frontend.
- Fetches the latest weekly note from GitHub Raw (no local disk read).
- Sends the email directly via SMTP using environment variables.
- No FastAPI/uvicorn needed — Vercel calls this as a plain HTTP handler.
"""

import json
import os
import re
import smtplib
import ssl
import urllib.request
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from http.server import BaseHTTPRequestHandler

GITHUB_RAW_URL = (
    "https://raw.githubusercontent.com/"
    "terse2103/Weekly-Product-Pulse-And-Fee-Explainer/"
    "master/output/latest_note.json"
)


def _markdown_to_plain(md: str) -> str:
    """Strip markdown to plain text for email body fallback."""
    text = re.sub(r"#{1,6}\s+", "", md)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    return text.strip()


def _send_smtp(html_body: str, subject: str, recipient_name: str, recipient_email: str) -> None:
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = f"{recipient_name} <{recipient_email}>"
    msg["Date"] = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")

    plain = _markdown_to_plain(re.sub(r"<[^>]+>", "", html_body))
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls(context=context)
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, recipient_email, msg.as_string())


class handler(BaseHTTPRequestHandler):
    """Plain WSGI-style handler that Vercel invokes for /api/send."""

    def do_OPTIONS(self):
        """CORS preflight."""
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            body = json.loads(raw)
            recipient_name  = body.get("recipient_name", "").strip()
            recipient_email = body.get("recipient_email", "").strip()

            if not recipient_name or not recipient_email:
                return self._error(400, "recipient_name and recipient_email are required.")

            # ── Fetch note from GitHub Raw ────────────────────────────────
            with urllib.request.urlopen(GITHUB_RAW_URL, timeout=10) as resp:
                note_data = json.loads(resp.read().decode())
            markdown = note_data.get("markdown", "")
            if not markdown:
                return self._error(404, "No weekly note found. Run the Streamlit pipeline first.")

            # ── Build HTML email body ─────────────────────────────────────
            html_body = f"""
            <html><body style="font-family:sans-serif;max-width:680px;margin:auto;color:#1a1a2e">
              <h2 style="color:#6c6bd8">📋 INDMoney Weekly Product Pulse</h2>
              <p>Hi {recipient_name},</p>
              <div style="background:#f4f4f8;padding:20px;border-radius:8px;white-space:pre-wrap">{markdown}</div>
              <hr/>
              <p style="font-size:12px;color:#999">Generated automatically — Weekly Pulse Admin Panel</p>
            </body></html>
            """
            subject = f"📋 INDMoney Weekly Product Pulse — {datetime.utcnow().strftime('%B %d, %Y')}"

            # ── Send via SMTP ──────────────────────────────────────────────
            _send_smtp(html_body, subject, recipient_name, recipient_email)

            self._json(200, {"status": "sent", "message": f"Weekly Pulse shipped to {recipient_email}!"})

        except KeyError as e:
            self._error(500, f"Missing environment variable: {e}. Set SMTP_HOST, SMTP_USER, SMTP_PASS in Vercel settings.")
        except Exception as exc:
            self._error(500, str(exc))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

    def _json(self, code: int, data: dict):
        payload = json.dumps(data).encode()
        self.send_response(code)
        self._cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _error(self, code: int, detail: str):
        self._json(code, {"detail": detail})
