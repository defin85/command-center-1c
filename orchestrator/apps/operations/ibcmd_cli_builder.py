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

_CONNECTION_PARAM_FLAGS = {
    "remote": "--remote",
    "pid": "--pid",
    "config": "--config",
    "data": "--data",
    "dbms": "--dbms",
    "db_server": "--db-server",
    "db_name": "--db-name",
    "db_user": "--db-user",
    "db_pwd": "--db-pwd",
}

_CONNECTION_FLAG_PREFIXES_BY_KEY: dict[str, tuple[str, ...]] = {
    "remote": ("--remote", "-r"),
    "pid": ("--pid", "-p"),
    "config": ("--config", "-c"),
    "data": ("--data", "-d"),
    "dbms": ("--dbms",),
    "db_server": ("--db-server", "--database-server"),
    "db_name": ("--db-name", "--database-name"),
    "db_user": ("--db-user", "--database-user"),
    "db_pwd": ("--db-pwd", "--database-password"),
}


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


def detect_connection_option_conflicts(*, connection_params: dict[str, Any], additional_args: list[str]) -> list[str]:
    """
    Returns list of connection option keys that are also present in additional_args.

    This is used to enforce a strict policy for driver-level flags:
    duplicates across connection vs additional_args should be treated as validation errors.
    """
    if not isinstance(connection_params, dict) or not connection_params:
        return []
    if not isinstance(additional_args, list) or not additional_args:
        return []

    normalized_args: list[str] = []
    for raw in additional_args:
        token = str(raw or "").strip()
        if token:
            normalized_args.append(token)

    if not normalized_args:
        return []

    conflicts: list[str] = []
    for key, value in connection_params.items():
        if value is None or value == "":
            continue
        prefixes = _CONNECTION_FLAG_PREFIXES_BY_KEY.get(str(key))
        if not prefixes:
            continue

        matched = False
        for token in normalized_args:
            lowered = token.lower()
            for prefix in prefixes:
                p = prefix.lower()
                if lowered == p or lowered.startswith(p + "=") or lowered.startswith(p + " "):
                    matched = True
                    break
                if p == "-p" and lowered.startswith("-p") and len(lowered) > 2 and lowered[2].isdigit():
                    matched = True
                    break
            if matched:
                break

        if matched:
            conflicts.append(str(key))

    return conflicts


def ibcmd_default_driver_schema() -> dict[str, Any]:
    return {
        "connection": {
            "remote": {
                "kind": "flag",
                "flag": "--remote",
                "expects_value": True,
                "required": False,
                "label": "Remote",
                "description": "Remote agent URL (optional).",
                "value_type": "string",
            },
            "pid": {
                "kind": "flag",
                "flag": "--pid",
                "expects_value": True,
                "required": False,
                "label": "PID",
                "description": "Attach to an existing ibcmd process (optional).",
                "value_type": "int",
            },
            "offline": {
                "config": {
                    "kind": "flag",
                    "flag": "--config",
                    "expects_value": True,
                    "required": False,
                    "label": "Config",
                    "value_type": "string",
                },
                "data": {
                    "kind": "flag",
                    "flag": "--data",
                    "expects_value": True,
                    "required": False,
                    "label": "Data",
                    "value_type": "string",
                },
                "dbms": {
                    "kind": "flag",
                    "flag": "--dbms",
                    "expects_value": True,
                    "required": False,
                    "label": "DBMS",
                    "value_type": "string",
                },
                "db_server": {
                    "kind": "flag",
                    "flag": "--db-server",
                    "expects_value": True,
                    "required": False,
                    "label": "DB server",
                    "value_type": "string",
                },
                "db_name": {
                    "kind": "flag",
                    "flag": "--db-name",
                    "expects_value": True,
                    "required": False,
                    "label": "DB name",
                    "value_type": "string",
                },
                "db_user": {
                    "kind": "flag",
                    "flag": "--db-user",
                    "expects_value": True,
                    "required": False,
                    "label": "DB user",
                    "value_type": "string",
                },
                "db_pwd": {
                    "kind": "flag",
                    "flag": "--db-pwd",
                    "expects_value": True,
                    "required": False,
                    "label": "DB password",
                    "sensitive": True,
                    "value_type": "string",
                },
            },
        },
        "timeout_seconds": {
            "kind": "int",
            "required": False,
            "default": 900,
            "min": 1,
            "max": 3600,
            "label": "Timeout (seconds)",
        },
        "stdin": {
            "kind": "text",
            "required": False,
            "label": "Stdin (optional)",
            "ui": {"widget": "textarea", "rows": 4},
        },
        "auth_database_id": {
            "kind": "database_ref",
            "required": False,
            "label": "Auth mapping infobase",
            "ui": {"source": "selected_targets", "required_when": {"command_scope": "global"}},
        },
    }


def build_ibcmd_connection_args(*, driver_schema: dict[str, Any] | None, connection: dict[str, Any]) -> list[str]:
    if not isinstance(connection, dict) or not connection:
        return []

    schema = driver_schema if isinstance(driver_schema, dict) else {}
    if not schema:
        schema = ibcmd_default_driver_schema()

    connection_schema = schema.get("connection") if isinstance(schema, dict) else None
    if not isinstance(connection_schema, dict):
        connection_schema = {}

    offline_schema = connection_schema.get("offline")
    if not isinstance(offline_schema, dict):
        offline_schema = {}

    flattened = flatten_connection_params(connection)
    if not flattened:
        return []

    def _build_flag(schema_obj: dict[str, Any] | None, *, key: str, value: Any) -> str | None:
        if value is None or value == "":
            return None

        if isinstance(schema_obj, dict):
            kind = str(schema_obj.get("kind") or "").strip()
            if kind == "positional":
                return _stringify_value(value, name=key) or None

            if kind == "flag":
                flag = schema_obj.get("flag")
                if not isinstance(flag, str) or not flag.startswith("-"):
                    flag = None
                expects_value = bool(schema_obj.get("expects_value", False))
                if flag and not expects_value:
                    return flag if _is_truthy(value) else None
                rendered = _stringify_value(value, name=key)
                if flag and rendered:
                    return f"{flag}={rendered}"

        fallback_flag = _CONNECTION_PARAM_FLAGS.get(key)
        if fallback_flag:
            rendered = _stringify_value(value, name=key)
            return f"{fallback_flag}={rendered}" if rendered else None

        return None

    args: list[str] = []
    for key in ("remote", "pid"):
        if key in flattened:
            schema_obj = connection_schema.get(key) if isinstance(connection_schema, dict) else None
            token = _build_flag(schema_obj, key=key, value=flattened.get(key))
            if token:
                args.append(token)

    for key in sorted(k for k in flattened.keys() if k not in {"remote", "pid"}):
        schema_obj = offline_schema.get(key) if isinstance(offline_schema, dict) else None
        token = _build_flag(schema_obj, key=key, value=flattened.get(key))
        if token:
            args.append(token)

    return args


def connection_params_to_additional_args(connection_params: dict[str, Any]) -> list[str]:
    if not isinstance(connection_params, dict) or not connection_params:
        return []

    args: list[str] = []
    for key in sorted(connection_params.keys()):
        flag = _CONNECTION_PARAM_FLAGS.get(key)
        if not flag:
            continue
        raw_value = connection_params.get(key)
        if raw_value is None or raw_value == "":
            continue
        value = _stringify_value(raw_value, name=key)
        if not value:
            continue
        args.append(f"{flag}={value}")

    return args


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
    pre_args: list[str] | None = None,
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

    pre = [str(x).strip() for x in (pre_args or []) if x is not None and str(x).strip()]
    argv_out = [token.strip() for token in argv] + pre + flags + [v for _, v in positionals] + extra_args
    masked = mask_argv(argv_out)
    return argv_out, masked


def build_ibcmd_cli_argv_manual(
    *,
    command: dict[str, Any],
    params: dict[str, Any],
    additional_args: list[str],
    pre_args: list[str] | None = None,
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

    pre = [str(x).strip() for x in (pre_args or []) if x is not None and str(x).strip()]
    argv_out = [token.strip() for token in argv] + pre + flags + [v for _, v in positionals] + extra_args
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
