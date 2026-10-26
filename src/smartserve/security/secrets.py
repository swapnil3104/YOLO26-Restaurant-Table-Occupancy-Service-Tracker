"""Secrets protection and sanitization utilities.

Ensures sensitive parameters (passwords, tokens, database credentials, API keys)
are never logged, returned in responses, or exposed through error traces.
Adheres to Docs/PRD.md Section 13 (Privacy & Security) and Docs/TASKS.md Phase 8.
"""

import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

SENSITIVE_FIELD_PATTERNS = [
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"auth", re.IGNORECASE),
    re.compile(r"credential", re.IGNORECASE),
    re.compile(r"private[_-]?key", re.IGNORECASE),
]

MASK_VALUE = "********"


def is_sensitive_key(key: str) -> bool:
    """Check if a dictionary key matches common sensitive name patterns."""
    return any(pattern.search(key) for pattern in SENSITIVE_FIELD_PATTERNS)


def sanitize_url(url: str | None) -> str | None:
    """Remove user credentials/passwords from connection strings and URLs."""
    if not url:
        return url
    try:
        parsed = urlsplit(url)
        if parsed.password:
            # Replace password with masked value
            netloc = f"{parsed.username}:{MASK_VALUE}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
        return url
    except Exception:
        # Fallback regex masking
        return re.sub(r"://([^:]+):([^@]+)@", rf"://\1:{MASK_VALUE}@", url)


def sanitize_data(data: Any, depth: int = 0, max_depth: int = 10) -> Any:
    """Recursively sanitize sensitive fields in dictionaries, lists, and primitives."""
    if depth > max_depth:
        return "[Max depth reached]"

    if isinstance(data, dict):
        sanitized: dict[str, Any] = {}
        for key, value in data.items():
            str_key = str(key)
            if is_sensitive_key(str_key):
                sanitized[str_key] = MASK_VALUE
            elif "url" in str_key.lower() and isinstance(value, str):
                sanitized[str_key] = sanitize_url(value)
            else:
                sanitized[str_key] = sanitize_data(value, depth=depth + 1, max_depth=max_depth)
        return sanitized

    if isinstance(data, (list, tuple, set)):
        items = [sanitize_data(item, depth=depth + 1, max_depth=max_depth) for item in data]
        return type(data)(items)

    return data
