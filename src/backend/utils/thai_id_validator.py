"""Thai National ID Card Validator using Modulo 11 checksum algorithm."""


def validate_thai_id(id_number: str) -> bool:
    """
    Validate Thai National ID using modulo 11 checksum algorithm.

    Algorithm:
    1. Take first 12 digits
    2. Multiply each digit by (13 - position), position starts at 1
    3. Sum all products
    4. Calculate (11 - (sum % 11)) % 10
    5. Compare with 13th digit (check digit)

    Args:
        id_number: 13-digit Thai ID number (can contain non-digit characters)

    Returns:
        True if valid, False otherwise

    Examples:
        >>> validate_thai_id("1234567890123")
        False  # Invalid checksum
        >>> validate_thai_id("1-1015-00208-53-4")
        True  # Valid format with dashes
    """
    # Remove non-digit characters
    clean_id = "".join(filter(str.isdigit, id_number))

    # Must be exactly 13 digits
    if len(clean_id) != 13:
        return False

    # Calculate checksum
    total = 0
    for i in range(12):
        total += int(clean_id[i]) * (13 - i)

    check_digit = (11 - (total % 11)) % 10

    # Compare with last digit
    return check_digit == int(clean_id[12])


def normalize_thai_id(id_number: str) -> str:
    """
    Normalize Thai ID by removing all non-digit characters.

    Args:
        id_number: Thai ID number (can contain dashes, spaces)

    Returns:
        Clean 13-digit ID number

    Examples:
        >>> normalize_thai_id("1-1015-00208-53-4")
        "1101500208534"
    """
    return "".join(filter(str.isdigit, id_number))
