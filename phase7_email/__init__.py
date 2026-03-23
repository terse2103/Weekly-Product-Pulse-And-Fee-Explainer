"""
phase7_email
============
Phase 7 — Email Draft Generation, Delivery & Fee Explanation + Google Doc Sync.

Sub-phases:
  Phase 7a: Email draft generation (with fee explanation appendix) & delivery.
  Phase 7b: Combined JSON creation & append to Google Doc via MCP.

Public API:
  send_email(note_markdown, recipient_name, recipient_email, fee_data=None)
      -> tuple[str, str]
  generate_email_html(note_markdown, recipient_name, week_label, fee_data=None)
      -> str
  generate_fee_explanation()
      -> dict
  build_combined_json(note_markdown, fee_data, date="")
      -> dict
  append_to_gdoc(combined, doc_id="")
      -> bool
"""

from .email_generator import send_email, generate_email_html          # noqa: F401
from .fee_explainer import generate_fee_explanation                    # noqa: F401
from .json_assembler import build_combined_json                        # noqa: F401
from .gdoc_mcp_appender import append_to_gdoc                         # noqa: F401

__all__ = [
    "send_email",
    "generate_email_html",
    "generate_fee_explanation",
    "build_combined_json",
    "append_to_gdoc",
]
