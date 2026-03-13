import os

APP_ID = "in.indwealth"
REVIEW_WEEKS = 12
LANGUAGE = "en"
COUNTRY = "in"
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
RAW_REVIEWS_FILE = os.path.join(DATA_DIR, "raw_reviews.json")
