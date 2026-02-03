from __future__ import annotations

import json
import re
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


def build_extensions_snapshot_from_worker_result(value: Any) -> dict[str, Any]:
    """
    Build normalized extensions snapshot from worker result payload.

    Best-effort parsing rules:
      1) If raw already contains structured extensions list, use it.
      2) Else, parse raw.stdout (or raw if it's a string).
      3) On failure, keep extensions=[] and set parse_error.
    """

    snapshot = normalize_extensions_snapshot(value)
    raw = snapshot.get("raw")

    try:
        extensions = _extract_structured_extensions(raw)
        if extensions is None:
            stdout = None
            if isinstance(raw, dict):
                stdout = raw.get("stdout")
            elif isinstance(raw, str):
                stdout = raw

            if not isinstance(stdout, str):
                raise ValueError("cannot parse extensions: missing stdout")
            extensions = parse_extensions_stdout(stdout)

        snapshot["extensions"] = extensions
        snapshot["parse_error"] = None
    except Exception as exc:
        snapshot["extensions"] = []
        snapshot["parse_error"] = str(exc)

    return snapshot


def parse_extensions_stdout(stdout: str) -> list[dict[str, Any]]:
    text = str(stdout or "").strip()
    if not text:
        return []

    parsed = _try_parse_json(text)
    if parsed is not None:
        return parsed

    # kv-style output: "name : \"test\" version : ... active : yes ..."
    kv = _try_parse_kv_records(text)
    if kv is not None:
        return kv

    table = _try_parse_table(text)
    if table is not None:
        return table

    raise ValueError("unsupported extensions stdout format")


def _extract_structured_extensions(raw: Any) -> list[dict[str, Any]] | None:
    if not isinstance(raw, dict):
        return None

    direct = raw.get("extensions")
    if isinstance(direct, list):
        return _normalize_extensions_list(direct)

    data = raw.get("data")
    if isinstance(data, dict):
        nested = data.get("extensions")
        if isinstance(nested, list):
            return _normalize_extensions_list(nested)

    return None


def _normalize_extensions_list(items: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    for item in items:
        normalized = _normalize_extension_item(item)
        if not normalized:
            continue
        key = (str(normalized.get("name") or ""), str(normalized.get("version")) if normalized.get("version") is not None else None)
        if not key[0] or key in seen:
            continue
        seen.add(key)
        out.append(normalized)
    return out


def _normalize_extension_item(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None

    name = item.get("name") or item.get("extension") or item.get("id")
    name = str(name or "").strip()
    if not name:
        return None

    version = item.get("version")
    if version is not None:
        version = str(version).strip() or None

    active_raw = item.get("is_active")
    if active_raw is None:
        active_raw = item.get("active")
    is_active = _coerce_bool(active_raw)

    out: dict[str, Any] = {"name": name}
    if version is not None:
        out["version"] = version
    if is_active is not None:
        out["is_active"] = is_active

    purpose = item.get("purpose")
    if purpose is not None:
        purpose = str(purpose).strip() or None
        if purpose is not None:
            out["purpose"] = purpose

    safe_mode = _coerce_bool(item.get("safe_mode") if "safe_mode" in item else item.get("safe-mode"))
    if safe_mode is not None:
        out["safe_mode"] = safe_mode

    security_profile_name = item.get("security_profile_name") if "security_profile_name" in item else item.get("security-profile-name")
    if security_profile_name is not None:
        security_profile_name = str(security_profile_name).strip() or None
        if security_profile_name is not None:
            out["security_profile_name"] = security_profile_name

    unsafe_action_protection = _coerce_bool(
        item.get("unsafe_action_protection") if "unsafe_action_protection" in item else item.get("unsafe-action-protection")
    )
    if unsafe_action_protection is not None:
        out["unsafe_action_protection"] = unsafe_action_protection

    used_in_distributed_infobase = _coerce_bool(
        item.get("used_in_distributed_infobase") if "used_in_distributed_infobase" in item else item.get("used-in-distributed-infobase")
    )
    if used_in_distributed_infobase is not None:
        out["used_in_distributed_infobase"] = used_in_distributed_infobase

    scope = item.get("scope")
    if scope is not None:
        scope = str(scope).strip() or None
        if scope is not None:
            out["scope"] = scope

    hash_sum = item.get("hash_sum") if "hash_sum" in item else item.get("hash-sum")
    if hash_sum is not None:
        hash_sum = str(hash_sum).strip() or None
        if hash_sum is not None:
            out["hash_sum"] = hash_sum
    return out


def _try_parse_json(text: str) -> list[dict[str, Any]] | None:
    if not text or text[0] not in "[{":
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        return None

    if isinstance(parsed, list):
        return _normalize_extensions_list(parsed)
    if isinstance(parsed, dict):
        extensions = parsed.get("extensions")
        if isinstance(extensions, list):
            return _normalize_extensions_list(extensions)
    return None


_KV_KEY_RE = re.compile(r"([\w-]+)\s*:\s*", re.UNICODE)


def _try_parse_kv_records(text: str) -> list[dict[str, Any]] | None:
    matches = list(_KV_KEY_RE.finditer(text))
    if not matches:
        return None

    records: list[dict[str, Any]] = []
    current: dict[str, str] = {}

    def flush():
        normalized = _normalize_kv_record(current)
        if normalized is not None:
            records.append(normalized)

    for idx, match in enumerate(matches):
        key = match.group(1).strip().lower()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        value = text[start:end].strip()

        if key == "name" and current:
            flush()
            current = {}

        current[key] = value

    if current:
        flush()

    if not records:
        return None
    return records


def _normalize_kv_record(record: dict[str, str]) -> dict[str, Any] | None:
    name = _strip_quotes(record.get("name", "")).strip()
    if not name:
        return None

    out: dict[str, Any] = {"name": name}

    version = record.get("version")
    if version is not None:
        version = _strip_quotes(version).strip() or None
        if version is not None:
            out["version"] = version

    active = record.get("active")
    is_active = _coerce_bool(active)
    if is_active is not None:
        out["is_active"] = is_active

    purpose = record.get("purpose")
    if purpose is not None:
        purpose = _strip_quotes(purpose).strip() or None
        if purpose is not None:
            out["purpose"] = purpose

    safe_mode = _coerce_bool(record.get("safe-mode"))
    if safe_mode is not None:
        out["safe_mode"] = safe_mode

    security_profile_name = record.get("security-profile-name")
    if security_profile_name is not None:
        security_profile_name = _strip_quotes(security_profile_name).strip() or None
        if security_profile_name is not None:
            out["security_profile_name"] = security_profile_name

    unsafe_action_protection = _coerce_bool(record.get("unsafe-action-protection"))
    if unsafe_action_protection is not None:
        out["unsafe_action_protection"] = unsafe_action_protection

    used_in_distributed_infobase = _coerce_bool(record.get("used-in-distributed-infobase"))
    if used_in_distributed_infobase is not None:
        out["used_in_distributed_infobase"] = used_in_distributed_infobase

    scope = record.get("scope")
    if scope is not None:
        scope = _strip_quotes(scope).strip() or None
        if scope is not None:
            out["scope"] = scope

    hash_sum = record.get("hash-sum")
    if hash_sum is not None:
        hash_sum = _strip_quotes(hash_sum).strip() or None
        if hash_sum is not None:
            out["hash_sum"] = hash_sum

    return out


def _try_parse_table(text: str) -> list[dict[str, Any]] | None:
    lines = [ln.rstrip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln.strip()]
    if len(lines) < 2:
        return None

    delimiter = None
    if any("|" in ln for ln in lines[:3]):
        delimiter = "|"
    elif any("\t" in ln for ln in lines[:3]):
        delimiter = "\t"

    def split_line(line: str) -> list[str]:
        if delimiter == "|":
            return [part.strip() for part in line.split("|") if part.strip()]
        if delimiter == "\t":
            return [part.strip() for part in line.split("\t") if part.strip()]
        return [part.strip() for part in re.split(r"\s{2,}", line.strip()) if part.strip()]

    header = split_line(lines[0])
    if not header:
        return None

    col_map = _map_table_header(header)
    if not col_map.get("name"):
        return None

    out: list[dict[str, Any]] = []
    for line in lines[1:]:
        if set(line.strip()) <= {"-", "="}:
            continue
        parts = split_line(line)
        if len(parts) < len(header):
            continue
        row = dict(zip(header, parts))
        item: dict[str, Any] = {"name": str(row.get(col_map["name"]) or "").strip()}
        if not item["name"]:
            continue
        if col_map.get("version"):
            version = str(row.get(col_map["version"]) or "").strip()
            if version:
                item["version"] = version
        if col_map.get("active"):
            item_active = _coerce_bool(row.get(col_map["active"]))
            if item_active is not None:
                item["is_active"] = item_active
        out.append(item)

    if not out:
        return None
    return out


def _map_table_header(columns: list[str]) -> dict[str, str]:
    lowered = {col: col.strip().lower() for col in columns}

    def find(*names: str) -> str | None:
        for col, low in lowered.items():
            if low in names:
                return col
        return None

    out: dict[str, str] = {}
    name_col = find("name", "extension")
    if name_col:
        out["name"] = name_col
    version_col = find("version")
    if version_col:
        out["version"] = version_col
    active_col = find("active", "enabled")
    if active_col:
        out["active"] = active_col
    return out


def _strip_quotes(value: str) -> str:
    text = str(value or "").strip()
    if len(text) >= 2 and ((text[0] == text[-1] == '"') or (text[0] == text[-1] == "'")):
        return text[1:-1]
    return text


def _coerce_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    text = str(value).strip().lower()
    if text in {"true", "yes", "on", "enabled", "enable", "1"}:
        return True
    if text in {"false", "no", "off", "disabled", "disable", "0"}:
        return False
    return None
