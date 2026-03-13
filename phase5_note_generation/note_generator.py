import os
import json
from datetime import datetime
from phase5_note_generation.groq_client import GroqClient
from phase5_note_generation.note_template import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from phase5_note_generation.word_counter import count_words


def summarize_reviews(themed_reviews, themes):
    """
    Creates a structured summary of themed reviews to pass to the LLM.

    Returns a string containing:
    - Total review count
    - Top themes ranked by review count
    - Sample user quotes (up to 5) per top theme
    """
    # Count reviews per theme and collect sample quotes
    theme_counts = {theme["theme"]: 0 for theme in themes}
    theme_reviews = {theme["theme"]: [] for theme in themes}
    theme_desc = {theme["theme"]: theme.get("description", "") for theme in themes}

    # Also handle 'Other' if present in themed_reviews
    for item in themed_reviews:
        theme = item.get("theme", "Other")
        if theme not in theme_counts:
            theme_counts[theme] = 0
            theme_reviews[theme] = []
            theme_desc[theme] = ""
        theme_counts[theme] += 1

        if "text" in item:
            theme_reviews[theme].append(item["text"])

    # Sort themes by count (descending)
    sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)
    top_themes = sorted_themes[:3]

    summary = []
    summary.append(f"Total reviews: {len(themed_reviews)}")
    summary.append("\nTop Themes:")
    for theme_name, count in top_themes:
        desc = theme_desc.get(theme_name, "")
        summary.append(f"- {theme_name}: {count} reviews. Description: {desc}")
        # Provide sample quotes for the LLM to choose from (up to 5 per theme)
        quotes = theme_reviews.get(theme_name, [])[:5]
        for q in quotes:
            summary.append(f'  * "{q}"')

    return "\n".join(summary)


def generate_note(themed_reviews, themes, date=None):
    """
    Generates the weekly one-pager note using Groq LLaMA 3.3 70B Versatile.

    Args:
        themed_reviews: List of review dicts with 'theme' and 'text' fields.
        themes: List of theme dicts with 'theme' (and optionally 'description').
        date: Optional date string (YYYY-MM-DD). Defaults to today.

    Returns:
        Tuple of (note_markdown: str, word_count: int).
        The note is also saved to output/weekly_note_{date}.md.
    """
    client = GroqClient()

    # Resolve date for filename
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    summary = summarize_reviews(themed_reviews, themes)
    user_prompt = USER_PROMPT_TEMPLATE.format(generation_date=date, themed_reviews_summary=summary)

    note = client.generate_content(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=2000,
        temperature=0.4,
    )

    # Resolve date for filename
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    word_count = count_words(note)

    # Save to output/
    os.makedirs("output", exist_ok=True)
    output_path = f"output/weekly_note_{date}.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(note)

    return note, word_count


if __name__ == "__main__":
    # Standalone execution — reads Phase 4 outputs and generates the weekly note
    with open("data/themed_reviews.json", "r", encoding="utf-8") as f:
        reviews = json.load(f)
    with open("data/themes.json", "r", encoding="utf-8") as f:
        theme_data = json.load(f)

    note, wc = generate_note(reviews, theme_data)
    print(f"Generated note ({wc} words):\n")
    print(note)
