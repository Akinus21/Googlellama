import base64
from akinus_utils.utils.logger  import log

def base64_encode(text: str) -> str:
    """
    Encode text to Base64.

    Args:
        text (str): Plain text input.

    Returns:
        str: Base64 encoded string.
    """
    encoded_bytes = base64.b64encode(text.encode('utf-8'))
    result = encoded_bytes.decode('utf-8')
    log("info", "obfuscation.encode.base64_encode", f"Encoded '{text}' to Base64")
    return result

def rot13_encode(text: str) -> str:
    """
    Encode text using ROT13 cipher.

    Args:
        text (str): Plain text input.

    Returns:
        str: ROT13 encoded string.
    """
    result = text.translate(
        str.maketrans(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
            "NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm"
        )
    )
    log("info", "obfuscation.encode.rot13_encode", f"Encoded '{text}' with ROT13")
    return result

def hex_encode(text: str) -> str:
    """
    Encode text to hexadecimal representation.

    Args:
        text (str): Plain text input.

    Returns:
        str: Hexadecimal string.
    """
    result = text.encode('utf-8').hex()
    log("info", "obfuscation.encode.hex_encode", f"Encoded '{text}' to hex")
    return result
