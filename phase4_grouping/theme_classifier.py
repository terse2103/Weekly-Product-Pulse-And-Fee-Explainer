"""Phase 4 — Grouping reviews into themes via Groq LLaMA 3.3 70B."""

import json
import os
import time
import logging
from typing import List, Dict

from .groq_client import call_groq_json_mode
from .prompts import THEME_CLASSIFICATION_SYSTEM, THEME_CLASSIFICATION_USER

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
CLEAN_REVIEWS_FILE = os.path.join(DATA_DIR, "clean_reviews.json")
THEMES_FILE = os.path.join(DATA_DIR, "themes.json")
THEMED_REVIEWS_FILE = os.path.join(DATA_DIR, "themed_reviews.json")

BATCH_SIZE = 50   # Limit per request
BATCH_DELAY_SECS = 2  # Groq is fast, less delay needed

def classify_reviews() -> None:
    if not os.path.exists(CLEAN_REVIEWS_FILE) or not os.path.exists(THEMES_FILE):
        logger.error("Required data files missing. Run Phases 2b and 3 first.")
        return

    with open(CLEAN_REVIEWS_FILE, "r", encoding="utf-8") as f:
        reviews = json.load(f)

    with open(THEMES_FILE, "r", encoding="utf-8") as f:
        themes = json.load(f)

    theme_names = [t["theme"] for t in themes] + ["Other"]
    themes_list_str = "\n".join(f"- {t}" for t in theme_names)

    # ensure reviews have unique ids (they should, but just in case, use hash if absent)
    for i, r in enumerate(reviews):
        if "id" not in r and "review_id" not in r:
            r["review_id"] = f"rev_{i}"
        elif "id" in r and "review_id" not in r:
            r["review_id"] = r["id"]

    batches = [reviews[i:i + BATCH_SIZE] for i in range(0, len(reviews), BATCH_SIZE)]
    logger.info(f"Loaded {len(reviews)} reviews and {len(themes)} themes. Grouping across {len(batches)} batches.")

    themed_reviews = []
    
    for idx, batch in enumerate(batches, 1):
        logger.info(f"--- Batch {idx}/{len(batches)} ---")
        reviews_str = "\n".join(
            f"Review ID: {r['review_id']}\nText: {r['text']}\n"
            for r in batch
        )
        
        user_prompt = THEME_CLASSIFICATION_USER.format(
            themes_list=themes_list_str,
            reviews_text=reviews_str
        )
        
        result = call_groq_json_mode(THEME_CLASSIFICATION_SYSTEM, user_prompt)
        classifications = result.get("classifications", [])
        
        # Merge classifications back to reviews
        classification_map = {c["review_id"]: c["theme"] for c in classifications if "review_id" in c and "theme" in c}
        
        for r in batch:
            assigned_theme = classification_map.get(r["review_id"], "Other")
            if assigned_theme not in theme_names:
                assigned_theme = "Other"
            
            r["theme"] = assigned_theme
            themed_reviews.append(r)
        
        if idx < len(batches):
            logger.info(f"Waiting {BATCH_DELAY_SECS}s...")
            time.sleep(BATCH_DELAY_SECS)

    with open(THEMED_REVIEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(themed_reviews, f, indent=2, ensure_ascii=False)

    logger.info(f"Successfully themed {len(themed_reviews)} reviews and saved to {THEMED_REVIEWS_FILE}.")
    
    # Calculate distribution
    dist = {}
    for r in themed_reviews:
        dist[r["theme"]] = dist.get(r["theme"], 0) + 1
    
    logger.info("Theme Distribution:")
    for k, v in dist.items():
        logger.info(f"  - {k}: {v}")

if __name__ == "__main__":
    classify_reviews()
