"""
phase7_email/fee_explainer.py
==============================
Phase 7a — Fee Explanation Generator.

Generates a neutral, facts-only "Fee Explanation: Mutual Fund Exit Load"
section to be appended to the weekly pulse email.

Rules (from Architecture.md):
  - Exactly 3 bullet points.
  - Neutral, facts-only tone — no recommendations, no comparisons, no opinions.
  - Only two approved source URLs may be referenced (hardcoded below).
  - last_checked is always the pipeline run date.

Public API
----------
  generate_fee_explanation() -> dict
    Returns:
      {
        "fee_scenario": "Mutual Fund Exit Load",
        "explanation_bullets": ["...", "...", "..."],   # exactly 3 strings
        "source_links": ["<url1>", "<url2>"],
        "last_checked": "YYYY-MM-DD",
      }

  format_fee_explanation_markdown(fee_data: dict) -> str
    Returns a markdown-formatted block ready to embed in an email or JSON.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Approved sources (hardcoded — only these two are permitted) ───────────────
APPROVED_SOURCES = [
    "https://groww.in/p/exit-load-in-mutual-funds",
    "https://mf.nipponindiaim.com/investoreducation/financial-term-of-the-week-exit-load",
]

# ── Fee scenario identifier ──────────────────────────────────────────────────
FEE_SCENARIO = "Mutual Fund Exit Load"

# ── Hardcoded factual bullets (neutral, facts-only) ───────────────────────────
# These are verified facts about exit loads drawn from the approved sources.
# No recommendations, comparisons, or opinions are included.
EXPLANATION_BULLETS = [
    (
        "An exit load is a fee charged by a mutual fund when an investor "
        "redeems (sells) their units before a specified holding period; "
        "it is expressed as a percentage of the redemption amount."
    ),
    (
        "Exit load rates and the applicable holding period vary by fund and "
        "fund house — for example, many equity mutual funds charge 1% exit load "
        "if units are redeemed within 1 year of purchase, while liquid funds "
        "typically have a graded exit load structure for very short holding periods."
    ),
    (
        "The exit load is deducted from the redemption proceeds before the "
        "remaining amount is credited to the investor; funds with no exit load "
        "are described as 'nil exit load' funds, and the specific terms are "
        "disclosed in the fund's Scheme Information Document (SID)."
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Public functions
# ─────────────────────────────────────────────────────────────────────────────

def generate_fee_explanation() -> dict:
    """
    Generate the fee explanation data structure.

    Returns
    -------
    dict with keys:
      fee_scenario       : str   — always "Mutual Fund Exit Load"
      explanation_bullets: list  — exactly 3 factual bullet strings
      source_links       : list  — the 2 approved source URLs
      last_checked       : str   — today's date in YYYY-MM-DD format
    """
    today = datetime.now().strftime("%Y-%m-%d")
    fee_data = {
        "fee_scenario": FEE_SCENARIO,
        "explanation_bullets": list(EXPLANATION_BULLETS),  # copy, not reference
        "source_links": list(APPROVED_SOURCES),
        "last_checked": today,
    }
    logger.info(
        "[Phase 7a] Fee explanation generated for scenario: %s (last_checked: %s)",
        FEE_SCENARIO,
        today,
    )
    return fee_data


def format_fee_explanation_markdown(fee_data: dict) -> str:
    """
    Format a fee_data dict (from generate_fee_explanation()) into a
    markdown block suitable for embedding in the email body.

    Format (matches Architecture.md spec):

        ─────────────────────────────────────────────
        Fee Explanation: Mutual Fund Exit Load
        ─────────────────────────────────────────────
        • Bullet 1
        • Bullet 2
        • Bullet 3

        Sources:
          [1] <url1>
          [2] <url2>

        Last checked: YYYY-MM-DD

    Parameters
    ----------
    fee_data : dict — output of generate_fee_explanation()

    Returns
    -------
    str — formatted markdown block
    """
    divider = "─" * 45
    scenario = fee_data.get("fee_scenario", FEE_SCENARIO)
    bullets = fee_data.get("explanation_bullets", EXPLANATION_BULLETS)
    sources = fee_data.get("source_links", APPROVED_SOURCES)
    last_checked = fee_data.get("last_checked", datetime.now().strftime("%Y-%m-%d"))

    bullet_lines = "\n".join(f"• {b}" for b in bullets)
    source_lines = "\n".join(f"  [{i + 1}] {url}" for i, url in enumerate(sources))

    return (
        f"\n{divider}\n"
        f"Fee Explanation: {scenario}\n"
        f"{divider}\n"
        f"{bullet_lines}\n\n"
        f"Sources:\n{source_lines}\n\n"
        f"Last checked: {last_checked}\n"
    )


def format_fee_explanation_html(fee_data: dict) -> str:
    """
    Format a fee_data dict into an HTML block for embedding in the email template.
    Styled to match the existing email_template.html design system.

    Parameters
    ----------
    fee_data : dict — output of generate_fee_explanation()

    Returns
    -------
    str — HTML string ready to substitute into {{FEE_EXPLANATION}}
    """
    scenario = fee_data.get("fee_scenario", FEE_SCENARIO)
    bullets = fee_data.get("explanation_bullets", EXPLANATION_BULLETS)
    sources = fee_data.get("source_links", APPROVED_SOURCES)
    last_checked = fee_data.get("last_checked", datetime.now().strftime("%Y-%m-%d"))

    bullet_items = "\n".join(
        f'      <li>{b}</li>' for b in bullets
    )
    source_items = "\n".join(
        f'      <li><a href="{url}" style="color:#0d6efd;text-decoration:none;">'
        f'Source [{i + 1}]</a> — {url}</li>'
        for i, url in enumerate(sources)
    )

    return f"""
<div class="fee-section" style="
  margin: 24px 0 0;
  padding: 20px 24px;
  background: #f0f7ff;
  border-left: 4px solid #0d6efd;
  border-radius: 8px;
">
  <h3 style="
    font-size: 15px;
    font-weight: 700;
    color: #1e3a5f;
    margin: 0 0 12px;
    border-bottom: 1px solid #bee3f8;
    padding-bottom: 8px;
  ">💡 Fee Explanation: {scenario}</h3>
  <ul style="
    list-style: none;
    margin: 0 0 14px;
    padding: 0;
  ">
{bullet_items}
  </ul>
  <p style="font-size: 12px; color: #718096; margin: 8px 0 4px;">
    <strong>Sources:</strong>
  </p>
  <ul style="list-style: none; margin: 0 0 10px; padding: 0; font-size: 12px; color: #718096;">
{source_items}
  </ul>
  <p style="font-size: 11px; color: #a0aec0; margin: 0;">
    Last checked: {last_checked}
  </p>
</div>
"""
