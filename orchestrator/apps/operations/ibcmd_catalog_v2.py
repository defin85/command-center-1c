from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from .driver_catalog_v2 import (
    CATALOG_RISK_DANGEROUS,
    CATALOG_RISK_SAFE,
    CATALOG_SCOPE_GLOBAL,
    CATALOG_SCOPE_PER_DATABASE,
)

_RU_MODE = "\u0420\u0435\u0436\u0438\u043c"
_RU_GROUP_COMMANDS = "\u041a\u043e\u043c\u0430\u043d\u0434\u044b \u0433\u0440\u0443\u043f\u043f\u044b"
_RU_PARAM = "\u041f\u0430\u0440\u0430\u043c\u0435\u0442\u0440"
_RU_PARAMS = "\u041f\u0430\u0440\u0430\u043c\u0435\u0442\u0440\u044b"
_RU_DESCRIPTION = "\u041e\u043f\u0438\u0441\u0430\u043d\u0438\u0435"
_RU_GENERAL_INFO = "\u041e\u0431\u0449\u0430\u044f \u0438\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u044f"
_RU_COMMON_PARAMS = "\u041e\u0431\u0449\u0438\u0435 \u043f\u0430\u0440\u0430\u043c\u0435\u0442\u0440\u044b"
_RU_ALLOWED_VALUES = "\u0414\u043e\u043f\u0443\u0441\u0442\u0438\u043c\u044b\u0435 \u0437\u043d\u0430\u0447\u0435\u043d\u0438\u044f"
_RU_BULLET = "\u25cf"
_RU_NO_INFOBASE_CONNECT = (
    "\u043d\u0435 \u0432\u044b\u043f\u043e\u043b\u043d\u044f\u0435\u0442 "
    "\u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435 "
    "\u043a \u0438\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u043e\u043d\u043d\u043e\u0439 \u0431\u0430\u0437\u0435"
)
_RU_DELETE_SUBSTR = "\u0443\u0434\u0430\u043b"
_RU_CLEAR_SUBSTR = "\u043e\u0447\u0438\u0441\u0442"

_TITLE_RE = re.compile(r"^(4\.10(?:\.\d+)*)\.\s*(.+)$")
_MODE_RE = re.compile(rf"^{_RU_MODE}\s+([A-Za-z0-9][A-Za-z0-9-]*)\b")
_GROUP_RE = re.compile(rf"^{_RU_GROUP_COMMANDS}\s+([A-Za-z0-9][A-Za-z0-9-]*)\b")
_COMMAND_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*(?: [a-z0-9-]+)*$")

_PARAM_SECTION_RE = re.compile(rf"^{_RU_PARAM}(?:\u044b)?\b", re.IGNORECASE)
_DESCRIPTION_HEADER_RE = re.compile(rf"^{_RU_DESCRIPTION}\b", re.IGNORECASE)
_GROUP_PARAMS_RE = re.compile(rf"^{_RU_PARAMS}\s+([A-Za-z0-9][A-Za-z0-9-]*)\b")

_FLAG_VARIANT_RE = re.compile(r"^(--?[A-Za-z0-9][A-Za-z0-9-]*)(?:=(<[^>]+>))?$")
_SHORT_FLAG_WITH_VALUE_RE = re.compile(r"^(-[A-Za-z0-9])\s+(<[^>]+>)$")
_POSITIONAL_VARIANT_RE = re.compile(r"^(<[^>]+>)$")

_INFO_TITLES = {
    _RU_GENERAL_INFO,
    _RU_COMMON_PARAMS,
}


@dataclass(frozen=True)
class _TitleEntry:
    kind: str  # mode|group|command|info
    token: str | None = None
    command_tokens: list[str] | None = None


def build_base_catalog_from_its(payload: dict[str, Any]) -> dict[str, Any]:
    platform_version = str(payload.get("version") or "").strip() or "unknown"
    doc_id = (
        str(payload.get("pointer_ti") or payload.get("current_ti") or payload.get("outer_pointer_ti") or "").strip()
        or str(payload.get("doc_id") or "").strip()
        or "unknown"
    )
    doc_url = str(payload.get("doc_url") or payload.get("page_url") or payload.get("frame_url") or "").strip()

    commands_by_id: dict[str, Any] = {}
    stack: dict[int, _TitleEntry] = {}

    for section in payload.get("sections") or []:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title") or "").strip()
        if not title.startswith("4.10."):
            continue

        match = _TITLE_RE.match(title)
        if not match:
            continue

        section_num = match.group(1)
        suffix = match.group(2).strip()
        depth = len(section_num.split(".")) - 2

        entry = _classify_title_suffix(suffix)
        stack[depth] = entry
        for key in list(stack.keys()):
            if key > depth:
                del stack[key]

        if entry.kind == "info":
            continue

        if entry.kind == "mode":
            continue

        if entry.kind == "group":
            group_text = str(section.get("text") or "")
            prefix_tokens = _normalize_argv_prefix(_build_argv_prefix(stack))
            group_params = _parse_group_params(group_text)
            for cmd_name, cmd_desc, cmd_desc_full, cmd_params in _iter_group_commands(group_text):
                argv = prefix_tokens + cmd_name.split()
                _upsert_command(
                    commands_by_id,
                    argv=argv,
                    title=title,
                    description=cmd_desc,
                    inference_text=cmd_desc_full,
                    params_by_name=_merge_params(group_params, cmd_params),
                    mode=_extract_mode_token(stack),
                )
            continue

        if entry.kind == "command":
            cmd_tokens = entry.command_tokens or []
            if not cmd_tokens:
                continue
            argv_prefix = _normalize_argv_prefix(_build_argv_prefix(stack))
            argv = argv_prefix + cmd_tokens

            text = str(section.get("text") or "")
            cmd_desc, cmd_desc_full, cmd_params = _parse_command_text(text)
            _upsert_command(
                commands_by_id,
                argv=argv,
                title=title,
                description=cmd_desc,
                inference_text=cmd_desc_full,
                params_by_name=cmd_params,
                mode=_extract_mode_token(stack),
            )
            continue

    return {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": platform_version,
        "source": {
            "type": "its_import",
            "doc_id": doc_id,
            "doc_url": doc_url,
            "section_prefix": "4.10",
        },
        "generated_at": _utc_now_iso(),
        "commands_by_id": commands_by_id,
    }


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


def _classify_title_suffix(suffix: str) -> _TitleEntry:
    if suffix in _INFO_TITLES:
        return _TitleEntry(kind="info")

    mode_match = _MODE_RE.match(suffix)
    if mode_match:
        return _TitleEntry(kind="mode", token=mode_match.group(1))

    group_match = _GROUP_RE.match(suffix)
    if group_match:
        return _TitleEntry(kind="group", token=group_match.group(1))

    if suffix.startswith(_RU_GROUP_COMMANDS):
        return _TitleEntry(kind="info")

    tokens = [t for t in suffix.split() if t]
    if not tokens:
        return _TitleEntry(kind="info")

    if not all(_is_ascii_command_token(t) for t in tokens):
        return _TitleEntry(kind="info")

    return _TitleEntry(kind="command", command_tokens=tokens)


def _build_argv_prefix(stack: dict[int, _TitleEntry]) -> list[str]:
    prefix: list[str] = []
    for depth in sorted(stack.keys()):
        entry = stack[depth]
        if entry.kind == "mode" and entry.token:
            prefix = [entry.token]
        elif entry.kind == "group" and entry.token:
            prefix.append(entry.token)
    return prefix


def _extract_mode_token(stack: dict[int, _TitleEntry]) -> str:
    for depth in sorted(stack.keys()):
        entry = stack[depth]
        if entry.kind == "mode" and entry.token:
            return entry.token
    return ""


def _normalize_argv_prefix(prefix: list[str]) -> list[str]:
    if prefix[:3] == ["infobase", "config", "extension"]:
        return ["infobase", "extension"]
    return prefix


def _iter_group_commands(text: str) -> Iterable[tuple[str, str, str, dict[str, Any]]]:
    lines = _split_lines(text)
    idx = 0
    while idx < len(lines):
        name = lines[idx].strip()
        if not _is_command_heading(name):
            idx += 1
            continue

        idx += 1
        while idx < len(lines) and not lines[idx].strip():
            idx += 1

        desc_lines: list[str] = []
        while idx < len(lines):
            cur = lines[idx].strip()
            if _is_command_heading(cur):
                break
            if _PARAM_SECTION_RE.match(cur):
                break
            desc_lines.append(lines[idx])
            idx += 1

        desc_raw = "\n".join(desc_lines).strip()
        description = _first_paragraph(desc_raw)

        params_by_name: dict[str, Any] = {}
        if idx < len(lines) and _PARAM_SECTION_RE.match(lines[idx].strip()):
            idx = _skip_param_headers(lines, idx)
            params_by_name, idx = _parse_params(lines, idx, stop_at_command=True)

        yield name, description, desc_raw, params_by_name


def _parse_group_params(text: str) -> dict[str, Any]:
    lines = _split_lines(text)
    for idx, raw in enumerate(lines):
        match = _GROUP_PARAMS_RE.match(raw.strip())
        if not match:
            continue
        idx = idx + 1
        while idx < len(lines) and not _PARAM_SECTION_RE.match(lines[idx].strip()):
            idx += 1
        if idx >= len(lines):
            return {}
        idx = _skip_param_headers(lines, idx)
        params_by_name, _ = _parse_params(lines, idx, stop_at_command=True)
        return params_by_name
    return {}


def _parse_command_text(text: str) -> tuple[str, str, dict[str, Any]]:
    lines = _split_lines(text)
    idx = 0
    desc_lines: list[str] = []
    while idx < len(lines) and not _PARAM_SECTION_RE.match(lines[idx].strip()):
        desc_lines.append(lines[idx])
        idx += 1
    desc_raw = "\n".join(desc_lines).strip()
    description = _first_paragraph(desc_raw)
    if idx >= len(lines):
        return description, desc_raw, {}
    idx = _skip_param_headers(lines, idx)
    params_by_name, _ = _parse_params(lines, idx, stop_at_command=False)
    return description, desc_raw, params_by_name


def _skip_param_headers(lines: list[str], idx: int) -> int:
    while idx < len(lines) and not _DESCRIPTION_HEADER_RE.match(lines[idx].strip()):
        idx += 1
    if idx < len(lines) and _DESCRIPTION_HEADER_RE.match(lines[idx].strip()):
        idx += 1
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    return idx


def _parse_params(
    lines: list[str],
    idx: int,
    *,
    stop_at_command: bool,
) -> tuple[dict[str, Any], int]:
    params_by_name: dict[str, Any] = {}
    positional_index = 0
    while idx < len(lines):
        cur = lines[idx].strip()
        if stop_at_command and _is_command_heading(cur):
            break
        if not cur:
            idx += 1
            continue
        if not _is_param_variant(cur):
            idx += 1
            continue

        variants, idx = _collect_variants(lines, idx)
        desc, idx = _collect_param_description(lines, idx, stop_at_command=stop_at_command)

        param = _build_param_from_variants(variants, desc, positional_index)
        if param.get("kind") == "positional":
            positional_index += 1

        name = str(param.get("name") or "")
        if not name:
            continue
        param.pop("name", None)
        params_by_name[name] = param

    return params_by_name, idx


def _collect_variants(lines: list[str], idx: int) -> tuple[list[str], int]:
    variants: list[str] = []
    while idx < len(lines):
        cur = lines[idx].strip()
        if not cur:
            idx += 1
            continue
        if not _is_param_variant(cur):
            break
        variants.append(cur)
        idx += 1
    return variants, idx


def _collect_param_description(
    lines: list[str],
    idx: int,
    *,
    stop_at_command: bool,
) -> tuple[str, int]:
    desc_lines: list[str] = []
    while idx < len(lines):
        cur = lines[idx].strip()
        if stop_at_command and _is_command_heading(cur):
            break
        if _is_param_variant(cur):
            break
        desc_lines.append(lines[idx])
        idx += 1
    return "\n".join(desc_lines).strip(), idx


def _build_param_from_variants(variants: list[str], description: str, positional_index: int) -> dict[str, Any]:
    long_flags: list[str] = []
    other_flags: list[str] = []
    positionals: list[str] = []

    for v in variants:
        if v.startswith("--"):
            long_flags.append(v)
        elif v.startswith("-"):
            other_flags.append(v)
        else:
            positionals.append(v)

    if positionals:
        return {
            "name": f"arg{positional_index + 1}",
            "kind": "positional",
            "position": positional_index + 1,
            "required": False,
            "expects_value": True,
            "label": _render_positional_label(positionals[0]),
            "description": _first_paragraph(description),
        }

    flag_tokens: list[str] = []
    expects_value = False
    for v in long_flags + other_flags:
        tok, exp = _parse_flag_variant(v)
        if not tok:
            continue
        flag_tokens.append(tok)
        expects_value = expects_value or exp

    unique_tokens = sorted(set(flag_tokens), key=_flag_preference_key)
    flag_token = unique_tokens[0] if unique_tokens else ""
    name = _flag_name_to_param_name(flag_token) if flag_token else ""

    aliases = [t for t in unique_tokens[1:] if t and t != flag_token]

    param: dict[str, Any] = {
        "name": name,
        "kind": "flag",
        "flag": flag_token,
        "required": False,
        "expects_value": expects_value,
        "label": flag_token,
        "description": _first_paragraph(description),
    }

    enum_values = _extract_enum(description)
    if enum_values:
        param["enum"] = enum_values

    if aliases:
        param["ui"] = {"aliases": aliases}

    return param


def _parse_flag_variant(variant: str) -> tuple[str, bool]:
    variant = variant.strip()
    if not variant:
        return "", False

    # ITS sometimes renders variants with extra placeholders/units on the same line,
    # e.g. "--follow=<timeout> <ms>" or "-F <timeout> <ms>". We keep only the flag
    # token and infer expects_value from the presence of placeholders.
    parts = variant.split()
    first = parts[0].strip().strip(";,")

    if "=" in first:
        return first.split("=", 1)[0], True

    expects_value = any(_POSITIONAL_VARIANT_RE.match(p) for p in parts[1:])

    match = _FLAG_VARIANT_RE.match(first)
    if match:
        flag_token = match.group(1)
        expects_value = expects_value or bool(match.group(2))
        return flag_token, expects_value

    match = _SHORT_FLAG_WITH_VALUE_RE.match(variant)
    if match:
        return match.group(1), True

    return first, expects_value


def _render_positional_label(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("<") and raw.endswith(">"):
        return raw[1:-1].strip()
    return raw


def _extract_enum(description: str) -> list[str]:
    values: list[str] = []
    lines = _split_lines(description)
    idx = 0
    while idx < len(lines):
        if _RU_ALLOWED_VALUES not in lines[idx]:
            idx += 1
            continue
        idx += 1
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        while idx < len(lines):
            line = lines[idx].strip()
            if not line or not line.startswith(_RU_BULLET):
                break
            item = line.lstrip(_RU_BULLET).strip()
            token = item.split()[0].strip(";,")
            for part in token.split(","):
                v = part.strip().strip(";,")
                if v and v not in values and _is_ascii_command_token(v):
                    values.append(v)
            idx += 1
        break
    return values


def _is_param_variant(line: str) -> bool:
    if line.startswith("--") or line.startswith("-"):
        return True
    if _POSITIONAL_VARIANT_RE.match(line):
        return True
    if re.match(r"^[A-Za-z][A-Za-z0-9_-]*$", line):
        return True
    return False


def _is_command_heading(line: str) -> bool:
    line = line.strip()
    if not line:
        return False
    if line.startswith("-") or line.startswith("<"):
        return False
    return bool(_COMMAND_NAME_RE.match(line))


def _is_ascii_command_token(token: str) -> bool:
    return bool(re.match(r"^[A-Za-z0-9][A-Za-z0-9-]*$", token))


def _flag_name_to_param_name(flag: str) -> str:
    name = flag.lstrip("-").replace("-", "_")
    return name.lower()


def _flag_preference_key(token: str) -> tuple[int, int, str]:
    is_long = token.startswith("--")
    return (0 if is_long else 1, -len(token), token)


def _merge_params(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        merged[key] = value
    return merged


def _infer_scope(mode: str, text: str) -> str:
    if _RU_NO_INFOBASE_CONNECT in text:
        return CATALOG_SCOPE_GLOBAL
    if mode in {"server", "session", "lock", "eventlog", "binary-data-storage"}:
        return CATALOG_SCOPE_GLOBAL
    return CATALOG_SCOPE_PER_DATABASE


def _infer_risk(argv: list[str], text: str) -> str:
    tokens = set(argv)
    dangerous_tokens = {
        "clear",
        "restore",
        "delete",
        "terminate",
        "interrupt-current-server-call",
        "load-diff-backup",
        "load-full-backup",
    }
    if tokens & dangerous_tokens:
        return CATALOG_RISK_DANGEROUS
    if any(t.startswith("load-") for t in tokens):
        return CATALOG_RISK_DANGEROUS
    if _RU_DELETE_SUBSTR in text.lower() or _RU_CLEAR_SUBSTR in text.lower():
        return CATALOG_RISK_DANGEROUS
    return CATALOG_RISK_SAFE


def _upsert_command(
    commands_by_id: dict[str, Any],
    *,
    argv: list[str],
    title: str,
    description: str,
    inference_text: str,
    params_by_name: dict[str, Any],
    mode: str,
) -> None:
    if not argv:
        return

    cmd_id = ".".join(argv)
    scope = _infer_scope(mode, inference_text)
    risk = _infer_risk(argv, inference_text)

    command: dict[str, Any] = {
        "label": " ".join(argv),
        "description": description,
        "argv": argv,
        "scope": scope,
        "risk_level": risk,
    }
    if params_by_name:
        command["params_by_name"] = params_by_name
    if title:
        command["source_section"] = title

    existing = commands_by_id.get(cmd_id)
    if isinstance(existing, dict) and existing.get("params_by_name") and not params_by_name:
        return
    commands_by_id[cmd_id] = command


def _is_valid_command_id(value: str) -> bool:
    return bool(re.match(r"^[a-z0-9][a-z0-9.-]*(?:\.[a-z0-9][a-z0-9.-]*)*$", value))


def _first_paragraph(text: str) -> str:
    if not text:
        return ""
    for chunk in text.split("\n\n"):
        stripped = chunk.strip()
        if stripped:
            return stripped
    return ""


def _split_lines(text: str) -> list[str]:
    return text.splitlines() if text else []


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
