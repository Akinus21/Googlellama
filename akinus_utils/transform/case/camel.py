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

def camel(text: str) -> str:
    """
    Convert text to camelCase.

    Args:
        text (str): Input string in any case.

    Returns:
        str: camelCase version of the input.
    """
    words = _split_words(text)
    if not words:
        return ""
    first, *rest = words
    rest_cap = [w.capitalize() for w in rest]
    result = first + "".join(rest_cap)
    log("info", "case.camel", f"'{text}' -> '{result}'")
    return result
