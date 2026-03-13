import json
import os
import hashlib
from datetime import datetime, timedelta
# We should try our best to just use google_play_scraper
# if it is not installed, we should inform the user
import logging

try:
    from google_play_scraper import Sort, reviews
except ImportError:
    logging.error("google-play-scraper is not installed. Please run: pip install google-play-scraper")
    raise

from .config import APP_ID, REVIEW_WEEKS, LANGUAGE, COUNTRY, DATA_DIR, RAW_REVIEWS_FILE

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_reviews():
    """
    Fetches the last N weeks of public Play Store reviews for INDMoney.
    """
    logger.info(f"Fetching reviews for {APP_ID} from the last {REVIEW_WEEKS} weeks...")
    
    # Calculate the cutoff date
    cutoff_date = datetime.now() - timedelta(weeks=REVIEW_WEEKS)
    
    all_reviews = []
    continuation_token = None
    
    # Iteratively fetch reviews until we hit the cutoff date or run out of reviews
    while True:
        try:
            result, continuation_token = reviews(
                APP_ID,
                lang=LANGUAGE,
                country=COUNTRY,
                sort=Sort.NEWEST,
                count=1000,
                continuation_token=continuation_token
            )
        except Exception as e:
            logger.error(f"Error fetching reviews: {e}")
            break
            
        if not result:
            break
            
        oldest_in_batch = result[-1]['at']
        
        # Only keep reviews newer than or equal to cutoff_date
        filtered_batch = [r for r in result if r['at'] >= cutoff_date]
        all_reviews.extend(filtered_batch)
        
        logger.info(f"Fetched batch of {len(result)}. Kept {len(filtered_batch)}. Oldest in batch: {oldest_in_batch.isoformat()}")
        
        if oldest_in_batch < cutoff_date or not continuation_token:
            logger.info("Reached cutoff date or end of reviews.")
            break
            
    # Format and strip PII from the raw output (user names, images, etc. aren't kept)
    formatted_reviews = []
    for r in all_reviews:
        # Create a pseudo-anonymized review ID
        review_id_hash = hashlib.sha256(r['reviewId'].encode('utf-8')).hexdigest()[:10]
        
        # We only keep rating, title (if it exists, Google Play might not have it), text, date, review_id
        formatted_reviews.append({
            "rating": r['score'],
            "text": r['content'],
            "date": r['at'].isoformat(),
            "review_id": review_id_hash
        })
            
    logger.info(f"Total formatted reviews kept: {len(formatted_reviews)}.")
    
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(RAW_REVIEWS_FILE, 'w', encoding='utf-8') as f:
        json.dump(formatted_reviews, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Saved to {RAW_REVIEWS_FILE}")
    return formatted_reviews

if __name__ == "__main__":
    fetch_reviews()
