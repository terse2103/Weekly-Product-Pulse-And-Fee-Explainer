import pytest
import os
import json
from datetime import datetime, timedelta
from phase1_ingestion.config import RAW_REVIEWS_FILE, REVIEW_WEEKS

@pytest.fixture
def mock_reviews(monkeypatch):
    """Mocks google_play_scraper reviews to return dummy data."""
    def mock_return(*args, **kwargs):
        cutoff = datetime.now() - timedelta(weeks=REVIEW_WEEKS)
        # 1 valid new review, 1 valid old review (should be filtered)
        mock_data = [
            {
                'score': 4,
                'content': 'Great app, very useful.',
                'at': datetime.now() - timedelta(weeks=1),
                'reviewId': 'test_review_id_1'
            },
            {
                'score': 2,
                'content': 'Too old review',
                'at': cutoff - timedelta(days=1),
                'reviewId': 'test_review_id_2'
            }
        ]
        # if continuation token is None, we return mock data, else empty to stop loop
        if kwargs.get('continuation_token') is None:
            return mock_data, "dummy_token"
        return [], None
        
    import sys
    import phase1_ingestion.fetch_reviews
    monkeypatch.setattr(sys.modules["phase1_ingestion.fetch_reviews"], 'reviews', mock_return)


def test_fetch_reviews(mock_reviews):
    """
    Tests if the fetch_reviews function appropriately fetches, filters,
    and formats the reviews.
    """
    from phase1_ingestion.fetch_reviews import fetch_reviews
    
    formatted_reviews = fetch_reviews()
    
    # We expect 1 review because the old one should be filtered out
    assert len(formatted_reviews) == 1
    review = formatted_reviews[0]
    
    # Check fields
    assert 'rating' in review
    assert 'text' in review
    assert 'date' in review
    assert 'review_id' in review
    assert 'title' not in review
    
    assert review['rating'] == 4
    assert review['text'] == 'Great app, very useful.'
    assert len(review['review_id']) == 10  # Because of the hash digest truncation

def test_data_schema():
    """
    Tests if the output file exists, matches the expected schema,
    and adheres to the defined date constraints.
    """
    if not os.path.exists(RAW_REVIEWS_FILE):
        pytest.skip(f"Test skipped: {RAW_REVIEWS_FILE} does not exist. Run fetch_reviews first.")
        
    with open(RAW_REVIEWS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    assert isinstance(data, list), "Data should be a list of reviews."
    
    if len(data) == 0:
        pytest.skip("Test skipped: No reviews fetched.")
        
    cutoff_date = datetime.now() - timedelta(weeks=REVIEW_WEEKS)
    
    for review in data:
        assert 'rating' in review, "Review missing 'rating' field."
        assert 'text' in review, "Review missing 'text' field."
        assert 'date' in review, "Review missing 'date' field."
        assert 'review_id' in review, "Review missing 'review_id' field."
        assert 'title' not in review, "Review should NOT have a 'title' field."
        
        # Test schema constraints
        assert isinstance(review['rating'], int), "Rating should be an integer."
        assert 1 <= review['rating'] <= 5, "Rating should be between 1 and 5."
        assert isinstance(review['review_id'], str) and len(review['review_id']) == 10, "Review ID should be a 10 char string."
        assert isinstance(review['text'], str), "Text should be a string."
        
        # Test date constraint
        review_date = datetime.fromisoformat(review['date'])
        assert review_date >= cutoff_date, f"Review is older than {REVIEW_WEEKS} weeks."
        
        # Test PII absence (basic)
        assert '@' not in review['review_id'], "Review ID shouldn't expose emails."
