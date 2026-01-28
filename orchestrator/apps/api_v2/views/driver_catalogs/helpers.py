"""Internal helper functions for driver catalog endpoints."""

from __future__ import annotations

import copy
import json

from apps.operations.cli_catalog import validate_cli_catalog
from apps.operations.driver_catalog_effective import (
    compute_driver_catalog_etag,
    get_effective_driver_catalog,
    load_catalog_json,
)
from apps.operations.driver_catalog_v2 import cli_catalog_v1_to_v2
from apps.operations.ibcmd_cli_builder import (
    build_ibcmd_cli_argv,
    build_ibcmd_cli_argv_manual,
    build_ibcmd_connection_args,
    detect_connection_option_conflicts,
    flatten_connection_params,
    mask_argv,
)

from .common import ArtifactVersion


def _invalidate_driver_catalog_cache(driver: str) -> None:
    from apps.api_v2.views import driver_catalogs as driver_catalogs_view

    driver_catalogs_view.invalidate_driver_catalog_cache(driver)


def _upload_overrides_catalog_version(*, driver: str, catalog: dict, created_by, metadata_extra: dict | None = None):
    from apps.api_v2.views import driver_catalogs as driver_catalogs_view

    return driver_catalogs_view.upload_overrides_catalog_version(
        driver=driver,
        catalog=catalog,
        created_by=created_by,
        metadata_extra=metadata_extra,
    )


def _record_driver_catalog_editor_error(driver: str, *, action: str, code: str) -> None:
    from apps.api_v2.views import driver_catalogs as driver_catalogs_view

    driver_catalogs_view.record_driver_catalog_editor_error(driver, action=action, code=code)


def _deep_merge_dict(target: dict, patch: dict) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge_dict(target[key], value)
        else:
            target[key] = value


def _build_empty_catalog_v2(driver: str) -> dict:
    driver = str(driver or "").strip().lower()
    return {
        "catalog_version": 2,
        "driver": driver or "unknown",
        "platform_version": "",
        "source": {"type": "not_available", "hint": "base catalog is not imported yet"},
        "generated_at": "",
        "commands_by_id": {},
    }


def _resolve_driver_base_version(
    *,
    base_versions: dict[str, ArtifactVersion | None],
) -> tuple[ArtifactVersion | None, str | None]:
    approved = base_versions.get("approved")
    latest = base_versions.get("latest")
    if approved is not None:
        return approved, "approved"
    if latest is not None:
        return latest, "latest"
    return None, None


def _extract_expected_etag(request, payload_etag: str | None) -> str | None:
    header_etag = str(request.headers.get("If-Match") or "").strip()
    if header_etag:
        return header_etag
    if payload_etag is None:
        return None
    value = str(payload_etag or "").strip()
    return value or None


def _compute_command_schemas_etag(
    *,
    driver: str,
    base_versions: dict[str, ArtifactVersion | None],
    overrides_version: ArtifactVersion | None,
) -> str:
    approved = base_versions.get("approved")
    latest = base_versions.get("latest")
    approved_id = str(approved.id) if approved else ""
    latest_id = str(latest.id) if latest else ""
    base_part = f"approved={approved_id}|latest={latest_id}"
    return compute_driver_catalog_etag(
        driver=driver,
        base_version_id=base_part if (approved_id or latest_id) else None,
        overrides_version_id=str(overrides_version.id) if overrides_version else None,
        roles_hash=None,
    )


def _issue(
    severity: str,
    code: str,
    message: str,
    *,
    command_id: str | None = None,
    path: str | None = None,
) -> dict:
    payload: dict = {"severity": severity, "code": code, "message": message}
    if command_id is not None:
        payload["command_id"] = command_id
    if path is not None:
        payload["path"] = path
    return payload


def _get_commands_by_id(catalog: dict) -> dict:
    commands_by_id = catalog.get("commands_by_id")
    if isinstance(commands_by_id, dict):
        return commands_by_id
    return {}


def _is_truthy(value) -> bool:
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


def _stringify_value(value, *, name: str) -> str:
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
        _ = name
        return ""


def _build_command_argv(
    *,
    command: dict,
    params: dict,
    additional_args: list[str],
    strict: bool,
) -> tuple[list[str], list[str]]:
    argv = command.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x.strip() for x in argv):
        raise ValueError("command.argv must be a non-empty string array")

    params_by_name = command.get("params_by_name") or {}
    if params_by_name and not isinstance(params_by_name, dict):
        raise ValueError("command.params_by_name must be an object")

    if not isinstance(params, dict):
        raise ValueError("params must be an object")

    normalized_params = dict(params)

    if params_by_name and strict:
        unknown = [key for key in normalized_params.keys() if key not in params_by_name]
        if unknown:
            raise ValueError(f"unknown params: {', '.join(sorted(str(k) for k in unknown))}")

    if not params_by_name and strict and normalized_params:
        raise ValueError("params are not supported for this command")

    flags: list[str] = []
    positionals: list[tuple[int, str]] = []

    for name, schema in (params_by_name or {}).items():
        if not isinstance(schema, dict):
            continue
        if name not in normalized_params:
            if strict and schema.get("required") is True:
                raise ValueError(f"missing required param: {name}")
            continue

        raw_value = normalized_params.get(name)
        if raw_value is None or raw_value == "":
            if strict and schema.get("required") is True:
                raise ValueError(f"missing required param: {name}")
            continue

        kind = str(schema.get("kind") or "").strip()
        if kind == "positional":
            pos = schema.get("position")
            if strict:
                if not isinstance(pos, int) or pos < 1:
                    raise ValueError(f"{name}.position must be >= 1")
            if isinstance(pos, int) and pos >= 1:
                positionals.append((pos, _stringify_value(raw_value, name=name)))
            continue

        if kind != "flag":
            if strict:
                raise ValueError(f"{name}.kind must be flag|positional")
            continue

        flag = schema.get("flag")
        if strict:
            if not isinstance(flag, str) or not flag.startswith("-"):
                raise ValueError(f"{name}.flag must be a flag string")
        if not isinstance(flag, str) or not flag:
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
        if strict and enum_values is not None:
            if not isinstance(enum_values, list) or not all(isinstance(x, str) and x for x in enum_values):
                raise ValueError(f"{name}.enum must be a string array")
            for value in values:
                if value not in enum_values:
                    raise ValueError(f"invalid {name}: {value!r} (allowed: {', '.join(enum_values)})")

        for value in values:
            flags.append(f"{flag}={value}")

    flags.sort()
    positionals.sort(key=lambda item: item[0])

    argv_out = [token.strip() for token in argv] + flags + [v for _, v in positionals]
    argv_out.extend([str(x).strip() for x in (additional_args or []) if x is not None and str(x).strip()])

    masked = mask_argv(argv_out)
    return argv_out, masked


def _collect_command_param_issues(command_id: str, command: dict) -> list[dict]:
    params_by_name = command.get("params_by_name") or {}
    if params_by_name and not isinstance(params_by_name, dict):
        return [_issue("error", "PARAMS_INVALID", "params_by_name must be an object", command_id=command_id)]

    return _collect_params_by_name_issues(
        params_by_name=params_by_name,
        command_id=command_id,
        path_prefix=f"commands_by_id.{command_id}.params_by_name",
    )

def _collect_params_by_name_issues(
    *,
    params_by_name: dict,
    path_prefix: str,
    command_id: str | None = None,
) -> list[dict]:
    issues: list[dict] = []

    used_flags: dict[str, str] = {}
    used_positions: dict[int, str] = {}

    for name, schema in (params_by_name or {}).items():
        if not isinstance(name, str) or not name:
            issues.append(_issue("error", "PARAM_NAME_INVALID", "param name must be non-empty string", command_id=command_id))
            continue
        if not isinstance(schema, dict):
            issues.append(_issue("error", "PARAM_SCHEMA_INVALID", f"{name} must be an object", command_id=command_id))
            continue

        kind = schema.get("kind")
        if kind not in {"flag", "positional"}:
            issues.append(_issue(
                "error",
                "PARAM_KIND_INVALID",
                f"{name}.kind must be flag|positional",
                command_id=command_id,
                path=f"{path_prefix}.{name}.kind",
            ))
            continue

        if kind == "flag":
            flag = schema.get("flag")
            if not isinstance(flag, str) or not flag.startswith("-"):
                issues.append(_issue(
                    "error",
                    "FLAG_INVALID",
                    f"{name}.flag must be a flag string",
                    command_id=command_id,
                    path=f"{path_prefix}.{name}.flag",
                ))
                continue

            prev = used_flags.get(flag)
            if prev is not None and prev != name:
                issues.append(_issue(
                    "error",
                    "DUPLICATE_FLAG",
                    f"duplicate flag {flag}: {prev} and {name}",
                    command_id=command_id,
                    path=f"{path_prefix}.{name}.flag",
                ))
            else:
                used_flags[flag] = name

        if kind == "positional":
            pos = schema.get("position")
            if not isinstance(pos, int) or pos < 1:
                issues.append(_issue(
                    "error",
                    "POSITION_INVALID",
                    f"{name}.position must be >= 1",
                    command_id=command_id,
                    path=f"{path_prefix}.{name}.position",
                ))
                continue

            prev = used_positions.get(pos)
            if prev is not None and prev != name:
                issues.append(_issue(
                    "error",
                    "DUPLICATE_POSITION",
                    f"duplicate position {pos}: {prev} and {name}",
                    command_id=command_id,
                    path=f"{path_prefix}.{name}.position",
                ))
            else:
                used_positions[pos] = name

    return issues


def _collect_ibcmd_driver_schema_issues(catalog: dict) -> list[dict]:
    issues: list[dict] = []
    if not isinstance(catalog, dict):
        return issues

    driver_schema = catalog.get("driver_schema")
    if driver_schema is None:
        return issues
    if not isinstance(driver_schema, dict):
        return [_issue("error", "DRIVER_SCHEMA_INVALID", "driver_schema must be an object", path="driver_schema")]

    connection = driver_schema.get("connection")
    if connection is None:
        return issues
    if not isinstance(connection, dict):
        return [_issue("error", "DRIVER_SCHEMA_INVALID", "driver_schema.connection must be an object", path="driver_schema.connection")]

    connection_params: dict[str, dict] = {}
    for key in ("remote", "pid"):
        schema = connection.get(key)
        if schema is None:
            continue
        if not isinstance(schema, dict):
            issues.append(_issue(
                "error",
                "PARAM_SCHEMA_INVALID",
                f"{key} must be an object",
                path=f"driver_schema.connection.{key}",
            ))
            continue
        connection_params[key] = schema

    if connection_params:
        issues.extend(_collect_params_by_name_issues(
            params_by_name=connection_params,
            path_prefix="driver_schema.connection",
        ))

    offline = connection.get("offline")
    if offline is not None:
        if not isinstance(offline, dict):
            issues.append(_issue(
                "error",
                "DRIVER_SCHEMA_INVALID",
                "driver_schema.connection.offline must be an object",
                path="driver_schema.connection.offline",
            ))
        else:
            issues.extend(_collect_params_by_name_issues(
                params_by_name=offline,
                path_prefix="driver_schema.connection.offline",
            ))

    used_flags: dict[str, str] = {}
    for name, schema in connection_params.items():
        if isinstance(schema, dict) and schema.get("kind") == "flag":
            flag = schema.get("flag")
            if isinstance(flag, str) and flag.startswith("-"):
                used_flags[flag] = f"driver_schema.connection.{name}"

    if isinstance(offline, dict):
        for name, schema in offline.items():
            if not isinstance(schema, dict) or schema.get("kind") != "flag":
                continue
            flag = schema.get("flag")
            if not isinstance(flag, str) or not flag.startswith("-"):
                continue
            prev = used_flags.get(flag)
            if prev is not None and prev != f"driver_schema.connection.offline.{name}":
                issues.append(_issue(
                    "error",
                    "DUPLICATE_FLAG",
                    f"duplicate flag {flag}: {prev} and driver_schema.connection.offline.{name}",
                    path=f"driver_schema.connection.offline.{name}.flag",
                ))
            else:
                used_flags[flag] = f"driver_schema.connection.offline.{name}"

    return issues


def _validate_cli_catalog_v2(catalog: dict) -> list[dict]:
    issues: list[dict] = []

    if not isinstance(catalog, dict):
        return [_issue("error", "CATALOG_INVALID", "catalog must be an object")]

    if catalog.get("catalog_version") != 2:
        issues.append(_issue("error", "CATALOG_VERSION_INVALID", "catalog_version must be 2"))

    driver = str(catalog.get("driver") or "").strip()
    if driver != "cli":
        issues.append(_issue("error", "DRIVER_INVALID", "driver must be cli"))

    commands_by_id = catalog.get("commands_by_id")
    if not isinstance(commands_by_id, dict):
        issues.append(_issue("error", "COMMANDS_INVALID", "commands_by_id must be an object"))
        return issues

    for command_id, command in commands_by_id.items():
        if not isinstance(command_id, str) or not command_id.strip():
            issues.append(_issue("error", "COMMAND_ID_INVALID", "command id must be a non-empty string"))
            continue
        command_id = command_id.strip()
        if not isinstance(command, dict):
            issues.append(_issue("error", "COMMAND_INVALID", "command must be an object", command_id=command_id))
            continue

        argv = command.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x.strip() for x in argv):
            issues.append(_issue(
                "error",
                "ARGV_INVALID",
                "argv must be a non-empty string array",
                command_id=command_id,
                path=f"commands_by_id.{command_id}.argv",
            ))
        else:
            expected_token = f"/{command_id}"
            if str(argv[0]).strip() != expected_token:
                issues.append(_issue(
                    "error",
                    "COMMAND_ID_MISMATCH",
                    f"id mismatch: expected {expected_token}",
                    command_id=command_id,
                    path=f"commands_by_id.{command_id}.argv.0",
                ))

        scope = command.get("scope")
        if scope not in {"per_database", "global"}:
            issues.append(_issue(
                "error",
                "SCOPE_INVALID",
                "scope must be per_database|global",
                command_id=command_id,
                path=f"commands_by_id.{command_id}.scope",
            ))

        risk = command.get("risk_level")
        if risk not in {"safe", "dangerous"}:
            issues.append(_issue(
                "error",
                "RISK_INVALID",
                "risk_level must be safe|dangerous",
                command_id=command_id,
                path=f"commands_by_id.{command_id}.risk_level",
            ))

        disabled = command.get("disabled")
        if disabled is not None and not isinstance(disabled, bool):
            issues.append(_issue(
                "error",
                "DISABLED_INVALID",
                "disabled must be boolean",
                command_id=command_id,
                path=f"commands_by_id.{command_id}.disabled",
            ))

        params_by_name = command.get("params_by_name") or {}
        if isinstance(params_by_name, dict):
            for name, schema in params_by_name.items():
                if not isinstance(name, str) or not name:
                    continue
                if not isinstance(schema, dict):
                    continue

                required = schema.get("required")
                if not isinstance(required, bool):
                    issues.append(_issue(
                        "error",
                        "PARAM_REQUIRED_INVALID",
                        f"{name}.required must be boolean",
                        command_id=command_id,
                        path=f"commands_by_id.{command_id}.params_by_name.{name}.required",
                    ))

                expects_value = schema.get("expects_value")
                if not isinstance(expects_value, bool):
                    issues.append(_issue(
                        "error",
                        "PARAM_EXPECTS_VALUE_INVALID",
                        f"{name}.expects_value must be boolean",
                        command_id=command_id,
                        path=f"commands_by_id.{command_id}.params_by_name.{name}.expects_value",
                    ))

                enum_values = schema.get("enum")
                if enum_values is not None and (
                    not isinstance(enum_values, list)
                    or not all(isinstance(x, str) and x for x in enum_values)
                ):
                    issues.append(_issue(
                        "error",
                        "PARAM_ENUM_INVALID",
                        f"{name}.enum must be a string array",
                        command_id=command_id,
                        path=f"commands_by_id.{command_id}.params_by_name.{name}.enum",
                    ))

        issues.extend(_collect_command_param_issues(command_id, command))

    return issues


def _diff_values(
    *,
    base,
    effective,
    path: str,
    out: list[dict],
) -> None:
    if isinstance(base, dict) and isinstance(effective, dict):
        keys = sorted({k for k in base.keys() if isinstance(k, str)} | {k for k in effective.keys() if isinstance(k, str)})
        for key in keys:
            next_path = f"{path}.{key}" if path else key
            if key not in base:
                out.append({
                    "path": next_path,
                    "base_present": False,
                    "base": None,
                    "effective_present": True,
                    "effective": effective.get(key),
                })
                continue
            if key not in effective:
                out.append({
                    "path": next_path,
                    "base_present": True,
                    "base": base.get(key),
                    "effective_present": False,
                    "effective": None,
                })
                continue

            _diff_values(base=base.get(key), effective=effective.get(key), path=next_path, out=out)
        return

    if base != effective:
        out.append({
            "path": path,
            "base_present": True,
            "base": base,
            "effective_present": True,
            "effective": effective,
        })


def _validate_overrides_catalog_v2(driver: str, catalog: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(catalog, dict):
        return ["catalog must be an object"]
    if catalog.get("catalog_version") != 2:
        errors.append("catalog_version must be 2")
    if str(catalog.get("driver") or "").strip().lower() != driver:
        errors.append("driver mismatch")
    overrides = catalog.get("overrides")
    if not isinstance(overrides, dict):
        errors.append("overrides must be an object")
    return errors


