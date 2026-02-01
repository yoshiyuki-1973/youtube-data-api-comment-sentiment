"""Text utility module."""


def truncate_string(s: str, max_length: int) -> str:
    """
    Safely truncate string for utf8mb4 columns (handles 4-byte emoji).

    Args:
        s: Input string
        max_length: Maximum character length

    Returns:
        Truncated string that is valid UTF-8

    Example:
        >>> truncate_string("Hello World", 5)
        'Hello'
        >>> truncate_string("abc", 10)
        'abc'
    """
    if not s:
        return ''

    if len(s) <= max_length:
        return s

    # Simply truncate by character count (utf8mb4 supports all Unicode)
    truncated = s[:max_length]

    # Ensure valid UTF-8 by encoding and decoding
    try:
        # This will raise UnicodeDecodeError if truncated at surrogate pair boundary
        truncated.encode('utf-8')
        return truncated
    except (UnicodeDecodeError, UnicodeEncodeError):
        # Rare case: truncated in middle of surrogate pair, back off by 1
        return s[:max_length - 1] if max_length > 1 else ''
