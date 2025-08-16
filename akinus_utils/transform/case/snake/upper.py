import re
from akinus_utils.logger import local as log

def _split_words(text: str) -> list[str]:
    if not text:
        return []
    text = re.sub(r"[_\-]+", " ", text)
    words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", text)
    if not words:
        words = text.split()
    return [w.lower() for w in words]

def upper_snake(text: str) -> str:
    """
    Convert text to UPPER_SNAKE_CASE.

    Args:
        text (str): Input string.

    Returns:
        str: UPPER_SNAKE_CASE version of the input.
    """
    words = _split_words(text)
    result = "_".join(w.upper() for w in words)
    log("info", "case.upper_snake", f"'{text}' -> '{result}'")
    return result
