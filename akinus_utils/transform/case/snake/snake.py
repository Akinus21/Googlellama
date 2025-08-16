import re
from akinus_utils.utils.logger  import log

def _split_words(text: str) -> list[str]:
    if not text:
        return []
    text = re.sub(r"[_\-]+", " ", text)
    words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", text)
    if not words:
        words = text.split()
    return [w.lower() for w in words]

def snake(text: str) -> str:
    """
    Convert text to snake_case.

    Args:
        text (str): Input string.

    Returns:
        str: snake_case version of the input.
    """
    words = _split_words(text)
    result = "_".join(words)
    log("info", "case.snake", f"'{text}' -> '{result}'")
    return result
