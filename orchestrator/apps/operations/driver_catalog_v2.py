from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

CATALOG_VERSION_V2 = 2

CATALOG_ALIAS_LATEST = "latest"
CATALOG_ALIAS_APPROVED = "approved"
CATALOG_ALIAS_ACTIVE = "active"

CATALOG_SCOPE_PER_DATABASE = "per_database"
CATALOG_SCOPE_GLOBAL = "global"

CATALOG_RISK_SAFE = "safe"
CATALOG_RISK_DANGEROUS = "dangerous"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def cli_catalog_v1_to_v2(cli_catalog: dict[str, Any]) -> dict[str, Any]:
    version = str(cli_catalog.get("version") or "").strip() or "unknown"
    source_hint = str(cli_catalog.get("source") or "").strip() or "legacy_cli_config"
    generated_at = str(cli_catalog.get("generated_at") or "").strip() or utc_now_iso()
    commands = cli_catalog.get("commands") or []

    commands_by_id: dict[str, Any] = {}
    for cmd in commands:
        if not isinstance(cmd, dict):
            continue
        cmd_id = str(cmd.get("id") or "").strip()
        if not cmd_id:
            continue

        params_by_name: dict[str, Any] = {}
        for raw_param in (cmd.get("params") or []):
            if not isinstance(raw_param, dict):
                continue
            name = str(raw_param.get("name") or "").strip()
            if not name:
                continue

            kind = str(raw_param.get("kind") or "").strip() or "flag"
            param: dict[str, Any] = {
                "kind": kind,
                "required": bool(raw_param.get("required", False)),
                "expects_value": bool(raw_param.get("expects_value", False)),
            }

            label = raw_param.get("label")
            if isinstance(label, str) and label:
                param["label"] = label

            if kind == "flag":
                flag = raw_param.get("flag")
                if isinstance(flag, str) and flag:
                    param["flag"] = flag
            elif kind == "positional":
                position = _extract_position_from_name(name)
                if position is not None:
                    param["position"] = position

            params_by_name[name] = param

        command_entry: dict[str, Any] = {
            "label": str(cmd.get("label") or cmd_id),
            "description": str(cmd.get("description") or ""),
            "argv": [f"/{cmd_id}"],
            "scope": CATALOG_SCOPE_PER_DATABASE,
            "risk_level": CATALOG_RISK_SAFE,
            "params_by_name": params_by_name,
        }

        source_section = cmd.get("source_section")
        if isinstance(source_section, str) and source_section:
            command_entry["source_section"] = source_section

        commands_by_id[cmd_id] = command_entry

    return {
        "catalog_version": CATALOG_VERSION_V2,
        "driver": "cli",
        "platform_version": version,
        "source": {"type": "legacy_cli_config", "hint": source_hint},
        "generated_at": generated_at,
        "commands_by_id": commands_by_id,
    }


def compute_etag(data: Any) -> str:
    payload = json.dumps(
        data,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"\"{hashlib.sha256(payload).hexdigest()}\""


def _extract_position_from_name(name: str) -> int | None:
    if name.startswith("arg") and name[3:].isdigit():
        return int(name[3:])
    return None
