"""
phase7_email/email_generator.py
================================
Phase 7a — Email Draft Generation & Delivery (with Fee Explanation).

Converts the markdown weekly note into a professional HTML email, appends a
"Fee Explanation: Mutual Fund Exit Load" section, and delivers it via one of
three methods, in priority order:

  1. Gmail API  (creates a draft in the sender's Drafts folder)
  2. SMTP       (sends immediately via any SMTP server)
  3. Local .eml (saves a draft file under output/ when no email config exists)

Public API
----------
  send_email(note_markdown, recipient_name, recipient_email, fee_data=None) → tuple[str, str]
  generate_email_html(note_markdown, recipient_name, week_label, fee_data=None) → str
"""

import logging
import os
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
_TEMPLATE_PATH = _HERE / "email_template.html"
_OUTPUT_DIR = Path("output")

# ── Email subject template ───────────────────────────────────────────────────
SUBJECT_TEMPLATE = "📋 INDMoney Weekly Product Pulse — Week of {date}"


# ─────────────────────────────────────────────────────────────────────────────
# Markdown → HTML conversion (lightweight, no external deps)
# ─────────────────────────────────────────────────────────────────────────────

def _markdown_to_html(md: str) -> str:
    """
    Convert a subset of Markdown to HTML suitable for email bodies.

    Supported constructs (in order of processing):
      - ATX headings  (# ## ###)
      - Bold          (**text**)
      - Italic        (*text*)
      - Blockquotes   (> text)
      - Unordered lists (* item / - item)
      - Ordered lists  (1. item)
      - Horizontal rules (---)
      - Plain paragraphs (blank-line separation)
    """
    lines = md.splitlines()
    html_lines: list[str] = []
    in_ul = False
    in_ol = False
    in_blockquote = False

    def _close_lists():
        nonlocal in_ul, in_ol, in_blockquote
        if in_ul:
            html_lines.append("</ul>")
            in_ul = False
        if in_ol:
            html_lines.append("</ol>")
            in_ol = False
        if in_blockquote:
            html_lines.append("</blockquote>")
            in_blockquote = False

    def _inline(text: str) -> str:
        """Apply inline markdown (bold, italic)."""
        # Bold
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        # Italic (single star, not double)
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
        return text

    for line in lines:
        stripped = line.strip()

        # Blank line → close any open constructs, then add paragraph break
        if stripped == "":
            _close_lists()
            html_lines.append("<br/>")
            continue

        # Horizontal rule
        if re.match(r"^-{3,}$", stripped) or re.match(r"^_{3,}$", stripped):
            _close_lists()
            html_lines.append("<hr/>")
            continue

        # ATX headings
        heading_match = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if heading_match:
            _close_lists()
            level = len(heading_match.group(1))
            content = _inline(heading_match.group(2))
            html_lines.append(f"<h{level}>{content}</h{level}>")
            continue

        # Blockquote
        if stripped.startswith("> "):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False
            text = _inline(stripped[2:])
            html_lines.append(f"<blockquote>{text}</blockquote>")
            continue

        # Unordered list
        ul_match = re.match(r"^[\*\-]\s+(.*)", stripped)
        if ul_match:
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False
            if not in_ul:
                html_lines.append("<ul>")
                in_ul = True
            html_lines.append(f"<li>{_inline(ul_match.group(1))}</li>")
            continue

        # Ordered list
        ol_match = re.match(r"^\d+\.\s+(.*)", stripped)
        if ol_match:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if not in_ol:
                html_lines.append("<ol>")
                in_ol = True
            html_lines.append(f"<li>{_inline(ol_match.group(1))}</li>")
            continue

        # Plain paragraph
        _close_lists()
        html_lines.append(f"<p>{_inline(stripped)}</p>")

    _close_lists()
    return "\n".join(html_lines)


# ─────────────────────────────────────────────────────────────────────────────
# HTML email assembly
# ─────────────────────────────────────────────────────────────────────────────

def generate_email_html(
    note_markdown: str,
    recipient_name: str,
    week_label: str = "",
    fee_data: dict | None = None,
) -> str:
    """
    Fill the HTML email template with the weekly note content and optional
    fee explanation appendix.

    Parameters
    ----------
    note_markdown   : str  — Full markdown text of the weekly note.
    recipient_name  : str  — Recipient's display name.
    week_label      : str  — Human-readable week range (e.g. "March 2–8, 2026").
    fee_data        : dict — Output of fee_explainer.generate_fee_explanation().
                             If None, the {{FEE_EXPLANATION}} placeholder is
                             replaced with an empty string.

    Returns
    -------
    str  — Complete HTML string ready to embed in an email.
    """
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")

    note_html = _markdown_to_html(note_markdown)

    # Infer review count from first line if available
    review_count = "recent"
    first_line = note_markdown.strip().splitlines()[0] if note_markdown.strip() else ""
    count_match = re.search(r"Reviews analyzed:\s*(\d+)", first_line)
    if count_match:
        review_count = count_match.group(1)

    if not week_label:
        week_label = datetime.now().strftime("Week of %B %d, %Y")

    # Build fee explanation HTML (or empty string if not provided)
    if fee_data is not None:
        from .fee_explainer import format_fee_explanation_html
        fee_html = format_fee_explanation_html(fee_data)
    else:
        fee_html = ""

    html = (
        template
        .replace("{{RECIPIENT_NAME}}", recipient_name)
        .replace("{{WEEK_LABEL}}", week_label)
        .replace("{{NOTE_BODY}}", note_html)
        .replace("{{REVIEW_COUNT}}", str(review_count))
        .replace("{{YEAR}}", str(datetime.now().year))
        .replace("{{FEE_EXPLANATION}}", fee_html)
    )
    return html


# ─────────────────────────────────────────────────────────────────────────────
# Subject builder
# ─────────────────────────────────────────────────────────────────────────────

def build_subject(date_str: str = "") -> str:
    """
    Build the email subject line.

    Parameters
    ----------
    date_str : str — ISO date string (YYYY-MM-DD). Defaults to today.

    Returns
    -------
    str — Formatted subject line matching the architecture spec.
    """
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        formatted = dt.strftime("%B %d, %Y")
    except ValueError:
        formatted = date_str
    return SUBJECT_TEMPLATE.format(date=formatted)


# ─────────────────────────────────────────────────────────────────────────────
# .eml fallback
# ─────────────────────────────────────────────────────────────────────────────

def _save_eml(
    html_body: str,
    subject: str,
    recipient_name: str,
    recipient_email: str,
    sender_alias: str = "weekly-pulse@company.com",
) -> Path:
    """
    Save the email as a local .eml file and return its path.
    This is the fallback when no email credentials are configured.
    """
    import email.mime.multipart
    import email.mime.text

    msg = email.mime.multipart.MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_alias
    msg["To"] = f"{recipient_name} <{recipient_email}>"
    msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")

    # Plain-text fallback (strip HTML tags)
    plain = re.sub(r"<[^>]+>", "", html_body)
    plain = re.sub(r"\n{3,}", "\n\n", plain).strip()

    msg.attach(email.mime.text.MIMEText(plain, "plain", "utf-8"))
    msg.attach(email.mime.text.MIMEText(html_body, "html", "utf-8"))

    _OUTPUT_DIR.mkdir(exist_ok=True)
    date_tag = datetime.now().strftime("%Y-%m-%d")
    eml_path = _OUTPUT_DIR / f"email_draft_{date_tag}.eml"

    with open(eml_path, "w", encoding="utf-8") as fh:
        fh.write(msg.as_string())

    logger.info(f"[Phase 7] Email draft saved locally: {eml_path}")
    return eml_path


# ─────────────────────────────────────────────────────────────────────────────
# Main public function
# ─────────────────────────────────────────────────────────────────────────────

def send_email(
    note_markdown: str,
    recipient_name: str,
    recipient_email: str,
    fee_data: dict | None = None,
) -> tuple[str, str]:
    """
    Wrap the weekly note (with optional fee explanation appendix) into a
    professional HTML email and deliver it.

    Delivery priority:
      1. Gmail API  (if GMAIL_CREDENTIALS env var is set)
      2. SMTP       (if SMTP_HOST / SMTP_USER / SMTP_PASS env vars are set)
      3. Local .eml (fallback — always succeeds)

    Parameters
    ----------
    note_markdown  : str  — Full markdown text of the weekly note.
    recipient_name : str  — Recipient's display name.
    recipient_email: str  — Recipient's email address.
    fee_data       : dict — Optional output of fee_explainer.generate_fee_explanation().
                            When provided, a fee explanation section is appended to the email.

    Returns
    -------
    tuple[str, str] — (delivery_method, detail_message)
    """
    logger.info(
        f"[Phase 7] Preparing email for {recipient_name} <{recipient_email}>"
    )

    # ── Build common assets ──────────────────────────────────────────────────
    date_str = datetime.now().strftime("%Y-%m-%d")
    subject = build_subject(date_str)
    html_body = generate_email_html(
        note_markdown=note_markdown,
        recipient_name=recipient_name,
        fee_data=fee_data,
    )

    # ── 1. Gmail API ─────────────────────────────────────────────────────────
    gmail_creds = os.environ.get("GMAIL_CREDENTIALS")
    if gmail_creds:
        try:
            from .gmail_client import create_gmail_draft
            create_gmail_draft(
                html_body=html_body,
                subject=subject,
                recipient_name=recipient_name,
                recipient_email=recipient_email,
            )
            msg = "Gmail API draft created successfully."
            logger.info(f"[Phase 7] {msg}")
            return ("gmail", msg)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[Phase 7] Gmail API failed ({exc}). Falling back to SMTP.")

    # ── 2. SMTP ──────────────────────────────────────────────────────────────
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    if smtp_host and smtp_user and smtp_pass:
        try:
            from .smtp_client import send_via_smtp
            send_via_smtp(
                html_body=html_body,
                subject=subject,
                recipient_name=recipient_name,
                recipient_email=recipient_email,
                smtp_host=smtp_host,
                smtp_user=smtp_user,
                smtp_pass=smtp_pass,
            )
            msg = f"Email sent via SMTP to {recipient_email}."
            logger.info(f"[Phase 7] {msg}")
            return ("smtp", msg)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[Phase 7] SMTP failed ({exc}). Falling back to local .eml.")

    # ── 3. Local .eml fallback ────────────────────────────────────────────────
    eml_path = _save_eml(
        html_body=html_body,
        subject=subject,
        recipient_name=recipient_name,
        recipient_email=recipient_email,
    )
    logger.info(f"[Phase 7] Fallback: email draft saved to {eml_path}")
    return ("fallback", f"Failed to send email. Draft saved to {eml_path}")
