from akinus_utils.logger import local as log

def lower(text: str) -> str:
    """
    Convert text to all lowercase.

    Args:
        text (str): Input string.

    Returns:
        str: Lowercase version of the input.
    """
    result = text.lower()
    log("info", "case.lower", f"'{text}' -> '{result}'")
    return result
