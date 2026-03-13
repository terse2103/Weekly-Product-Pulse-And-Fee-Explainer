import re
import json
import os
from typing import List, Dict

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
NORMALIZED_REVIEWS_FILE = os.path.join(DATA_DIR, "normalized_reviews.json")
CLEAN_REVIEWS_FILE = os.path.join(DATA_DIR, "clean_reviews.json")

# Note: Order matters! E.g., match Emails before UPI to avoid partial matches
PII_PATTERNS = [
    # 1. Emails
    (re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'), '[EMAIL]'),
    # 2. UPI IDs (e.g., username@bankname - simple format)
    (re.compile(r'[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}'), '[REDACTED]'),
    # 3. Phone numbers (Indian format +91 or just 10 digits starting with 6-9)
    (re.compile(r'(?:\+?91[-.\s]?)?[6-9]\d{9}\b'), '[PHONE]'),
    # 4. Bank account numbers / Random long numbers (9-18 digits)
    (re.compile(r'\b\d{9,18}\b'), '[REDACTED]'),
    # 5. @ Mentions (Usernames)
    (re.compile(r'@\w+'), '[USER]')
]

def redact_pii(text: str) -> str:
    """Scans and redacts PII based on defined regex patterns."""
    redacted_text = str(text) if text is not None else ""
    for pattern, placeholder in PII_PATTERNS:
        redacted_text = pattern.sub(placeholder, redacted_text)
    return redacted_text

def filter_pii(reviews_data: List[Dict]) -> List[Dict]:
    """Iterates through reviews and redacts PII from text."""
    clean_data = []
    
    for review in reviews_data:
        if 'text' not in review:
            continue
            
        clean_review = review.copy()
        clean_review['text'] = redact_pii(review['text'])
        clean_data.append(clean_review)
        
    return clean_data

def run_pii_filtering():
    """Reads normalized reviews, scrubs PII, and writes to clean_reviews.json."""
    if not os.path.exists(NORMALIZED_REVIEWS_FILE):
        print(f"Error: {NORMALIZED_REVIEWS_FILE} does not exist. Run Phase 2a first.")
        return []
        
    with open(NORMALIZED_REVIEWS_FILE, 'r', encoding='utf-8') as f:
        normalized_reviews = json.load(f)
        
    print(f"Starting PII redaction for {len(normalized_reviews)} reviews.")
    clean_reviews = filter_pii(normalized_reviews)
    
    with open(CLEAN_REVIEWS_FILE, 'w', encoding='utf-8') as f:
        json.dump(clean_reviews, f, indent=2, ensure_ascii=False)
        
    print(f"Phase 2b complete. PII-free data written to {CLEAN_REVIEWS_FILE}")
    return clean_reviews

if __name__ == "__main__":
    run_pii_filtering()
