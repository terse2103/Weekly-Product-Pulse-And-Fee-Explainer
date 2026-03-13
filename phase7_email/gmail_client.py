"""
phase7_email/gmail_client.py
============================
Gmail API integration — creates an email draft in the sender's Gmail Drafts.

Prereqs
-------
1. Install:  pip install google-api-python-client google-auth-oauthlib
2. Set the GMAIL_CREDENTIALS env var to a path pointing to a valid
   credentials.json (OAuth2 client secrets from Google Cloud Console)
   OR to the JSON content of a service-account key with domain-wide delegation.

OAuth2 consent is required on first run; the token is cached in
~/.weekly_pulse_gmail_token.json.

The draft is created in the Gmail account that performed the OAuth2 login.
"""

import base64
import json
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

logger = logging.getLogger(__name__)

_TOKEN_PATH = Path.home() / ".weekly_pulse_gmail_token.json"
_SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


def _get_credentials():
    """
    Return valid Gmail OAuth2 credentials.
    Loads from the cached token file if available; otherwise runs the
    OAuth2 flow (browser pop-up / device flow).
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
    except ImportError as exc:
        raise ImportError(
            "Gmail API client libraries not installed. "
            "Run: pip install google-api-python-client google-auth-oauthlib"
        ) from exc

    creds = None
    gmail_creds_env = os.environ.get("GMAIL_CREDENTIALS", "")

    # ── Load from token cache ────────────────────────────────────────────────
    if _TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), _SCOPES)

    # ── Refresh or re-authorise ──────────────────────────────────────────────
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Determine credentials source: env var can be a file path or JSON
            if os.path.isfile(gmail_creds_env):
                client_secrets_file = gmail_creds_env
            else:
                # Write env var JSON content to a temp file for the flow
                import tempfile
                tmp = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".json", delete=False
                )
                tmp.write(gmail_creds_env)
                tmp.close()
                client_secrets_file = tmp.name

            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_file, _SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Cache the token
        _TOKEN_PATH.write_text(creds.to_json())

    return creds


def create_gmail_draft(
    html_body: str,
    subject: str,
    recipient_name: str,
    recipient_email: str,
    sender_alias: str = "me",
) -> dict:
    """
    Create a Gmail draft with the given HTML body.

    Parameters
    ----------
    html_body        : str — Fully rendered HTML string.
    subject          : str — Email subject line.
    recipient_name   : str — Recipient display name.
    recipient_email  : str — Recipient email address.
    sender_alias     : str — Gmail sender ('me' = authenticated account).

    Returns
    -------
    dict — Gmail API draft resource (contains 'id', 'message', etc.)
    """
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise ImportError(
            "google-api-python-client not installed. "
            "Run: pip install google-api-python-client"
        ) from exc

    creds = _get_credentials()
    service = build("gmail", "v1", credentials=creds)

    # ── Build the MIME message ───────────────────────────────────────────────
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_alias
    msg["To"] = f"{recipient_name} <{recipient_email}>"

    import re
    plain = re.sub(r"<[^>]+>", "", html_body)
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # ── Encode and create draft ──────────────────────────────────────────────
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    draft_body = {"message": {"raw": raw}}

    draft = (
        service.users()
        .drafts()
        .create(userId="me", body=draft_body)
        .execute()
    )
    logger.info(f"[Gmail] Draft created — ID: {draft.get('id')}")
    return draft
