import base64
from akinus_utils.utils.logger  import log

def base64_decode(text: str) -> str:
    """
    Decode Base64 encoded string back to plain text.

    Args:
        text (str): Base64 encoded string.

    Returns:
        str: Decoded plain text.
    """
    try:
        decoded_bytes = base64.b64decode(text)
        result = decoded_bytes.decode('utf-8')
        log("info", "obfuscation.decode.base64_decode", f"Decoded Base64 string")
        return result
    except Exception as e:
        log("error", "obfuscation.decode.base64_decode", f"Failed to decode Base64: {e}")
        raise

def rot13_decode(text: str) -> str:
    """
    Decode ROT13 encoded string (ROT13 is symmetric, so same as encoding).

    Args:
        text (str): ROT13 encoded string.

    Returns:
        str: Decoded plain text.
    """
    # ROT13 is symmetric
    result = text.translate(
        str.maketrans(
            "NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm",
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        )
    )
    log("info", "obfuscation.decode.rot13_decode", f"Decoded ROT13 string")
    return result

def hex_decode(text: str) -> str:
    """
    Decode hexadecimal string back to plain text.

    Args:
        text (str): Hexadecimal string.

    Returns:
        str: Decoded plain text.
    """
    try:
        bytes_data = bytes.fromhex(text)
        result = bytes_data.decode('utf-8')
        log("info", "obfuscation.decode.hex_decode", f"Decoded hex string")
        return result
    except Exception as e:
        log("error", "obfuscation.decode.hex_decode", f"Failed to decode hex: {e}")
        raise
