"""
Utility functions for the Panini Album application.
"""

import re


def validate_email(email: str) -> bool:
    """
    Validate email address format.

    Uses a simple regex pattern to check for valid email format.
    Does not verify if the email actually exists.

    Args:
        email: Email address to validate

    Returns:
        True if email format is valid, False otherwise
    """
    if not email:
        return False

    # Simple regex for email validation
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None
