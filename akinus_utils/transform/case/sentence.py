from akinus_utils.logger import local as log

def sentence(text: str) -> str:
    """
    Convert text to sentence case (capitalize first letter, rest lowercase).

    Args:
        text (str): Input string.

    Returns:
        str: Sentence cased string.
    """
    if not text:
        return ""
    text = text.strip()
    result = text[0].upper() + text[1:].lower() if len(text) > 1 else text.upper()
    log("info", "case.sentence", f"'{text}' -> '{result}'")
    return result
