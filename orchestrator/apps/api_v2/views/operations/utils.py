"""Operations helpers shared across submodules."""

from __future__ import annotations

_SENSITIVE_KEYS: set[str] = {
    "db_password",
    "db_pwd",
    "password",
    "secret",
    "token",
    "api_key",
    "access_key",
    "secret_key",
    "stdin",
}


def _is_sensitive_key(key: str) -> bool:
    key_norm = (key or "").strip().lower()
    if not key_norm:
        return False
    if key_norm in _SENSITIVE_KEYS:
        return True
    if key_norm.endswith("_password") or key_norm.endswith("_pwd"):
        return True
    return False

