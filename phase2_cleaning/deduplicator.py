import json
import os
import re
from typing import List, Dict
from phase2_cleaning.cleaner import process as clean_process, NORMALIZED_REVIEWS_FILE

def get_jaccard_similarity(set1: set, set2: set) -> float:
    """Calculates Jaccard similarity between two sets."""
    if not set1 or not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return float(intersection) / union

def get_tokens(text: str) -> set:
    """Gets tokens (words) from a clean text string."""
    return set(text.split())

def deduplicate_reviews(reviews_data: List[Dict], threshold: float = 0.9) -> List[Dict]:
    """
    Removes exact and near-duplicate reviews using Jaccard Similarity.
    Reviews should already be normalized before passing here.
    """
    deduped = []
    seen_texts = set()
    
    for review in reviews_data:
        text = review.get('text', '')
        # 1. Exact match check
        if text in seen_texts:
            continue
            
        # 2. Near-duplicate check
        is_duplicate = False
        current_tokens = get_tokens(text)
        
        # We check against already saved deduped items
        # Note: This is O(N^2) but fine for a small weekly batch of a few hundred reviews
        for saved_review in deduped:
            saved_tokens = get_tokens(saved_review['text'])
            sim = get_jaccard_similarity(current_tokens, saved_tokens)
            if sim > threshold:
                is_duplicate = True
                break
                
        if not is_duplicate:
            deduped.append(review)
            seen_texts.add(text)
            
    return deduped

def run_phase2a():
    """Runs cleaner and deduplicator, saving to normalized_reviews.json"""
    cleaned_reviews = clean_process()
    
    if not cleaned_reviews:
        print("No cleaned reviews to process.")
        return []
        
    print(f"Starting deduplication for {len(cleaned_reviews)} reviews.")
    deduped_reviews = deduplicate_reviews(cleaned_reviews)
    print(f"After deduplication: {len(deduped_reviews)} unique reviews remain.")
    
    with open(NORMALIZED_REVIEWS_FILE, 'w', encoding='utf-8') as f:
        json.dump(deduped_reviews, f, indent=2, ensure_ascii=False)
        
    print(f"Phase 2a complete. Output written to {NORMALIZED_REVIEWS_FILE}")
    return deduped_reviews

if __name__ == "__main__":
    run_phase2a()
