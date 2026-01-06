from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger(__name__)


_INFOBASE_AUTH_PARAM_NAMES = {"user", "password"}
_INFOBASE_AUTH_FLAG_PREFIXES = ("--user", "--password")

_SENSITIVE_FLAG_PREFIXES = (
    "--db-pwd",
    "--db-password",
    "--password",
    "--target-database-password",
    "--target-db-password",
    "--target-db-pwd",
    "--secret",
    "--token",
    "--api-key",
)


def flatten_connection_params(connection: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(connection, dict):
        return {}

    params: dict[str, Any] = {}

    remote = connection.get("remote")
    if remote is not None:
        params["remote"] = remote

    pid = connection.get("pid")
    if pid is not None:
        params["pid"] = pid

    offline = connection.get("offline")
    if isinstance(offline, dict):
        for key in ("config", "data", "dbms", "db_server", "db_name", "db_user", "db_pwd"):
            if key in offline:
                params[key] = offline.get(key)

    return params


def strip_infobase_auth_params(params: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(params, dict) or not params:
        return {}
    cleaned = dict(params)
    for key in list(cleaned.keys()):
        if str(key).strip().lower() in _INFOBASE_AUTH_PARAM_NAMES:
            cleaned.pop(key, None)
    return cleaned


def strip_infobase_auth_args(args: list[str]) -> list[str]:
    if not args:
        return []

    result: list[str] = []
    idx = 0
    while idx < len(args):
        token = str(args[idx] or "")
        stripped = token.strip()
        lowered = stripped.lower()

        if any(lowered.startswith(prefix) for prefix in _INFOBASE_AUTH_FLAG_PREFIXES):
            if "=" in stripped:
                idx += 1
                continue
            idx += 2
            continue

        result.append(stripped)
        idx += 1

    return [token for token in result if token]


def build_ibcmd_cli_argv(
    *,
    command: dict[str, Any],
    params: dict[str, Any],
    additional_args: list[str],
) -> tuple[list[str], list[str]]:
    argv = command.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x.strip() for x in argv):
        raise ValueError("command.argv must be a non-empty string array")

    params_by_name = command.get("params_by_name") or {}
    if params_by_name and not isinstance(params_by_name, dict):
        raise ValueError("command.params_by_name must be an object")

    normalized_params: dict[str, Any] = strip_infobase_auth_params(params or {})
    extra_args = strip_infobase_auth_args(additional_args or [])

    if not isinstance(normalized_params, dict):
        raise ValueError("params must be an object")

    if params_by_name:
        unknown = [key for key in normalized_params.keys() if key not in params_by_name]
        if unknown:
            raise ValueError(f"unknown params: {', '.join(sorted(str(k) for k in unknown))}")
    else:
        if normalized_params:
            raise ValueError("params are not supported for this command")

    flags: list[str] = []
    positionals: list[tuple[int, str]] = []

    for name, schema in (params_by_name or {}).items():
        if not isinstance(schema, dict):
            continue
        if name not in normalized_params:
            if schema.get("required") is True:
                raise ValueError(f"missing required param: {name}")
            continue

        raw_value = normalized_params.get(name)
        if raw_value is None or raw_value == "":
            if schema.get("required") is True:
                raise ValueError(f"missing required param: {name}")
            continue

        kind = str(schema.get("kind") or "").strip()
        if kind == "positional":
            pos = schema.get("position")
            if not isinstance(pos, int) or pos < 1:
                raise ValueError(f"{name}.position must be >= 1")
            positionals.append((pos, _stringify_value(raw_value, name=name)))
            continue

        if kind != "flag":
            raise ValueError(f"{name}.kind must be flag|positional")

        flag = schema.get("flag")
        if not isinstance(flag, str) or not flag.startswith("-"):
            raise ValueError(f"{name}.flag must be a flag string")

        expects_value = bool(schema.get("expects_value", False))
        if not expects_value:
            if _is_truthy(raw_value):
                flags.append(flag)
            continue

        if isinstance(raw_value, (list, tuple)):
            values = [_stringify_value(v, name=name) for v in raw_value]
        else:
            values = [_stringify_value(raw_value, name=name)]

        enum_values = schema.get("enum")
        if enum_values is not None:
            if not isinstance(enum_values, list) or not all(isinstance(x, str) and x for x in enum_values):
                raise ValueError(f"{name}.enum must be a string array")
            for value in values:
                if value not in enum_values:
                    raise ValueError(f"invalid {name}: {value!r} (allowed: {', '.join(enum_values)})")

        for value in values:
            flags.append(f"{flag}={value}")

    flags.sort()
    positionals.sort(key=lambda item: item[0])

    argv_out = [token.strip() for token in argv] + flags + [v for _, v in positionals] + extra_args
    masked = mask_argv(argv_out)
    return argv_out, masked


def build_ibcmd_cli_argv_manual(
    *,
    command: dict[str, Any],
    params: dict[str, Any],
    additional_args: list[str],
) -> tuple[list[str], list[str]]:
    argv = command.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x.strip() for x in argv):
        raise ValueError("command.argv must be a non-empty string array")

    params_by_name = command.get("params_by_name") or {}
    if params_by_name and not isinstance(params_by_name, dict):
        raise ValueError("command.params_by_name must be an object")

    normalized_params: dict[str, Any] = strip_infobase_auth_params(params or {})
    extra_args = strip_infobase_auth_args(additional_args or [])

    if not isinstance(normalized_params, dict):
        raise ValueError("params must be an object")

    flags: list[str] = []
    positionals: list[tuple[int, str]] = []

    for name, schema in (params_by_name or {}).items():
        if not isinstance(schema, dict):
            continue
        if name not in normalized_params:
            continue

        raw_value = normalized_params.get(name)
        if raw_value is None or raw_value == "":
            continue

        kind = str(schema.get("kind") or "").strip()
        if kind == "positional":
            pos = schema.get("position")
            if not isinstance(pos, int) or pos < 1:
                continue
            positionals.append((pos, _stringify_value(raw_value, name=name)))
            continue

        if kind != "flag":
            continue

        flag = schema.get("flag")
        if not isinstance(flag, str) or not flag.startswith("-"):
            continue

        expects_value = bool(schema.get("expects_value", False))
        if not expects_value:
            if _is_truthy(raw_value):
                flags.append(flag)
            continue

        if isinstance(raw_value, (list, tuple)):
            values = [_stringify_value(v, name=name) for v in raw_value]
        else:
            values = [_stringify_value(raw_value, name=name)]

        enum_values = schema.get("enum")
        if enum_values is not None:
            if not isinstance(enum_values, list) or not all(isinstance(x, str) and x for x in enum_values):
                raise ValueError(f"{name}.enum must be a string array")
            for value in values:
                if value not in enum_values:
                    raise ValueError(f"invalid {name}: {value!r} (allowed: {', '.join(enum_values)})")

        for value in values:
            if value:
                flags.append(f"{flag}={value}")

    flags.sort()
    positionals.sort(key=lambda item: item[0])

    argv_out = [token.strip() for token in argv] + flags + [v for _, v in positionals] + extra_args
    masked = mask_argv(argv_out)
    return argv_out, masked


def mask_argv(argv: list[str]) -> list[str]:
    if not argv:
        return []

    masked: list[str] = []
    idx = 0
    while idx < len(argv):
        token = str(argv[idx] or "")
        stripped = token.strip()
        lowered = stripped.lower()

        matched_prefix = None
        for prefix in _SENSITIVE_FLAG_PREFIXES:
            if lowered == prefix or lowered.startswith(prefix + "="):
                matched_prefix = prefix
                break

        if matched_prefix is not None:
            if "=" in stripped:
                masked.append(stripped.split("=", 1)[0] + "=***")
                idx += 1
                continue
            masked.append(stripped)
            if idx + 1 < len(argv):
                masked.append("***")
                idx += 2
                continue
            idx += 1
            continue

        masked.append(stripped)
        idx += 1

    return masked


def _is_truthy(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"", "0", "false", "no", "off"}:
            return False
        return True
    return True


def _stringify_value(value: Any, *, name: str) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        logger.debug("Failed to stringify param %s=%r", name, value)
        return ""
