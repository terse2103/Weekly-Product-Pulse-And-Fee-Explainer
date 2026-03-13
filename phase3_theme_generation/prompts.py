"""All prompt templates for Phase 3 — LLM Theme Generation."""

THEME_GENERATION_SYSTEM = """You are an expert product analyst working with mobile app review data.
Your task is to identify the most important recurring themes from a batch of user reviews.

Each theme should be:
- A short label (5 words or fewer)
- A one-sentence description explaining the theme
- Representative of a meaningful pattern in user feedback

Return ONLY a valid JSON object with a single key "themes" whose value is an array of theme objects.
Format:
{"themes": [
  {"theme": "Short Theme Label", "description": "One sentence describing what users say about this."},
  ...
]}"""

THEME_GENERATION_USER = """Here is a batch of app reviews from INDMoney users. Identify the top recurring themes.

Reviews:
{reviews_text}

Rules:
- Identify between 3 and 5 themes only.
- Focus on BROAD, OVERARCHING themes that encompass many different specific issues (e.g., use 'App Performance & Technical Issues' instead of specific 'App crashes on launch'). This helps ensure most reviews can fit into one of these categories.
- Ignore one-off complaints that do not form a pattern.
- Return ONLY the JSON object with key "themes". No extra text."""


THEME_MERGE_SYSTEM = """You are an expert product analyst. You will receive multiple lists of themes extracted from different batches of user reviews.
Your task is to consolidate them into a single deduplicated list of the top themes.

Return ONLY a valid JSON object with a single key "themes" whose value is an array of theme objects.
Format:
{"themes": [
  {"theme": "Short Theme Label", "description": "One sentence describing what users say about this."},
  ...
]}"""

THEME_MERGE_USER = """Here are the theme lists extracted from different batches of reviews:

{all_themes_text}

Rules:
- Merge similar or overlapping themes into one BROAD, OVERARCHING theme (e.g., combine 'Login issues' and 'App crashes' into 'App Performance & Stability').
- Ensure the final themes are broad enough to capture the vast majority of user feedback.
- Keep only the top 5 most significant overarching themes.
- Each theme label must be 5 words or fewer.
- Return ONLY the JSON object with key "themes". No extra text."""
