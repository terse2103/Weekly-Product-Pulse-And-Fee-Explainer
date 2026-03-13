from .cleaner import clean_reviews, normalize_text
from .deduplicator import deduplicate_reviews, run_phase2a
from .pii_filter import filter_pii, redact_pii, run_pii_filtering
from .pii_validator import validate_no_pii, run_validation

def clean_text(raw_reviews):
    """Phase 2a full pipeline (clean + deduplicate)"""
    cleaned = clean_reviews(raw_reviews)
    deduped = deduplicate_reviews(cleaned)
    return deduped

__all__ = [
    'clean_reviews', 'normalize_text', 
    'deduplicate_reviews', 'run_phase2a',
    'filter_pii', 'redact_pii', 'run_pii_filtering',
    'validate_no_pii', 'run_validation',
    'clean_text'
]
