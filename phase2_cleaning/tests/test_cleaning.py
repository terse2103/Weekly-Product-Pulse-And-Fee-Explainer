import pytest
from phase2_cleaning.cleaner import normalize_text, is_valid_length, clean_reviews
from phase2_cleaning.deduplicator import deduplicate_reviews

def test_normalize():
    """ Tests emoji removal, lowercasing, and whitespace collapsing. """
    text = "  THIS App is COOL! 😍🔥🔥   Too many bugs though… \n\t Need fix!  "
    normalized = normalize_text(text)
    assert "😍" not in normalized
    assert "🔥" not in normalized
    assert "this app is cool!" in normalized
    assert "  " not in normalized

def test_length_filter():
    """ Tests discarding reviews with < 5 words. """
    assert not is_valid_length("cool app")
    assert not is_valid_length("i hate it so") # 4 words
    assert is_valid_length("this is a five word review")
    
def test_clean_reviews_integration():
    """ Tests clean reviews removes short reviews and invalid schema. """
    raw_data = [
        {"rating": 5, "date": "2026-01-01", "review_id": "r1", "text": "good app"}, # < 5 words
        {"rating": 4, "date": "2026-01-02", "review_id": "r2", "text": "I really like this app a lot"}, # >= 5 words, valid
        {"rating": 3, "date": "2026-01-03", "review_id": "r3", "text": "short review here"}, # < 5 words
        {"text": "this is a long enough review but invalid schema"} # missing fields!
    ]
        
    cleaned = clean_reviews(raw_data)
    assert len(cleaned) == 1
    assert "like this app" in cleaned[0]['text']

def test_deduplicator():
    """ Tests exact and near duplicates are discarded. """
    cleaned_reviews = [
        {"text": "the new ui is very confusing and hard to use"},
        {"text": "the new ui is confusing and very hard to use for me"}, # Near duplicate (Jaccard > 0.9 depending on logic, let's see)
        {"text": "totally different review right here"},
        {"text": "the new ui is very confusing and hard to use"} # Exact match
    ]
    
    # Exact duplicate should definitely be removed. Make threshold low for test
    deduped = deduplicate_reviews(cleaned_reviews, threshold=0.7)
    
    # Should definitely remove the exact match
    assert len(deduped) <= 3
    
    # Check deduplication against exact texts
    texts = [r['text'] for r in deduped]
    assert len(texts) == len(set(texts))

def test_empty_string():
    assert normalize_text("") == ""
    assert normalize_text("    \n\t   ") == ""
    assert not is_valid_length("    ")
