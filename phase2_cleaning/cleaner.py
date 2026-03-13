import json
import os
import re

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
RAW_REVIEWS_FILE = os.path.join(DATA_DIR, "raw_reviews.json")
NORMALIZED_REVIEWS_FILE = os.path.join(DATA_DIR, "normalized_reviews.json")

def remove_emojis(text: str) -> str:
    """Removes emojis from the given text."""
    # A simple regex to remove most common emoji ranges
    emoji_pattern = re.compile(
        "["
        u"\U0001f600-\U0001f64f"  # emoticons
        u"\U0001f300-\U0001f5ff"  # symbols & pictographs
        u"\U0001f680-\U0001f6ff"  # transport & map symbols
        u"\U0001f1e0-\U0001f1ff"  # flags (iOS)
        u"\u2702-\u27b0"          # Dingbats
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)

def normalize_text(text: str) -> str:
    """Normalizes the text by lowercasing and collapsing whitespace."""
    text = str(text) if text is not None else ""
    # Remove emojis first
    text = remove_emojis(text)
    # Lowercase
    text = text.lower()
    # Replace multiple whitespace characters with a single space
    text = re.sub(r'\s+', ' ', text)
    # Strip leading/trailing whitespaces
    return text.strip()

def is_valid_length(text: str) -> bool:
    """Checks if the review has at least 5 words."""
    words = text.split()
    return len(words) >= 5

def validate_schema(review: dict) -> bool:
    """Validates that expected schema fields are intact."""
    required_fields = ['rating', 'text', 'date', 'review_id']
    for field in required_fields:
        if field not in review:
            return False
        if review[field] is None:
            return False
    return True

def clean_reviews(reviews_data: list) -> list:
    """Applies normalization, length filtering, and schema validation."""
    cleaned = []
    
    for review in reviews_data:
        # Validate schema first
        if not validate_schema(review):
            continue
            
        original_text = review['text']
        normalized = normalize_text(original_text)
        
        # Only keep reviews with >= 5 words post-normalization
        if is_valid_length(normalized):
            new_review = review.copy()
            new_review['text'] = normalized
            cleaned.append(new_review)
            
    return cleaned

def process():
    """Reads raw reviews, cleans them, and writes to normalized_reviews.json (minus dedup)."""
    if not os.path.exists(RAW_REVIEWS_FILE):
        print(f"Error: {RAW_REVIEWS_FILE} does not exist.")
        return []
        
    with open(RAW_REVIEWS_FILE, 'r', encoding='utf-8') as f:
        raw_reviews = json.load(f)
        
    print(f"Loaded {len(raw_reviews)} raw reviews.")
    cleaned_reviews = clean_reviews(raw_reviews)
    print(f"Kept {len(cleaned_reviews)} reviews after cleaning (length & empty checks).")
    
    return cleaned_reviews

if __name__ == "__main__":
    process()
