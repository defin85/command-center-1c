from __future__ import annotations

from typing import Any


def build_canonical_extensions_inventory(normalized_snapshot: Any, spec: dict | None) -> dict[str, Any]:
    """
    MVP mapping: normalized extensions snapshot -> canonical extensions_inventory.

    Today, the canonical shape is intentionally close to normalized snapshot output:
      {"extensions": [{"name": "...", "version"?: "...", "is_active"?: bool}, ...]}

    `spec` is reserved for future deterministic mapping rules. For now, it can be used
    as an identity placeholder without changing output.
    """

    if not isinstance(normalized_snapshot, dict):
        return {"extensions": []}

    extensions = normalized_snapshot.get("extensions")
    if not isinstance(extensions, list):
        extensions = []

    out_items: list[dict[str, Any]] = []
    for item in extensions:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        row: dict[str, Any] = {"name": name}
        version = item.get("version")
        if version is not None:
            version = str(version).strip() or None
            if version is not None:
                row["version"] = version
        is_active = item.get("is_active")
        if isinstance(is_active, bool):
            row["is_active"] = is_active
        out_items.append(row)

    return {"extensions": out_items}


def validate_extensions_inventory(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["payload must be an object"]

    extensions = payload.get("extensions")
    if not isinstance(extensions, list):
        return ["extensions must be a list"]

    errors: list[str] = []
    for idx, item in enumerate(extensions):
        if not isinstance(item, dict):
            errors.append(f"extensions[{idx}] must be an object")
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            errors.append(f"extensions[{idx}].name is required")
    return errors

