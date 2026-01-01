"""
CLI command catalog loader/parser for designer_cli operations.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from django.conf import settings

logger = logging.getLogger(__name__)

_CACHE: dict | None = None

_COMMAND_RE = re.compile(r"^/([A-Za-z0-9][A-Za-z0-9_-]*)\b(.*)$")
_TOKEN_RE = re.compile(r"<[^>]+>|-[A-Za-z0-9_]+|\S+")


def _catalog_path() -> Path:
    return Path(settings.BASE_DIR).parent / "config" / "cli_commands.json"


def load_cli_command_catalog() -> dict:
    """
    Load CLI command catalog from config/cli_commands.json.
    Returns empty catalog if file is missing.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    catalog_path = _catalog_path()
    try:
        with catalog_path.open("r", encoding="utf-8") as handle:
            _CACHE = json.load(handle)
            return _CACHE
    except FileNotFoundError:
        logger.warning("CLI command catalog not found: %s", catalog_path)
    except json.JSONDecodeError as exc:
        logger.warning("CLI command catalog is invalid: %s", exc)
    except OSError as exc:
        logger.warning("Failed to read CLI command catalog: %s", exc)

    _CACHE = {"version": "unknown", "source": str(catalog_path), "commands": []}
    return _CACHE


def save_cli_command_catalog(catalog: dict) -> None:
    catalog_path = _catalog_path()
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    global _CACHE
    _CACHE = catalog


def build_cli_catalog_from_its(payload: dict[str, Any], *, source_hint: str | None = None) -> dict:
    version = str(payload.get("version") or "").strip() or "unknown"
    source = (
        str(source_hint)
        if source_hint
        else str(payload.get("doc_url") or payload.get("doc_id") or payload.get("frame_url") or "")
    ).strip() or "its_import"
    sections = payload.get("sections") or []
    commands: dict[str, dict[str, Any]] = {}

    for section in sections:
        if not isinstance(section, dict):
            continue
        text = str(section.get("text") or "")
        for command, usage, description in _iter_command_blocks(text):
            entry = _build_command_entry(
                command=command,
                usage=usage,
                description=description,
                section_id=section.get("id"),
                section_title=section.get("title"),
            )
            current = commands.get(command)
            commands[command] = _merge_command_entries(current, entry)

    sorted_commands = [commands[key] for key in sorted(commands.keys())]
    return {
        "version": version,
        "source": source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commands": sorted_commands,
    }


def validate_cli_catalog(catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(catalog, dict):
        return ["catalog must be an object"]
    if not str(catalog.get("version") or "").strip():
        errors.append("version is required")
    commands = catalog.get("commands")
    if commands is None:
        errors.append("commands is required")
    elif not isinstance(commands, list):
        errors.append("commands must be a list")
    else:
        for idx, cmd in enumerate(commands):
            if not isinstance(cmd, dict):
                errors.append(f"commands[{idx}] must be an object")
                continue
            if not str(cmd.get("id") or "").strip():
                errors.append(f"commands[{idx}].id is required")
    return errors


def _iter_command_blocks(text: str) -> Iterable[tuple[str, str, str]]:
    lines = text.splitlines()
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        match = _COMMAND_RE.match(line)
        if not match:
            idx += 1
            continue
        command = match.group(1)
        usage = line
        idx += 1
        desc_lines: list[str] = []
        while idx < len(lines):
            next_line = lines[idx].strip()
            if _COMMAND_RE.match(next_line):
                break
            desc_lines.append(lines[idx])
            idx += 1
        description = "\n".join(desc_lines).strip()
        yield command, usage, description


def _build_command_entry(
    *,
    command: str,
    usage: str,
    description: str,
    section_id: Any,
    section_title: Any,
) -> dict[str, Any]:
    usage_tail = usage[len(command) + 1 :].strip() if usage.startswith("/") else usage
    params = _parse_params(usage_tail)
    summary = _first_paragraph(description)
    return {
        "id": command,
        "label": command,
        "usage": usage,
        "description": summary,
        "params": params,
        "source_section_id": section_id,
        "source_section": section_title,
    }


def _merge_command_entries(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
    if not existing:
        return incoming
    merged = dict(existing)
    for key in ("usage", "description", "source_section_id", "source_section"):
        if not merged.get(key) and incoming.get(key):
            merged[key] = incoming[key]
    if len(incoming.get("params") or []) > len(merged.get("params") or []):
        merged["params"] = incoming.get("params", [])
    return merged


def _first_paragraph(text: str) -> str:
    if not text:
        return ""
    for chunk in text.split("\n\n"):
        stripped = chunk.strip()
        if stripped:
            return stripped
    return ""


def _parse_params(usage_tail: str) -> list[dict[str, Any]]:
    params: list[dict[str, Any]] = []
    used_names: set[str] = set()
    arg_index = 0

    optional_segments = re.findall(r"\[([^\]]+)\]", usage_tail)
    required_segment = re.sub(r"\[[^\]]+\]", " ", usage_tail)

    arg_index = _parse_segment(required_segment, True, params, used_names, arg_index)
    for segment in optional_segments:
        arg_index = _parse_segment(segment, False, params, used_names, arg_index)

    return params


def _parse_segment(
    segment: str,
    required: bool,
    params: list[dict[str, Any]],
    used_names: set[str],
    arg_index: int,
) -> int:
    normalized = segment.replace("|", " ")
    tokens = _TOKEN_RE.findall(normalized)
    idx = 0
    while idx < len(tokens):
        token = tokens[idx].strip()
        if not token:
            idx += 1
            continue
        if token.startswith("-"):
            flag = token
            label = None
            expects_value = False
            if idx + 1 < len(tokens) and tokens[idx + 1].startswith("<") and tokens[idx + 1].endswith(">"):
                expects_value = True
                label = tokens[idx + 1][1:-1].strip()
                idx += 1
            name = _unique_param_name(flag.lstrip("-") or "flag", used_names)
            params.append({
                "name": name,
                "kind": "flag",
                "flag": flag,
                "required": required,
                "label": label or flag,
                "expects_value": expects_value,
            })
        elif token.startswith("<") and token.endswith(">"):
            arg_index += 1
            label = token[1:-1].strip()
            name = _unique_param_name(f"arg{arg_index}", used_names)
            params.append({
                "name": name,
                "kind": "positional",
                "required": required,
                "label": label or name,
                "expects_value": True,
            })
        idx += 1
    return arg_index


def _unique_param_name(name: str, used: set[str]) -> str:
    base = name
    if base not in used:
        used.add(base)
        return base
    counter = 2
    while f"{base}_{counter}" in used:
        counter += 1
    unique = f"{base}_{counter}"
    used.add(unique)
    return unique
