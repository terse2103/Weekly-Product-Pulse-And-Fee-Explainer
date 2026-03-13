import json
import os
from phase2_cleaning.pii_filter import PII_PATTERNS, CLEAN_REVIEWS_FILE
from typing import List, Dict

def validate_no_pii(reviews: List[Dict]) -> bool:
    """
    Second-pass check to assert no PII tokens/patterns remain in the text.
    Returns True if safe, False if a leak is detected.
    """
    is_safe = True
    
    for review in reviews:
        text = review.get('text', '')
        for pattern, placeholder in PII_PATTERNS:
            # We don't want the actual data to match our regex anymore!
            if pattern.search(text):
                print(f"🚨 PII LEAK DETECTED: Review ID: {review.get('review_id')}")
                is_safe = False
                
    return is_safe

def run_validation():
    """Reads clean_reviews.json and verifies no PII leaked."""
    if not os.path.exists(CLEAN_REVIEWS_FILE):
        print(f"Error: {CLEAN_REVIEWS_FILE} does not exist. Run filter first.")
        return False
        
    with open(CLEAN_REVIEWS_FILE, 'r', encoding='utf-8') as f:
        clean_reviews = json.load(f)
        
    print(f"Validating {len(clean_reviews)} reviews for PII leaks...")
    safe = validate_no_pii(clean_reviews)
    
    if safe:
        print("✅ Validation successful: No PII detected.")
    else:
        print("❌ Validation failed: PII leak found.")
        
    return safe

if __name__ == "__main__":
    run_validation()
