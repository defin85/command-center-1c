from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable

from .common import (
    _COMMAND_NAME_RE,
    _COMMON_PARAMS_KEY_RENAMES,
    _COMMON_PARAMS_SECTION_PREFIX,
    _CREDENTIAL_SEMANTICS,
    _DESCRIPTION_HEADER_RE,
    _FLAG_VARIANT_RE,
    _GROUP_PARAMS_RE,
    _INFO_TITLES,
    _PARAM_SECTION_RE,
    _POSITIONAL_VARIANT_RE,
    _RU_ALLOWED_VALUES,
    _RU_BULLET,
    _RU_COMMON_PARAMS,
    _RU_DESCRIPTION,
    _RU_GROUP_COMMANDS,
    _RU_PARAM,
    _RU_PARAMS,
    _SHORT_FLAG_WITH_VALUE_RE,
)
from .schema_fallback import _ibcmd_driver_schema_fallback


def _find_common_params_section(payload: dict[str, Any]) -> dict[str, Any] | None:
    for section in payload.get("sections") or []:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title") or "").strip()
        if not title.startswith(_COMMON_PARAMS_SECTION_PREFIX):
            continue
        if _RU_COMMON_PARAMS not in title:
            continue
        return section
    return None


def _iter_common_params_rows(section: dict[str, Any]) -> Iterable[tuple[str, str]]:
    blocks = section.get("blocks")
    if not isinstance(blocks, list):
        return

    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("kind") != "table":
            continue
        rows = block.get("rows")
        if not isinstance(rows, list) or len(rows) < 2:
            continue
        header = rows[0]
        if not isinstance(header, list) or len(header) < 2:
            continue
        if str(header[0] or "").strip() != _RU_PARAM:
            continue
        if str(header[1] or "").strip() != _RU_DESCRIPTION:
            continue
        for row in rows[1:]:
            if not isinstance(row, list) or len(row) < 2:
                continue
            variants_cell = str(row[0] or "").strip()
            desc_cell = str(row[1] or "").strip()
            if not variants_cell:
                continue
            yield variants_cell, desc_cell


def _split_common_param_variants(cell: str) -> list[str]:
    tokens = [t for t in str(cell or "").split() if t]
    variants: list[str] = []
    current: list[str] = []
    for tok in tokens:
        if tok.startswith("-"):
            if current:
                variants.append(" ".join(current))
            current = [tok]
            continue
        if current:
            current.append(tok)
    if current:
        variants.append(" ".join(current))
    return variants


def _pick_canonical_long_flag(flag_tokens: list[str]) -> str:
    long_flags = [t for t in flag_tokens if t.startswith("--")]
    if not long_flags:
        return flag_tokens[0] if flag_tokens else ""
    # Prefer shorter canonical long flag (keeps stable db_* variants vs database_*).
    return sorted(set(long_flags), key=lambda t: (len(t), t))[0]


def _build_driver_flag_schema(*, variants_cell: str, description: str) -> tuple[str, dict[str, Any]] | None:
    variants = _split_common_param_variants(variants_cell)
    if not variants:
        return None

    flag_tokens: list[str] = []
    expects_value = False
    for v in variants:
        tok, exp = _parse_flag_variant(v)
        if not tok:
            continue
        flag_tokens.append(tok)
        expects_value = expects_value or exp

    if not flag_tokens:
        return None

    canonical_flag = _pick_canonical_long_flag(flag_tokens)
    aliases = sorted({t for t in flag_tokens if t and t != canonical_flag}, key=_flag_preference_key)

    key = _flag_name_to_param_name(canonical_flag)
    key = _COMMON_PARAMS_KEY_RENAMES.get(key, key)

    value_type = "bool"
    if expects_value:
        value_type = "int" if key == "pid" else "string"

    schema: dict[str, Any] = {
        "kind": "flag",
        "flag": canonical_flag,
        "expects_value": expects_value,
        "required": False,
        "label": canonical_flag,
        "description": _first_paragraph(description or ""),
        "value_type": value_type,
    }

    enum_values = _extract_enum(description or "")
    if enum_values:
        schema["enum"] = enum_values

    if aliases:
        schema["ui"] = {"aliases": aliases}

    return key, schema


def _build_ibcmd_driver_schema_from_common_params(common_params_section: dict[str, Any] | None) -> dict[str, Any]:
    """
    Extends the fallback schema with all common flags from 4.10.2 (including aliases).

    Note: only the driver_schema is derived from 4.10.2; command params are still parsed from their own sections.
    """
    schema = _ibcmd_driver_schema_fallback()
    if not isinstance(common_params_section, dict):
        return schema

    connection = schema.get("connection")
    if not isinstance(connection, dict):
        connection = {}
        schema["connection"] = connection

    offline = connection.get("offline")
    if not isinstance(offline, dict):
        offline = {}
        connection["offline"] = offline

    base_ib_auth = schema.get("ib_auth") if isinstance(schema.get("ib_auth"), dict) else {}
    ib_auth: dict[str, Any] = {}
    connection_paths: list[str] = ["connection.remote", "connection.pid"]

    for variants_cell, desc in _iter_common_params_rows(common_params_section):
        built = _build_driver_flag_schema(variants_cell=variants_cell, description=desc)
        if not built:
            continue
        key, flag_schema = built

        if key in {"db_user", "db_pwd"}:
            flag_schema["semantics"] = _CREDENTIAL_SEMANTICS[key]
            if key == "db_pwd":
                flag_schema["sensitive"] = True

        if key in {"remote", "pid"}:
            connection[key] = flag_schema
            connection_paths.append(f"connection.{key}")
            continue

        if key in {"user", "password"}:
            flag_schema["semantics"] = _CREDENTIAL_SEMANTICS[key]
            if key == "password":
                flag_schema["sensitive"] = True
            ib_auth[key] = flag_schema
            continue

        prev = offline.get(key)
        if isinstance(prev, dict) and prev.get("sensitive") is True and flag_schema.get("sensitive") is not True:
            flag_schema["sensitive"] = True
        offline[key] = flag_schema
        connection_paths.append(f"connection.offline.{key}")

    if ib_auth:
        if "strategy" in base_ib_auth and "strategy" not in ib_auth:
            ib_auth["strategy"] = base_ib_auth.get("strategy")
        schema["ib_auth"] = ib_auth
        ui = schema.get("ui")
        if isinstance(ui, dict):
            sections = ui.get("sections")
            if isinstance(sections, list):
                for sec in sections:
                    if isinstance(sec, dict) and sec.get("id") == "ibcmd.auth":
                        paths = sec.get("paths")
                        if isinstance(paths, list):
                            for p in ("ib_auth.strategy", "ib_auth.user", "ib_auth.password"):
                                if p not in paths:
                                    paths.append(p)
                        break

    ui = schema.get("ui")
    if isinstance(ui, dict):
        sections = ui.get("sections")
        if isinstance(sections, list):
            for sec in sections:
                if not isinstance(sec, dict):
                    continue
                if sec.get("id") != "ibcmd.connection":
                    continue
                sec["paths"] = sorted(set(connection_paths), key=lambda p: (0 if p.startswith("connection.") else 1, p))
                break

    return schema


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
            if not line:
                idx += 1
                continue
            if not line.startswith(_RU_BULLET):
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


def _section_text_for_parser(section: dict[str, Any]) -> str:
    blocks = section.get("blocks")
    if isinstance(blocks, list):
        lines = _blocks_to_lines(blocks)
        if lines:
            return "\n".join(lines)
    return str(section.get("text") or "")


def _blocks_to_lines(blocks: list[Any]) -> list[str]:
    lines: list[str] = []
    prev_is_bullet = False
    for block in blocks:
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if not isinstance(text, str):
            continue
        text = text.strip()
        if not text:
            continue
        is_bullet = text.startswith(_RU_BULLET)
        if lines and not (prev_is_bullet and is_bullet):
            lines.append("")
        lines.append(text)
        prev_is_bullet = is_bullet
    return lines


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

