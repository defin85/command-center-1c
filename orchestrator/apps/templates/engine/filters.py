"""
Custom Jinja2 filters for 1С-specific formatting.
"""

from datetime import datetime, date


def register_custom_filters(env):
    """Register all custom filters."""
    env.filters['guid1c'] = filter_guid1c
    env.filters['datetime1c'] = filter_datetime1c
    env.filters['date1c'] = filter_date1c
    env.filters['bool1c'] = filter_bool1c


def filter_guid1c(value):
    """
    Format GUID in 1C OData format.

    Example:
        {{ user_id|guid1c }}
        => guid'12345678-1234-1234-1234-123456789012'
    """
    if not value:
        return None
    return f"guid'{value}'"


def filter_datetime1c(value):
    """
    Format datetime in 1C OData format.

    Example:
        {{ created_at|datetime1c }}
        => datetime'2025-01-01T12:00:00'
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        # Serialize datetime object to ISO format string
        return f"datetime'{value.isoformat()}'"
    elif isinstance(value, str):
        return f"datetime'{value}'"
    # If value is already serialized (from JSON), try to parse it
    return f"datetime'{str(value)}'"


def filter_date1c(value):
    """
    Format date in 1C OData format.

    Example:
        {{ created_date|date1c }}
        => datetime'2025-01-01T00:00:00'
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        # If datetime object, use date part
        return f"datetime'{value.date().isoformat()}T00:00:00'"
    elif isinstance(value, date):
        return f"datetime'{value.isoformat()}T00:00:00'"
    elif isinstance(value, str):
        # Remove 'T...' part if present
        date_str = value.split('T')[0]
        return f"datetime'{date_str}T00:00:00'"
    return None


def filter_bool1c(value):
    """
    Format boolean in 1C format.

    Example:
        {{ is_active|bool1c }}
        => true / false (lowercase)
    """
    return str(bool(value)).lower()
