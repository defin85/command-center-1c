from __future__ import annotations

import re
from typing import Any

_SAFE_TOKEN_KEYS = frozenset(
    {
        "checkpoint_token",
        "next_checkpoint_token",
        "source_checkpoint_token",
        "pending_checkpoint_token",
    }
)
_SENSITIVE_KEYWORDS = (
    "password",
    "passwd",
    "pwd",
    "secret",
    "authorization",
    "api_key",
    "apikey",
    "client_secret",
    "access_token",
    "refresh_token",
    "id_token",
    "auth_token",
    "bearer_token",
)

_URL_CREDENTIALS_PATTERN = re.compile(r"://[^/\s:@]+:[^@\s/]+@")
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_KEY_VALUE_PATTERN = re.compile(
    (
        r"(?P<prefix>(?P<key>[\"']?"
        r"(?:"
        r"password|passwd|pwd|secret|authorization|api[_-]?key|apikey|client[_-]?secret|"
        r"access[_-]?token|refresh[_-]?token|id[_-]?token|auth[_-]?token|bearer[_-]?token|"
        r"token|[A-Za-z0-9_.-]*_token"
        r")"
        r"[\"']?)\s*(?::|=)\s*)(?P<value>\"[^\"]*\"|'[^']*'|[^,\s;]+)"
    ),
    re.IGNORECASE,
)


def sanitize_master_data_sync_text(value: object) -> str:
    text = str(value or "")
    if not text:
        return ""

    sanitized = _URL_CREDENTIALS_PATTERN.sub("://***:***@", text)
    sanitized = _BEARER_PATTERN.sub("Bearer ***", sanitized)
    sanitized = _KEY_VALUE_PATTERN.sub(_mask_sensitive_key_value_match, sanitized)
    return sanitized


def sanitize_master_data_sync_value(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, nested_value in value.items():
            if _is_sensitive_key(str(key)):
                sanitized[key] = "***"
                continue
            sanitized[key] = sanitize_master_data_sync_value(nested_value)
        return sanitized
    if isinstance(value, list):
        return [sanitize_master_data_sync_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_master_data_sync_value(item) for item in value)
    if isinstance(value, str):
        return sanitize_master_data_sync_text(value)
    return value


def _mask_sensitive_key_value_match(match: re.Match[str]) -> str:
    key = str(match.group("key") or "")
    if not _is_sensitive_key(key):
        return str(match.group(0))

    prefix = str(match.group("prefix") or "")
    value = str(match.group("value") or "")
    if value.startswith('"'):
        masked_value = '"***"'
    elif value.startswith("'"):
        masked_value = "'***'"
    else:
        masked_value = "***"
    return f"{prefix}{masked_value}"


def _is_sensitive_key(key: str) -> bool:
    normalized = str(key or "").strip().strip("'\"").replace("-", "_").lower()
    if not normalized:
        return False
    if normalized in _SAFE_TOKEN_KEYS:
        return False
    if normalized.endswith("_token"):
        return True
    if normalized == "token":
        return True
    return any(keyword in normalized for keyword in _SENSITIVE_KEYWORDS)


__all__ = [
    "sanitize_master_data_sync_text",
    "sanitize_master_data_sync_value",
]
