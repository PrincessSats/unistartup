"""
Input sanitization utilities for preventing XSS and injection attacks.

This module provides functions for sanitizing user input before storing
or displaying it. Uses bleach library for HTML sanitization.
"""

import re
import html
from typing import Optional

try:
    import bleach
except ImportError:
    # Fallback if bleach is not installed
    bleach = None


# Allowed HTML tags for rich text (if needed in future)
ALLOWED_TAGS = []  # No HTML tags allowed by default

# Allowed attributes for allowed tags
ALLOWED_ATTRIBUTES = {}

# Common XSS patterns to detect and block
XSS_PATTERNS = [
    re.compile(r'<\s*script', re.IGNORECASE),
    re.compile(r'javascript\s*:', re.IGNORECASE),
    re.compile(r'vbscript\s*:', re.IGNORECASE),
    re.compile(r'on\w+\s*=', re.IGNORECASE),  # onclick=, onerror=, etc.
    re.compile(r'<\s*iframe', re.IGNORECASE),
    re.compile(r'<\s*object', re.IGNORECASE),
    re.compile(r'<\s*embed', re.IGNORECASE),
    re.compile(r'expression\s*\(', re.IGNORECASE),
    re.compile(r'url\s*\(\s*["\']?\s*javascript:', re.IGNORECASE),
]


def sanitize_html(text: str, allowed_tags: Optional[list] = None) -> str:
    """
    Sanitize HTML input by removing dangerous tags and attributes.
    
    Args:
        text: Input text that may contain HTML
        allowed_tags: List of allowed HTML tags (default: none)
    
    Returns:
        Sanitized text safe for HTML display
    """
    if not text:
        return ""
    
    if bleach is not None:
        return bleach.clean(
            text,
            tags=allowed_tags or ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES or {},
            strip=True
        )
    else:
        # Fallback: strip all HTML tags and escape
        return strip_html_tags(text)


def strip_html_tags(text: str) -> str:
    """
    Remove all HTML tags from text.
    
    Args:
        text: Input text with potential HTML tags
    
    Returns:
        Plain text with HTML tags removed
    """
    if not text:
        return ""
    
    # Remove HTML tags using regex
    clean = re.sub(r'<[^>]+>', '', text)
    return clean


def escape_html(text: str) -> str:
    """
    Escape HTML special characters to prevent XSS.
    
    Args:
        text: Input text to escape
    
    Returns:
        HTML-escaped text safe for display
    """
    if not text:
        return ""
    
    return html.escape(text, quote=True)


def detect_xss_attempt(text: str) -> bool:
    """
    Detect potential XSS attack patterns in input.
    
    Args:
        text: Input text to check
    
    Returns:
        True if XSS pattern detected, False otherwise
    """
    if not text:
        return False
    
    for pattern in XSS_PATTERNS:
        if pattern.search(text):
            return True
    
    return False


def sanitize_username(username: str) -> str:
    """
    Sanitize username input.
    
    Allowed: alphanumeric, underscore, hyphen
    Max length: 50 characters
    
    Args:
        username: Raw username input
    
    Returns:
        Sanitized username
    """
    if not username:
        return ""
    
    # Remove any character that's not alphanumeric, underscore, or hyphen
    clean = re.sub(r'[^\w\-]', '', username)
    
    # Limit length
    return clean[:50]


def sanitize_email(email: str) -> str:
    """
    Sanitize email input.
    
    Args:
        email: Raw email input
    
    Returns:
        Sanitized email (lowercase, trimmed)
    """
    if not email:
        return ""
    
    # Lowercase and trim
    return email.lower().strip()[:254]


def sanitize_comment(body: str, max_length: int = 2000) -> str:
    """
    Sanitize comment body.
    
    - Strips all HTML
    - Escapes special characters
    - Enforces length limit
    
    Args:
        body: Comment text
        max_length: Maximum allowed length
    
    Returns:
        Sanitized comment text
    """
    if not body:
        return ""
    
    # Strip HTML tags
    clean = strip_html_tags(body)
    
    # Escape HTML entities
    clean = escape_html(clean)
    
    # Enforce length limit
    return clean[:max_length]


def sanitize_feedback_message(message: str, max_length: int = 500) -> str:
    """
    Sanitize feedback message.
    
    Args:
        message: Feedback text
        max_length: Maximum allowed length
    
    Returns:
        Sanitized feedback message
    """
    if not message:
        return ""
    
    # Strip and escape
    clean = strip_html_tags(message)
    clean = escape_html(clean)
    
    return clean[:max_length]


def sanitize_topic(topic: str, max_length: int = 100) -> str:
    """
    Sanitize topic/title input.
    
    Args:
        topic: Topic text
        max_length: Maximum allowed length
    
    Returns:
        Sanitized topic
    """
    if not topic:
        return ""
    
    # Strip HTML and escape
    clean = strip_html_tags(topic)
    clean = escape_html(clean)
    
    return clean[:max_length]


def validate_sql_sort_order(order: str, allowed_values: tuple = ("asc", "desc")) -> str:
    """
    Validate SQL ORDER BY parameter to prevent injection.
    
    Args:
        order: Sort order parameter from user
        allowed_values: Tuple of allowed values
    
    Returns:
        Validated sort order or default value
    
    Raises:
        ValueError: If order is not in allowed values
    """
    if not order:
        return allowed_values[0]
    
    order_lower = order.lower().strip()
    
    if order_lower not in allowed_values:
        raise ValueError(f"Invalid sort order: {order}. Must be one of {allowed_values}")
    
    return order_lower
