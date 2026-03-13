"""Phase 3 — LLM Theme Generation via Groq (llama-3.3-70b-versatile)."""

import json
import os
import time
import logging
from typing import List, Dict

from .groq_client import call_groq_json_mode
from .prompts import (
    THEME_GENERATION_SYSTEM,
    THEME_GENERATION_USER,
    THEME_MERGE_SYSTEM,
    THEME_MERGE_USER,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
CLEAN_REVIEWS_FILE = os.path.join(DATA_DIR, "clean_reviews.json")
THEMES_FILE = os.path.join(DATA_DIR, "themes.json")

BATCH_SIZE = 50   # reviews per LLM call (architecture: batches of 50)
BATCH_DELAY_SECS = 5   # short pause between batches (Groq is fast)
MAX_THEMES = 5    # hard cap per architecture


def _build_reviews_text(batch: List[Dict]) -> str:
    """Formats a batch of reviews into a numbered text block for the prompt."""
    lines = []
    for i, r in enumerate(batch, 1):
        rating_stars = "⭐" * r.get("rating", 0)
        lines.append(f"{i}. [{rating_stars}] {r['text']}")
    return "\n".join(lines)


def _validate_theme(theme: Dict) -> bool:
    """Returns True if a theme dict has the required keys and valid values."""
    if not isinstance(theme, dict):
        return False
    if "theme" not in theme or "description" not in theme:
        return False
    if not isinstance(theme["theme"], str) or not theme["theme"].strip():
        return False
    if not isinstance(theme["description"], str) or not theme["description"].strip():
        return False
    # Label should be <= 5 words
    if len(theme["theme"].split()) > 5:
        logger.warning(f"Theme label too long (>5 words): '{theme['theme']}'")
    return True


def _extract_themes_from_batch(batch: List[Dict]) -> List[Dict]:
    """Sends one batch to Groq and returns validated theme list."""
    reviews_text = _build_reviews_text(batch)
    user_prompt = THEME_GENERATION_USER.format(reviews_text=reviews_text)

    logger.info(f"Sending batch of {len(batch)} reviews to Groq (LLaMA 3.3 70B) for theme extraction...")
    result = call_groq_json_mode(THEME_GENERATION_SYSTEM, user_prompt)

    raw_themes = result.get("themes", [])
    if not isinstance(raw_themes, list):
        logger.warning("Unexpected response shape from Groq — skipping batch.")
        return []

    valid_themes = [t for t in raw_themes if _validate_theme(t)]
    logger.info(f"Extracted {len(valid_themes)} valid themes from batch.")
    return valid_themes


def _merge_themes(all_batch_themes: List[List[Dict]]) -> List[Dict]:
    """
    If there are multiple batches, sends all extracted theme lists to Groq
    for semantic merging and deduplication. Caps at MAX_THEMES.
    """
    flat = []
    for idx, batch_themes in enumerate(all_batch_themes, 1):
        flat.append(f"Batch {idx}:")
        for t in batch_themes:
            flat.append(f'  - Theme: "{t["theme"]}" -> {t["description"]}')

    all_themes_text = "\n".join(flat)
    user_prompt = THEME_MERGE_USER.format(all_themes_text=all_themes_text)

    logger.info("Merging themes across batches via Groq (LLaMA 3.3 70B)...")
    result = call_groq_json_mode(THEME_MERGE_SYSTEM, user_prompt)
    merged = result.get("themes", [])

    if not isinstance(merged, list):
        logger.warning("Unexpected merge response — falling back to first-batch themes.")
        return all_batch_themes[0][:MAX_THEMES] if all_batch_themes else []

    valid = [t for t in merged if _validate_theme(t)]
    return valid[:MAX_THEMES]


def generate_themes() -> List[Dict]:
    """
    Main entry point for Phase 3.
    Reads clean_reviews.json, batches reviews (50 per batch), extracts themes
    via Groq LLaMA 3.3 70B Versatile, merges across batches, caps at MAX_THEMES,
    and writes themes.json.
    """
    if not os.path.exists(CLEAN_REVIEWS_FILE):
        logger.error(f"{CLEAN_REVIEWS_FILE} not found. Run Phase 2b first.")
        return []

    with open(CLEAN_REVIEWS_FILE, "r", encoding="utf-8") as f:
        clean_reviews = json.load(f)

    logger.info(f"Loaded {len(clean_reviews)} clean reviews for theme generation.")

    # Split into batches of 50
    batches = [
        clean_reviews[i : i + BATCH_SIZE]
        for i in range(0, len(clean_reviews), BATCH_SIZE)
    ]
    logger.info(f"Processing {len(batches)} batch(es) of up to {BATCH_SIZE} reviews each.")

    all_batch_themes = []
    for idx, batch in enumerate(batches, 1):
        logger.info(f"--- Batch {idx}/{len(batches)} ---")
        themes = _extract_themes_from_batch(batch)
        if themes:
            all_batch_themes.append(themes)
        # Short pause between batches
        if idx < len(batches):
            logger.info(f"Waiting {BATCH_DELAY_SECS}s before next batch...")
            time.sleep(BATCH_DELAY_SECS)

    if not all_batch_themes:
        logger.error("No themes extracted from any batch.")
        return []

    # Merge if multiple batches, otherwise just take the single result
    if len(all_batch_themes) == 1:
        final_themes = all_batch_themes[0][:MAX_THEMES]
    else:
        final_themes = _merge_themes(all_batch_themes)

    logger.info(f"Final theme count: {len(final_themes)} (cap: {MAX_THEMES})")

    # Save themes.json
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(THEMES_FILE, "w", encoding="utf-8") as f:
        json.dump(final_themes, f, indent=2, ensure_ascii=False)

    logger.info(f"Themes saved to {THEMES_FILE}")
    for i, t in enumerate(final_themes, 1):
        logger.info(f"  {i}. {t['theme']}: {t['description']}")

    return final_themes


if __name__ == "__main__":
    generate_themes()
