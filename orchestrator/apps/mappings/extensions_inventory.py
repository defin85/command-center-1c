from __future__ import annotations

from typing import Any


def build_canonical_extensions_inventory(normalized_snapshot: Any, spec: dict | None) -> dict[str, Any]:
    """
    MVP mapping: normalized extensions snapshot -> canonical extensions_inventory.

    Today, the canonical shape is intentionally close to normalized snapshot output:
      {
        "extensions": [
          {
            "name": "...",
            "purpose"?: "...",
            "version"?: "...",
            "is_active"?: bool,
            "safe_mode"?: bool,
            "unsafe_action_protection"?: bool,
          },
          ...
        ]
      }

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
        purpose = item.get("purpose")
        if purpose is not None:
            purpose = str(purpose).strip() or None
            if purpose is not None:
                row["purpose"] = purpose
        version = item.get("version")
        if version is not None:
            version = str(version).strip() or None
            if version is not None:
                row["version"] = version
        is_active = item.get("is_active")
        if isinstance(is_active, bool):
            row["is_active"] = is_active
        safe_mode = item.get("safe_mode")
        if isinstance(safe_mode, bool):
            row["safe_mode"] = safe_mode
        unsafe_action_protection = item.get("unsafe_action_protection")
        if isinstance(unsafe_action_protection, bool):
            row["unsafe_action_protection"] = unsafe_action_protection
        out_items.append(row)

    return {"extensions": out_items}


def validate_extensions_inventory(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["payload must be an object"]

    errors: list[str] = []

    allowed_top_level_keys = {"extensions"}
    for key in payload.keys():
        if key not in allowed_top_level_keys:
            errors.append(f"unexpected top-level key: {key}")

    extensions = payload.get("extensions")
    if not isinstance(extensions, list):
        errors.append("extensions must be a list")
        return errors

    allowed_item_keys = {
        "name",
        "purpose",
        "version",
        "is_active",
        "safe_mode",
        "unsafe_action_protection",
    }

    for idx, item in enumerate(extensions):
        if not isinstance(item, dict):
            errors.append(f"extensions[{idx}] must be an object")
            continue

        for key in item.keys():
            if key not in allowed_item_keys:
                errors.append(f"extensions[{idx}].{key} is not allowed")

        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"extensions[{idx}].name is required")

        purpose = item.get("purpose")
        if "purpose" in item and (not isinstance(purpose, str) or not purpose.strip()):
            errors.append(f"extensions[{idx}].purpose must be a non-empty string")

        version = item.get("version")
        if "version" in item and (not isinstance(version, str) or not version.strip()):
            errors.append(f"extensions[{idx}].version must be a non-empty string")

        is_active = item.get("is_active")
        if "is_active" in item and not isinstance(is_active, bool):
            errors.append(f"extensions[{idx}].is_active must be a boolean")

        safe_mode = item.get("safe_mode")
        if "safe_mode" in item and not isinstance(safe_mode, bool):
            errors.append(f"extensions[{idx}].safe_mode must be a boolean")

        unsafe_action_protection = item.get("unsafe_action_protection")
        if "unsafe_action_protection" in item and not isinstance(unsafe_action_protection, bool):
            errors.append(f"extensions[{idx}].unsafe_action_protection must be a boolean")

    return errors
