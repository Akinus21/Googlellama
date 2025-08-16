from akinus_utils.logger import local as log

def upper(text: str) -> str:
    """
    Convert text to all uppercase.

    Args:
        text (str): Input string.

    Returns:
        str: Uppercase version of the input.
    """
    result = text.upper()
    log("info", "case.upper", f"'{text}' -> '{result}'")
    return result
