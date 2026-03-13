"""Validator for Phase 4 (Grouping)."""

import json
import os
import logging
from typing import List, Dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
THEMED_REVIEWS_FILE = os.path.join(DATA_DIR, "themed_reviews.json")

def validate_distribution() -> bool:
    if not os.path.exists(THEMED_REVIEWS_FILE):
        logger.error(f"{THEMED_REVIEWS_FILE} not found.")
        return False
        
    with open(THEMED_REVIEWS_FILE, "r", encoding="utf-8") as f:
        reviews = json.load(f)
        
    if not reviews:
        logger.error("No reviews to validate.")
        return False

    theme_counts: Dict[str, int] = {}
    for r in reviews:
        assert isinstance(r, dict), "Review must be a dict"
        assert "theme" in r, f"Review missing theme: {r.get('review_id', 'unknown')}"
        theme = r["theme"]
        theme_counts[theme] = theme_counts.get(theme, 0) + 1
        
    total = len(reviews)
    valid = True
    
    for theme, count in theme_counts.items():
        percentage = count / total
        logger.info(f"Theme '{theme}': {percentage:.1%} ({count}/{total})")
        if percentage > 0.6:
            logger.warning(f"Theme '{theme}' dominates (>60%). This might indicate overly broad categorization.")
            valid = False
            
    if "Other" in theme_counts and (theme_counts["Other"] / total) > 0.3:
        logger.warning("'Other' category dominates (>30%). Re-run Phase 3 with broader prompts.")
        valid = False

    return valid

if __name__ == "__main__":
    validate_distribution()
