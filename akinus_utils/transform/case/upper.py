from akinus_utils.utils.logger  import log

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
