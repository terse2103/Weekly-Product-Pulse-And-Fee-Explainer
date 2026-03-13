"""
phase7_email/smtp_client.py
============================
SMTP fallback for Phase 7 email delivery.

Delivers the HTML email via any SMTP server (e.g. Gmail SMTP, Outlook, etc.)
using Python's built-in smtplib — no extra dependencies required.

Environment variables (set in .env or system env):
  SMTP_HOST  — e.g.  smtp.gmail.com
  SMTP_PORT  — e.g.  587   (default: 587 for STARTTLS)
  SMTP_USER  — sender email address
  SMTP_PASS  — app password or OAuth token

For Gmail SMTP:
  1. Enable 2-Step Verification in your Google Account.
  2. Generate an App Password (Security → App Passwords).
  3. Use the 16-character app password as SMTP_PASS.
"""

import logging
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

_DEFAULT_SMTP_PORT = 587


def send_via_smtp(
    html_body: str,
    subject: str,
    recipient_name: str,
    recipient_email: str,
    smtp_host: str = "",
    smtp_user: str = "",
    smtp_pass: str = "",
    smtp_port: int | None = None,
) -> None:
    """
    Send an HTML email via SMTP (STARTTLS).

    Parameters
    ----------
    html_body        : str — Fully rendered HTML string.
    subject          : str — Email subject line.
    recipient_name   : str — Recipient display name.
    recipient_email  : str — Recipient email address.
    smtp_host        : str — SMTP server hostname. Falls back to SMTP_HOST env var.
    smtp_user        : str — SMTP username. Falls back to SMTP_USER env var.
    smtp_pass        : str — SMTP password. Falls back to SMTP_PASS env var.
    smtp_port        : int — SMTP port. Falls back to SMTP_PORT env var, then 587.

    Raises
    ------
    ValueError   — if required SMTP credentials are missing.
    smtplib.SMTPException — on delivery failure.
    """
    # ── Resolve credentials ──────────────────────────────────────────────────
    host = smtp_host or os.environ.get("SMTP_HOST", "")
    user = smtp_user or os.environ.get("SMTP_USER", "")
    password = smtp_pass or os.environ.get("SMTP_PASS", "")
    port_env = os.environ.get("SMTP_PORT", str(_DEFAULT_SMTP_PORT))
    port = smtp_port or int(port_env)

    if not host or not user or not password:
        raise ValueError(
            "SMTP credentials incomplete. "
            "Set SMTP_HOST, SMTP_USER, and SMTP_PASS environment variables."
        )

    # ── Build MIME message ───────────────────────────────────────────────────
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = f"{recipient_name} <{recipient_email}>"

    # Plain-text fallback
    plain = re.sub(r"<[^>]+>", "", html_body)
    plain = re.sub(r"\n{3,}", "\n\n", plain).strip()

    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # ── Send ─────────────────────────────────────────────────────────────────
    logger.info(f"[SMTP] Connecting to {host}:{port} as {user}")
    with smtplib.SMTP(host, port) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(user, password)
        server.sendmail(user, [recipient_email], msg.as_string())

    logger.info(f"[SMTP] Email delivered to {recipient_email}")
