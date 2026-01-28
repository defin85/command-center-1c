from __future__ import annotations

from typing import Any

from .common import (
    CATALOG_RISK_DANGEROUS,
    CATALOG_RISK_SAFE,
    CATALOG_SCOPE_GLOBAL,
    CATALOG_SCOPE_PER_DATABASE,
    _GROUP_RE,
    _INFO_TITLES,
    _MODE_RE,
    _RU_CLEAR_SUBSTR,
    _RU_DELETE_SUBSTR,
    _RU_GROUP_COMMANDS,
    _RU_NO_INFOBASE_CONNECT,
    _TITLE_RE,
    _TitleEntry,
)
from .parser import (
    _build_ibcmd_driver_schema_from_common_params,
    _find_common_params_section,
    _is_ascii_command_token,
    _iter_group_commands,
    _merge_params,
    _parse_command_text,
    _parse_group_params,
    _section_text_for_parser,
    _utc_now_iso,
)


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

    common_params_section = _find_common_params_section(payload)

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
            group_text = _section_text_for_parser(section)
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

            text = _section_text_for_parser(section)
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

    driver_schema = _build_ibcmd_driver_schema_from_common_params(common_params_section)

    return {
        "catalog_version": 2,
        "driver": "ibcmd",
        "driver_schema": driver_schema,
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

