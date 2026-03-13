import re

def count_words(text: str) -> int:
    """
    Counts the number of words in a given text.
    """
    if not text:
        return 0
    words = re.findall(r'\b\w+\b', text)
    return len(words)

def truncate_to_word_limit(text: str, limit: int = 250) -> str:
    """
    Truncates text to a specific word limit if it exceeds it.
    """
    words = text.split()
    if len(words) > limit:
        return " ".join(words[:limit]) + "..."
    return text
