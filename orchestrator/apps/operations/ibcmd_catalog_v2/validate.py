from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .common import (
    CATALOG_RISK_DANGEROUS,
    CATALOG_RISK_SAFE,
    CATALOG_SCOPE_GLOBAL,
    CATALOG_SCOPE_PER_DATABASE,
)


def validate_catalog_v2(catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if not isinstance(catalog, dict):
        return ["catalog must be an object"]

    if catalog.get("catalog_version") != 2:
        errors.append("catalog_version must be 2")

    driver = str(catalog.get("driver") or "").strip()
    if driver != "ibcmd":
        errors.append("driver must be ibcmd")

    commands_by_id = catalog.get("commands_by_id")
    if not isinstance(commands_by_id, dict):
        errors.append("commands_by_id must be an object")
        return errors

    for cmd_id, cmd in commands_by_id.items():
        if not isinstance(cmd_id, str) or not cmd_id:
            errors.append("command id must be a non-empty string")
            continue
        if not _is_valid_command_id(cmd_id):
            errors.append(f"command id invalid: {cmd_id}")
        if not isinstance(cmd, dict):
            errors.append(f"commands_by_id[{cmd_id}] must be an object")
            continue
        argv = cmd.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
            errors.append(f"{cmd_id}.argv must be a non-empty string array")
        else:
            expected_id = ".".join(argv)
            if cmd_id != expected_id:
                errors.append(f"{cmd_id} id mismatch: expected {expected_id}")
        scope = cmd.get("scope")
        if scope not in {CATALOG_SCOPE_PER_DATABASE, CATALOG_SCOPE_GLOBAL}:
            errors.append(f"{cmd_id}.scope must be per_database|global")
        risk = cmd.get("risk_level")
        if risk not in {CATALOG_RISK_SAFE, CATALOG_RISK_DANGEROUS}:
            errors.append(f"{cmd_id}.risk_level must be safe|dangerous")

        params_by_name = cmd.get("params_by_name") or {}
        if not isinstance(params_by_name, dict):
            errors.append(f"{cmd_id}.params_by_name must be an object")
            continue

        for name, param in params_by_name.items():
            if not isinstance(name, str) or not name:
                errors.append(f"{cmd_id} param name must be non-empty string")
                continue
            if not re.match(r"^[A-Za-z0-9_]+$", name):
                errors.append(f"{cmd_id} param name invalid: {name}")
            if not isinstance(param, dict):
                errors.append(f"{cmd_id}.{name} must be an object")
                continue
            kind = param.get("kind")
            if kind not in {"flag", "positional"}:
                errors.append(f"{cmd_id}.{name}.kind must be flag|positional")
            if not isinstance(param.get("required"), bool):
                errors.append(f"{cmd_id}.{name}.required must be boolean")
            if not isinstance(param.get("expects_value"), bool):
                errors.append(f"{cmd_id}.{name}.expects_value must be boolean")
            if kind == "flag":
                flag = param.get("flag")
                if not isinstance(flag, str) or not flag.startswith("-"):
                    errors.append(f"{cmd_id}.{name}.flag must be a flag string")
            if kind == "positional":
                pos = param.get("position")
                if not isinstance(pos, int) or pos < 1:
                    errors.append(f"{cmd_id}.{name}.position must be >= 1")

    return errors


def compute_catalog_fingerprint(catalog: dict[str, Any]) -> str:
    payload = json.dumps(
        catalog,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def _is_valid_command_id(value: str) -> bool:
    return bool(re.match(r"^[a-z0-9][a-z0-9.-]*(?:\.[a-z0-9][a-z0-9.-]*)*$", value))

