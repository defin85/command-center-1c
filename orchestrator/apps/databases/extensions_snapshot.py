from __future__ import annotations

from typing import Any


def normalize_extensions_snapshot(value: Any) -> dict[str, Any]:
    """
    Normalize DatabaseExtensionsSnapshot.snapshot into a stable shape.

    Canonical shape (best-effort):
      - extensions: list[object]
      - raw: any
      - parse_error: str | None

    Legacy snapshots stored raw worker payload directly (e.g. stdout/stderr). This
    function wraps them into the canonical shape without requiring DB migrations.
    """

    if value is None:
        return {"extensions": [], "raw": {}, "parse_error": None}

    if not isinstance(value, dict):
        return {"extensions": [], "raw": value, "parse_error": "snapshot must be an object"}

    has_any_reserved = any(k in value for k in ("extensions", "raw", "parse_error"))
    if not has_any_reserved:
        return {"extensions": [], "raw": value, "parse_error": None}

    out = dict(value)

    extensions = out.get("extensions")
    if not isinstance(extensions, list):
        extensions = []
    out["extensions"] = extensions

    if "raw" not in out:
        out["raw"] = {k: v for k, v in value.items() if k not in {"extensions", "parse_error"}}

    parse_error = out.get("parse_error")
    if parse_error is None:
        out["parse_error"] = None
    elif isinstance(parse_error, str):
        out["parse_error"] = parse_error
    else:
        out["parse_error"] = "parse_error must be a string"

    return out

