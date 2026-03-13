"""
phase7_email
============
Phase 7 — Email Draft Generation & Delivery.

Public API:
  send_email(note_markdown, recipient_name, recipient_email) → None
  generate_email_html(note_markdown, recipient_name, week_label) → str
  generate_eml(note_markdown, recipient_name, recipient_email, ...) → str
"""

from .email_generator import send_email, generate_email_html  # noqa: F401

__all__ = ["send_email", "generate_email_html"]
