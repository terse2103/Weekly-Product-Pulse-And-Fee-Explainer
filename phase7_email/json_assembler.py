"""
phase7_email/json_assembler.py
================================
Phase 7b — Combined JSON Assembler.

Combines the weekly note content (themes, quotes, action ideas parsed from
Phase 5 output) with the fee explanation data (from fee_explainer.py) into
a single JSON record as specified in Architecture.md.

Combined JSON Schema (from Architecture.md):
  {
    "date": "YYYY-MM-DD",
    "weekly_pulse": {
      "themes":       ["Theme 1", "Theme 2", "Theme 3"],
      "quotes":       ["Quote 1", "Quote 2", "Quote 3"],
      "action_ideas": ["Action 1", "Action 2", "Action 3"]
    },
    "fee_scenario":        "Mutual Fund Exit Load",
    "explanation_bullets": ["Fact 1", "Fact 2", "Fact 3"],
    "source_links":        ["<url1>", "<url2>"],
    "last_checked":        "YYYY-MM-DD"
  }

Public API
----------
  build_combined_json(note_markdown: str, fee_data: dict, date: str = "") -> dict
    Returns the combined JSON dict and saves a backup to output/.

  parse_note_sections(note_markdown: str) -> dict
    Parses the weekly note markdown into themes, quotes, and action_ideas lists.
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_OUTPUT_DIR = Path("output")


# ─────────────────────────────────────────────────────────────────────────────
# Note parser — extracts structured sections from markdown note
# ─────────────────────────────────────────────────────────────────────────────

def parse_note_sections(note_markdown: str) -> dict:
    """
    Parse the Phase 5 weekly note markdown to extract:
      - themes:       up to 3 theme labels
      - quotes:       up to 3 user quotes
      - action_ideas: up to 3 action items

    Uses a state machine to correctly identify sections and extract content regardless
    of minor markdown formatting variations from the LLM (e.g. bullets vs numbers,
    blockquotes vs quotes).
    """
    themes: list[str] = []
    quotes: list[str] = []
    action_ideas: list[str] = []

    lines = note_markdown.splitlines()
    current_section = None

    for line in lines:
        stripped = line.strip()
        lower_line = stripped.lower()
        
        # Identify which section we are currently reading
        if "themes" in lower_line and stripped.startswith("#"):
            current_section = "themes"
            continue
        elif "quotes" in lower_line and stripped.startswith("#"):
            current_section = "quotes"
            continue
        elif "action ideas" in lower_line and stripped.startswith("#"):
            current_section = "action_ideas"
            continue
            
        # Skip empty lines or other headers
        if not stripped or stripped.startswith("#"):
            continue
            
        # Match any list marker (*, -, >, or numbers like 1.)
        m = re.match(r"^[\*\-\>\d\.]+\s*(.*)", stripped)
        if m:
            content = m.group(1).strip()
            if not content:
                continue
                
            if current_section == "themes" and len(themes) < 3:
                # Extract theme name (before first colon, strip bold)
                theme_name = content.split(":")[0].replace("**", "").strip()
                # Remove common review count suffixes like "(45 reviews)" or "45 reviews"
                theme_name = re.sub(r"\s*\(?\d+\s*reviews?\)?.*", "", theme_name, flags=re.IGNORECASE).strip()
                if theme_name:
                    themes.append(theme_name)
                    
            elif current_section == "quotes" and len(quotes) < 3:
                # Strip leading/trailing quotes
                quote_text = content.strip('"').strip("'").strip()
                if quote_text:
                    quotes.append(quote_text)
                    
            elif current_section == "action_ideas" and len(action_ideas) < 3:
                # Strip bold markers
                action_text = content.replace("**", "").strip()
                if action_text:
                    action_ideas.append(action_text)

    logger.info(
        "[Phase 7b] Parsed note: %d themes, %d quotes, %d action ideas",
        len(themes), len(quotes), len(action_ideas)
    )
    return {
        "themes": themes,
        "quotes": quotes,
        "action_ideas": action_ideas,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main public function
# ─────────────────────────────────────────────────────────────────────────────

def build_combined_json(
    note_markdown: str,
    fee_data: dict,
    date: str = "",
) -> dict:
    """
    Build the combined JSON record from the weekly note and fee explanation.

    Parameters
    ----------
    note_markdown : str  — Full markdown text of the Phase 5 weekly note.
    fee_data      : dict — Output of fee_explainer.generate_fee_explanation().
    date          : str  — ISO date string (YYYY-MM-DD). Defaults to today.

    Returns
    -------
    dict — Combined JSON record (also saved to output/combined_pulse_{date}.json).
    """
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    parsed = parse_note_sections(note_markdown)

    combined = {
        "date": date,
        "weekly_pulse": {
            "themes":       parsed["themes"],
            "quotes":       parsed["quotes"],
            "action_ideas": parsed["action_ideas"],
        },
        "fee_scenario":        fee_data.get("fee_scenario", "Mutual Fund Exit Load"),
        "explanation_bullets": fee_data.get("explanation_bullets", []),
        "source_links":        fee_data.get("source_links", []),
        "last_checked":        fee_data.get("last_checked", date),
    }

    # ── Save local backup ────────────────────────────────────────────────────
    _OUTPUT_DIR.mkdir(exist_ok=True)
    backup_path = _OUTPUT_DIR / f"combined_pulse_{date}.json"
    with open(backup_path, "w", encoding="utf-8") as fh:
        json.dump(combined, fh, indent=2, ensure_ascii=False)
    logger.info("[Phase 7b] Combined JSON saved to %s", backup_path)

    return combined
