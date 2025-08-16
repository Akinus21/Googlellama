from akinus_utils.utils.logger  import log
import re

def _split_words(text: str) -> list[str]:
    """
    Helper to split text into words for title casing.
    """
    if not text:
        return []
    text = re.sub(r"[_\-]+", " ", text)
    words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", text)
    if not words:
        words = text.split()
    return [w.lower() for w in words]

def title(text: str) -> str:
    """
    Convert text to title case.

    Small words like articles and prepositions remain lowercase unless
    they are first or last in the string.

    Args:
        text (str): Input string.

    Returns:
        str: Title cased string.
    """
    small_words = {
        "a", "an", "the", "and", "but", "or", "for", "nor",
        "on", "at", "to", "from", "by", "in", "of"
    }
    words = _split_words(text)
    if not words:
        return ""
    title_cased = []
    for i, word in enumerate(words):
        lw = word.lower()
        if i == 0 or i == len(words) - 1 or lw not in small_words:
            title_cased.append(lw.capitalize())
        else:
            title_cased.append(lw)
    result = " ".join(title_cased)
    log("info", "case.title_case", f"'{text}' -> '{result}'")
    return result
