"""
Driver catalog management endpoints (staff-only).

Supports:
- list/get/update driver catalogs (file-backed)
- import ITS JSON to CLI catalog (and publish v2 base artifact)
- import ITS JSON to IBCMD catalog v2 base artifact
"""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path

from django.conf import settings
from rest_framework import status as http_status
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.artifacts.models import ArtifactAlias, ArtifactVersion
from apps.core import permission_codes as perms
from apps.operations.cli_catalog import (
    load_cli_command_catalog,
    save_cli_command_catalog,
    build_cli_catalog_from_its,
    validate_cli_catalog,
)
from apps.operations.ibcmd_catalog_v2 import build_base_catalog_from_its as build_ibcmd_catalog_v2_from_its
from apps.operations.ibcmd_catalog_v2 import validate_catalog_v2 as validate_ibcmd_catalog_v2
from apps.operations.driver_catalog_artifacts import (
    get_or_create_catalog_artifacts,
    promote_base_alias,
    upload_base_catalog_version,
    upload_overrides_catalog_version,
)
from apps.operations.driver_catalog_v2 import cli_catalog_v1_to_v2
from apps.operations.driver_catalog_effective import (
    compute_driver_catalog_etag,
    get_effective_driver_catalog,
    invalidate_driver_catalog_cache,
    load_catalog_json,
)
from apps.operations.ibcmd_cli_builder import mask_argv
from apps.operations.models import AdminActionAuditLog
from apps.operations.services.admin_action_audit import log_admin_action
from apps.operations.prometheus_metrics import (
    record_driver_catalog_editor_conflict,
    record_driver_catalog_editor_validation_failed,
    record_driver_catalog_editor_error,
)
from apps.api_v2.serializers.common import ErrorResponseSerializer
from apps.artifacts.storage import ArtifactStorageError

logger = logging.getLogger(__name__)


DRIVER_CATALOGS = {
    "cli": {"path": "config/cli_commands.json", "kind": "cli"},
    "ras": {"path": "config/driver_catalogs/ras.json", "kind": "generic"},
    "odata": {"path": "config/driver_catalogs/odata.json", "kind": "generic"},
    "ibcmd": {"path": "config/driver_catalogs/ibcmd.json", "kind": "generic"},
}


def _permission_denied(message: str):
    return Response(
        {"success": False, "error": {"code": "PERMISSION_DENIED", "message": message}},
        status=http_status.HTTP_403_FORBIDDEN,
    )


def _ensure_manage_driver_catalogs(request, *, action: str | None = None):
    user = request.user
    if getattr(user, "is_superuser", False):
        return None

    all_permissions = user.get_all_permissions()
    if perms.PERM_OPERATIONS_MANAGE_DRIVER_CATALOGS in all_permissions:
        return None

    record_driver_catalog_editor_error("unknown", action=action or "permission_denied", code="PERMISSION_DENIED")
    return _permission_denied("You do not have permission to manage driver catalogs.")


def _catalog_path(rel_path: str) -> Path:
    return Path(settings.BASE_DIR).parent / rel_path


def _load_catalog(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        logger.info("Driver catalog not found: %s", path)
    except json.JSONDecodeError as exc:
        logger.warning("Driver catalog invalid: %s", exc)
    except OSError as exc:
        logger.warning("Failed to read driver catalog: %s", exc)
    return {"version": "unknown", "source": str(path), "commands": []}


def _save_catalog(path: Path, catalog: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")


class DriverCatalogListItemSerializer(serializers.Serializer):
    driver = serializers.CharField()
    version = serializers.CharField()
    command_count = serializers.IntegerField()
    source = serializers.CharField(required=False)


class DriverCatalogListResponseSerializer(serializers.Serializer):
    items = DriverCatalogListItemSerializer(many=True)
    count = serializers.IntegerField()


class DriverCatalogGetResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    catalog = serializers.DictField()


class DriverCatalogUpdateRequestSerializer(serializers.Serializer):
    driver = serializers.CharField()
    catalog = serializers.DictField()
    reason = serializers.CharField()


class DriverCatalogImportRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=["cli", "ibcmd"], default="cli")
    its_payload = serializers.DictField()
    save = serializers.BooleanField(default=True)


class DriverCatalogImportResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    catalog = serializers.DictField()


class DriverCatalogOverridesGetResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    overrides_version = serializers.CharField()
    catalog = serializers.DictField()


class DriverCatalogOverridesUpdateRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=["cli", "ibcmd"])
    catalog = serializers.DictField()
    reason = serializers.CharField()


class DriverCatalogOverridesUpdateResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    overrides_version = serializers.CharField()
    catalog = serializers.DictField()


class DriverCatalogPromoteRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=["cli", "ibcmd"])
    version = serializers.CharField()
    alias = serializers.CharField(required=False, default="approved")
    reason = serializers.CharField()


class DriverCatalogPromoteResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    alias = serializers.CharField()
    version = serializers.CharField()


class CommandSchemasEditorViewResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    etag = serializers.CharField()
    base = serializers.DictField()
    overrides = serializers.DictField()
    catalogs = serializers.DictField()


class CommandSchemasVersionsListResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    artifact = serializers.CharField()
    versions = serializers.ListField(child=serializers.DictField())
    count = serializers.IntegerField()


class CommandSchemasOverridesUpdateRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=["cli", "ibcmd"])
    catalog = serializers.DictField()
    reason = serializers.CharField()
    expected_etag = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class CommandSchemasOverridesUpdateResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    overrides_version = serializers.CharField()
    etag = serializers.CharField()


class CommandSchemasOverridesRollbackRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=["cli", "ibcmd"])
    version = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    version_id = serializers.UUIDField(required=False, allow_null=True)
    reason = serializers.CharField()
    expected_etag = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        if attrs.get("version_id") is None and not str(attrs.get("version") or "").strip():
            raise serializers.ValidationError("version or version_id is required")
        return attrs


class CommandSchemasOverridesRollbackResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    overrides_version = serializers.CharField()
    etag = serializers.CharField()


class CommandSchemasImportRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=["cli", "ibcmd"], default="cli")
    its_payload = serializers.DictField()
    save = serializers.BooleanField(default=True)
    reason = serializers.CharField()


class CommandSchemasImportResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    catalog = serializers.DictField()


class CommandSchemasPromoteRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=["cli", "ibcmd"])
    version = serializers.CharField()
    alias = serializers.CharField(required=False, default="approved")
    reason = serializers.CharField()


class CommandSchemasPromoteResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    alias = serializers.CharField()
    version = serializers.CharField()


class CommandSchemasIssueSerializer(serializers.Serializer):
    severity = serializers.ChoiceField(choices=["error", "warning"])
    code = serializers.CharField()
    message = serializers.CharField()
    command_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    path = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class CommandSchemasValidateRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=["cli", "ibcmd"])
    catalog = serializers.DictField(required=False, allow_null=True)


class CommandSchemasValidateResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    ok = serializers.BooleanField()
    base_version = serializers.CharField(allow_null=True)
    base_version_id = serializers.CharField(allow_null=True)
    overrides_version = serializers.CharField(allow_null=True)
    overrides_version_id = serializers.CharField(allow_null=True)
    issues = CommandSchemasIssueSerializer(many=True)
    errors_count = serializers.IntegerField()
    warnings_count = serializers.IntegerField()


class CommandSchemasPreviewRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=["cli", "ibcmd"])
    command_id = serializers.CharField()
    mode = serializers.ChoiceField(choices=["guided", "manual"], default="guided")
    params = serializers.DictField(required=False, default=dict)
    additional_args = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    catalog = serializers.DictField(required=False, allow_null=True)


class CommandSchemasPreviewResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    command_id = serializers.CharField()
    argv = serializers.ListField(child=serializers.CharField())
    argv_masked = serializers.ListField(child=serializers.CharField())
    risk_level = serializers.CharField(required=False, allow_null=True)
    scope = serializers.CharField(required=False, allow_null=True)
    disabled = serializers.BooleanField(required=False, allow_null=True)


class CommandSchemasDiffRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=["cli", "ibcmd"])
    command_id = serializers.CharField()
    catalog = serializers.DictField(required=False, allow_null=True)


class CommandSchemasDiffItemSerializer(serializers.Serializer):
    path = serializers.CharField()
    base_present = serializers.BooleanField()
    base = serializers.JSONField(required=False, allow_null=True)
    effective_present = serializers.BooleanField()
    effective = serializers.JSONField(required=False, allow_null=True)


class CommandSchemasDiffResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    command_id = serializers.CharField()
    has_overrides = serializers.BooleanField()
    changes = CommandSchemasDiffItemSerializer(many=True)
    count = serializers.IntegerField()


class CommandSchemasAuditLogItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    action = serializers.CharField()
    outcome = serializers.CharField()
    actor_username = serializers.CharField()
    target_type = serializers.CharField()
    target_id = serializers.CharField()
    metadata = serializers.DictField()
    error_message = serializers.CharField()


class CommandSchemasAuditListResponseSerializer(serializers.Serializer):
    items = CommandSchemasAuditLogItemSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


def _resolve_catalog(driver: str) -> dict:
    if driver == "cli":
        return load_cli_command_catalog()
    cfg = DRIVER_CATALOGS.get(driver)
    if not cfg:
        return {}
    return _load_catalog(_catalog_path(cfg["path"]))


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
    issues: list[dict] = []

    params_by_name = command.get("params_by_name") or {}
    if params_by_name and not isinstance(params_by_name, dict):
        issues.append(_issue("error", "PARAMS_INVALID", "params_by_name must be an object", command_id=command_id))
        return issues

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
                path=f"commands_by_id.{command_id}.params_by_name.{name}.kind",
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
                    path=f"commands_by_id.{command_id}.params_by_name.{name}.flag",
                ))
                continue

            prev = used_flags.get(flag)
            if prev is not None and prev != name:
                issues.append(_issue(
                    "error",
                    "DUPLICATE_FLAG",
                    f"duplicate flag {flag}: {prev} and {name}",
                    command_id=command_id,
                    path=f"commands_by_id.{command_id}.params_by_name.{name}.flag",
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
                    path=f"commands_by_id.{command_id}.params_by_name.{name}.position",
                ))
                continue

            prev = used_positions.get(pos)
            if prev is not None and prev != name:
                issues.append(_issue(
                    "error",
                    "DUPLICATE_POSITION",
                    f"duplicate position {pos}: {prev} and {name}",
                    command_id=command_id,
                    path=f"commands_by_id.{command_id}.params_by_name.{name}.position",
                ))
            else:
                used_positions[pos] = name

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


@extend_schema(
    tags=["v2"],
    summary="List driver catalogs",
    description="List available driver catalogs and metadata (staff-only).",
    responses={
        200: DriverCatalogListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAdminUser])
def list_driver_catalogs(request):
    denied = _ensure_manage_driver_catalogs(request, action="driver_catalog.list")
    if denied:
        return denied

    items = []
    for driver, cfg in DRIVER_CATALOGS.items():
        catalog = _resolve_catalog(driver)
        commands = catalog.get("commands")
        items.append({
            "driver": driver,
            "version": str(catalog.get("version") or "unknown"),
            "command_count": len(commands) if isinstance(commands, list) else 0,
            "source": str(catalog.get("source") or cfg.get("path")),
        })
    return Response({"items": items, "count": len(items)})


@extend_schema(
    tags=["v2"],
    summary="Get driver catalog",
    description="Return driver catalog contents (staff-only).",
    parameters=[
        OpenApiParameter(
            name="driver",
            type=str,
            required=True,
            description="Driver name (cli/ras/odata/ibcmd)",
        )
    ],
    responses={
        200: DriverCatalogGetResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAdminUser])
def get_driver_catalog(request):
    denied = _ensure_manage_driver_catalogs(request, action="driver_catalog.get")
    if denied:
        return denied

    driver = str(request.query_params.get("driver") or "").strip()
    if not driver:
        record_driver_catalog_editor_error("unknown", action="driver_catalog.get", code="MISSING_DRIVER")
        return Response({
            "success": False,
            "error": {"code": "MISSING_DRIVER", "message": "driver is required"},
        }, status=400)
    if driver not in DRIVER_CATALOGS:
        record_driver_catalog_editor_error("unknown", action="driver_catalog.get", code="UNKNOWN_DRIVER")
        return Response({
            "success": False,
            "error": {"code": "UNKNOWN_DRIVER", "message": f"Unknown driver: {driver}"},
        }, status=400)
    catalog = _resolve_catalog(driver)
    return Response({"driver": driver, "catalog": catalog})


@extend_schema(
    tags=["v2"],
    summary="Update driver catalog",
    description="Update driver catalog file (staff-only). Requires reason.",
    request=DriverCatalogUpdateRequestSerializer,
    responses={
        200: DriverCatalogGetResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def update_driver_catalog(request):
    denied = _ensure_manage_driver_catalogs(request, action="driver_catalog.update")
    if denied:
        return denied

    serializer = DriverCatalogUpdateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        record_driver_catalog_editor_error("unknown", action="driver_catalog.update", code="INVALID_REQUEST")
        log_admin_action(
            request,
            action="driver_catalog.update",
            outcome="error",
            target_type="driver_catalog",
            metadata={"error": "INVALID_REQUEST"},
            error_message="INVALID_REQUEST",
        )
        return Response({
            "success": False,
            "error": {"code": "INVALID_REQUEST", "message": "Invalid request", "details": serializer.errors},
        }, status=400)
    driver = serializer.validated_data["driver"]
    catalog = serializer.validated_data["catalog"]
    reason = serializer.validated_data["reason"]
    if driver not in DRIVER_CATALOGS:
        record_driver_catalog_editor_error("unknown", action="driver_catalog.update", code="UNKNOWN_DRIVER")
        log_admin_action(
            request,
            action="driver_catalog.update",
            outcome="error",
            target_type="driver_catalog",
            target_id=driver,
            metadata={"error": "UNKNOWN_DRIVER", "driver": driver, "reason": reason},
            error_message="UNKNOWN_DRIVER",
        )
        return Response({
            "success": False,
            "error": {"code": "UNKNOWN_DRIVER", "message": f"Unknown driver: {driver}"},
        }, status=400)
    if driver == "cli":
        errors = validate_cli_catalog(catalog)
        if errors:
            record_driver_catalog_editor_validation_failed(driver, stage="driver_catalog.update", kind="invalid_parsed")
            record_driver_catalog_editor_error(driver, action="driver_catalog.update", code="INVALID_CATALOG")
            log_admin_action(
                request,
                action="driver_catalog.update",
                outcome="error",
                target_type="driver_catalog",
                target_id=driver,
                metadata={"error": "INVALID_CATALOG", "driver": driver, "reason": reason},
                error_message="INVALID_CATALOG",
            )
            return Response({
                "success": False,
                "error": {"code": "INVALID_CATALOG", "message": "Invalid CLI catalog", "details": errors},
            }, status=400)
        try:
            save_cli_command_catalog(catalog)
            upload_base_catalog_version(
                driver="cli",
                catalog=cli_catalog_v1_to_v2(catalog),
                created_by=request.user,
                metadata_extra={"reason": reason},
            )
            invalidate_driver_catalog_cache("cli")
        except Exception as exc:
            record_driver_catalog_editor_error(driver, action="driver_catalog.update", code="UPDATE_FAILED")
            log_admin_action(
                request,
                action="driver_catalog.update",
                outcome="error",
                target_type="driver_catalog",
                target_id=driver,
                metadata={"error": "UPDATE_FAILED", "driver": driver, "reason": reason},
                error_message="UPDATE_FAILED",
            )
            return Response(
                {"success": False, "error": {"code": "UPDATE_FAILED", "message": str(exc)}},
                status=500,
            )
    else:
        try:
            _save_catalog(_catalog_path(DRIVER_CATALOGS[driver]["path"]), catalog)
        except Exception as exc:
            record_driver_catalog_editor_error(driver, action="driver_catalog.update", code="UPDATE_FAILED")
            log_admin_action(
                request,
                action="driver_catalog.update",
                outcome="error",
                target_type="driver_catalog",
                target_id=driver,
                metadata={"error": "UPDATE_FAILED", "driver": driver, "reason": reason},
                error_message="UPDATE_FAILED",
            )
            return Response(
                {"success": False, "error": {"code": "UPDATE_FAILED", "message": str(exc)}},
                status=500,
            )
    log_admin_action(
        request,
        action="driver_catalog.update",
        outcome="success",
        target_type="driver_catalog",
        target_id=driver,
        metadata={"driver": driver, "reason": reason},
    )
    return Response({"driver": driver, "catalog": catalog})


@extend_schema(
    tags=["v2"],
    summary="Import ITS catalog",
    description=(
        "Parse ITS JSON into driver command catalog and optionally save (staff-only).\n\n"
        "driver=cli: updates legacy file-backed catalog (v1) and uploads v2 base catalog artifact.\n"
        "driver=ibcmd: generates schema-driven catalog v2 and uploads it as a versioned artifact."
    ),
    request=DriverCatalogImportRequestSerializer,
    responses={
        200: DriverCatalogImportResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def import_its_driver_catalog(request):
    denied = _ensure_manage_driver_catalogs(request, action="import_its")
    if denied:
        return denied

    serializer = DriverCatalogImportRequestSerializer(data=request.data)
    if not serializer.is_valid():
        record_driver_catalog_editor_error("unknown", action="import_its", code="INVALID_REQUEST")
        log_admin_action(
            request,
            action="driver_catalog.import_its",
            outcome="error",
            target_type="driver_catalog",
            metadata={"error": "INVALID_REQUEST"},
            error_message="INVALID_REQUEST",
        )
        return Response({
            "success": False,
            "error": {"code": "INVALID_REQUEST", "message": "Invalid request", "details": serializer.errors},
        }, status=400)
    driver = serializer.validated_data["driver"]
    if driver != "cli":
        if driver != "ibcmd":
            record_driver_catalog_editor_error("unknown", action="import_its", code="UNSUPPORTED_DRIVER")
            log_admin_action(
                request,
                action="driver_catalog.import_its",
                outcome="error",
                target_type="driver_catalog",
                metadata={"error": "UNSUPPORTED_DRIVER", "driver": driver},
                error_message="UNSUPPORTED_DRIVER",
            )
            return Response({
                "success": False,
                "error": {"code": "UNSUPPORTED_DRIVER", "message": f"Unsupported driver: {driver}"},
            }, status=400)
    its_payload = serializer.validated_data["its_payload"]

    if driver == "cli":
        catalog = build_cli_catalog_from_its(its_payload)
        errors = validate_cli_catalog(catalog)
        if errors:
            record_driver_catalog_editor_validation_failed(driver, stage="import_its", kind="invalid_parsed")
            record_driver_catalog_editor_error(driver, action="import_its", code="INVALID_CATALOG")
            log_admin_action(
                request,
                action="driver_catalog.import_its",
                outcome="error",
                target_type="driver_catalog",
                target_id=driver,
                metadata={"error": "INVALID_CATALOG", "driver": driver},
                error_message="INVALID_CATALOG",
            )
            return Response({
                "success": False,
                "error": {"code": "INVALID_CATALOG", "message": "Parsed CLI catalog is invalid", "details": errors},
            }, status=400)
        if serializer.validated_data.get("save", True):
            try:
                save_cli_command_catalog(catalog)
                upload_base_catalog_version(
                    driver="cli",
                    catalog=cli_catalog_v1_to_v2(catalog),
                    created_by=request.user,
                )
                invalidate_driver_catalog_cache("cli")
            except Exception as exc:
                record_driver_catalog_editor_error(driver, action="import_its", code="IMPORT_FAILED")
                log_admin_action(
                    request,
                    action="driver_catalog.import_its",
                    outcome="error",
                    target_type="driver_catalog",
                    target_id=driver,
                    metadata={"error": "IMPORT_FAILED", "driver": driver},
                    error_message="IMPORT_FAILED",
                )
                return Response(
                    {"success": False, "error": {"code": "IMPORT_FAILED", "message": str(exc)}},
                    status=500,
                )
    else:
        catalog = build_ibcmd_catalog_v2_from_its(its_payload)
        errors = validate_ibcmd_catalog_v2(catalog)
        if errors:
            record_driver_catalog_editor_validation_failed(driver, stage="import_its", kind="invalid_parsed")
            record_driver_catalog_editor_error(driver, action="import_its", code="INVALID_CATALOG")
            log_admin_action(
                request,
                action="driver_catalog.import_its",
                outcome="error",
                target_type="driver_catalog",
                target_id=driver,
                metadata={"error": "INVALID_CATALOG", "driver": driver},
                error_message="INVALID_CATALOG",
            )
            return Response({
                "success": False,
                "error": {"code": "INVALID_CATALOG", "message": "Parsed IBCMD catalog is invalid", "details": errors},
            }, status=400)
        if serializer.validated_data.get("save", True):
            try:
                upload_base_catalog_version(
                    driver="ibcmd",
                    catalog=catalog,
                    created_by=request.user,
                )
                invalidate_driver_catalog_cache("ibcmd")
            except Exception as exc:
                record_driver_catalog_editor_error(driver, action="import_its", code="IMPORT_FAILED")
                log_admin_action(
                    request,
                    action="driver_catalog.import_its",
                    outcome="error",
                    target_type="driver_catalog",
                    target_id=driver,
                    metadata={"error": "IMPORT_FAILED", "driver": driver},
                    error_message="IMPORT_FAILED",
                )
                return Response(
                    {"success": False, "error": {"code": "IMPORT_FAILED", "message": str(exc)}},
                    status=500,
                )

    log_admin_action(
        request,
        action="driver_catalog.import_its",
        outcome="success",
        target_type="driver_catalog",
        target_id=driver,
        metadata={"driver": driver, "version": catalog.get("version") or catalog.get("platform_version")},
    )
    return Response({"driver": driver, "catalog": catalog})


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


@extend_schema(
    tags=["v2"],
    summary="Get driver catalog overrides (v2)",
    description="Return active overrides catalog for the requested driver (staff-only).",
    parameters=[
        OpenApiParameter(
            name="driver",
            type=str,
            required=True,
            description="Driver name (cli/ibcmd)",
        )
    ],
    responses={
        200: DriverCatalogOverridesGetResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAdminUser])
def get_driver_catalog_overrides(request):
    denied = _ensure_manage_driver_catalogs(request, action="overrides.get")
    if denied:
        return denied

    driver = str(request.query_params.get("driver") or "").strip().lower()
    if not driver:
        record_driver_catalog_editor_error("unknown", action="overrides.get", code="MISSING_DRIVER")
        return Response({
            "success": False,
            "error": {"code": "MISSING_DRIVER", "message": "driver is required"},
        }, status=400)
    if driver not in {"cli", "ibcmd"}:
        record_driver_catalog_editor_error("unknown", action="overrides.get", code="UNKNOWN_DRIVER")
        return Response({
            "success": False,
            "error": {"code": "UNKNOWN_DRIVER", "message": f"Unknown driver: {driver}"},
        }, status=400)

    artifacts = get_or_create_catalog_artifacts(driver, created_by=request.user)
    alias_obj = artifacts.overrides.aliases.select_related("version").get(alias="active")
    try:
        catalog = load_catalog_json(alias_obj.version)
    except ArtifactStorageError as exc:
        record_driver_catalog_editor_error(driver, action="overrides.get", code="STORAGE_ERROR")
        return Response(
            {"success": False, "error": {"code": "STORAGE_ERROR", "message": str(exc)}},
            status=500,
        )
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        record_driver_catalog_editor_error(driver, action="overrides.get", code="CATALOG_INVALID")
        return Response(
            {"success": False, "error": {"code": "CATALOG_INVALID", "message": str(exc)}},
            status=500,
        )
    return Response({
        "driver": driver,
        "overrides_version": str(alias_obj.version.version),
        "catalog": catalog,
    })


@extend_schema(
    tags=["v2"],
    summary="Update driver catalog overrides (v2)",
    description="Upload new overrides catalog version and move alias active (staff-only). Requires reason.",
    request=DriverCatalogOverridesUpdateRequestSerializer,
    responses={
        200: DriverCatalogOverridesUpdateResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def update_driver_catalog_overrides(request):
    denied = _ensure_manage_driver_catalogs(request, action="overrides.update")
    if denied:
        return denied

    serializer = DriverCatalogOverridesUpdateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        record_driver_catalog_editor_error("unknown", action="overrides.update", code="INVALID_REQUEST")
        log_admin_action(
            request,
            action="driver_catalog.overrides.update",
            outcome="error",
            target_type="driver_catalog",
            metadata={"error": "INVALID_REQUEST"},
            error_message="INVALID_REQUEST",
        )
        return Response({
            "success": False,
            "error": {"code": "INVALID_REQUEST", "message": "Invalid request", "details": serializer.errors},
        }, status=400)

    driver = serializer.validated_data["driver"]
    catalog = serializer.validated_data["catalog"]
    reason = serializer.validated_data["reason"]
    errors = _validate_overrides_catalog_v2(driver, catalog)
    if errors:
        record_driver_catalog_editor_validation_failed(driver, stage="overrides.update", kind="invalid_overrides")
        record_driver_catalog_editor_error(driver, action="overrides.update", code="INVALID_CATALOG")
        log_admin_action(
            request,
            action="driver_catalog.overrides.update",
            outcome="error",
            target_type="driver_catalog",
            target_id=driver,
            metadata={"error": "INVALID_CATALOG", "driver": driver, "reason": reason},
            error_message="INVALID_CATALOG",
        )
        return Response({
            "success": False,
            "error": {"code": "INVALID_CATALOG", "message": "Invalid overrides catalog", "details": errors},
        }, status=400)

    try:
        version_obj = upload_overrides_catalog_version(
            driver=driver,
            catalog=catalog,
            created_by=request.user,
            metadata_extra={"reason": reason},
        )
        invalidate_driver_catalog_cache(driver)
    except Exception as exc:
        record_driver_catalog_editor_error(driver, action="overrides.update", code="SAVE_FAILED")
        log_admin_action(
            request,
            action="driver_catalog.overrides.update",
            outcome="error",
            target_type="driver_catalog",
            target_id=driver,
            metadata={"error": "SAVE_FAILED", "driver": driver, "reason": reason},
            error_message="SAVE_FAILED",
        )
        return Response(
            {"success": False, "error": {"code": "SAVE_FAILED", "message": str(exc)}},
            status=500,
        )
    log_admin_action(
        request,
        action="driver_catalog.overrides.update",
        outcome="success",
        target_type="driver_catalog",
        target_id=driver,
        metadata={"driver": driver, "version": version_obj.version, "reason": reason},
    )
    return Response({"driver": driver, "overrides_version": version_obj.version, "catalog": catalog})


@extend_schema(
    tags=["v2"],
    summary="Promote driver catalog base alias",
    description="Move base alias (approved/latest) to a specific version (staff-only). Requires reason.",
    request=DriverCatalogPromoteRequestSerializer,
    responses={
        200: DriverCatalogPromoteResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def promote_driver_catalog_base(request):
    denied = _ensure_manage_driver_catalogs(request, action="promote")
    if denied:
        return denied

    serializer = DriverCatalogPromoteRequestSerializer(data=request.data)
    if not serializer.is_valid():
        record_driver_catalog_editor_error("unknown", action="promote", code="INVALID_REQUEST")
        log_admin_action(
            request,
            action="driver_catalog.promote",
            outcome="error",
            target_type="driver_catalog",
            metadata={"error": "INVALID_REQUEST"},
            error_message="INVALID_REQUEST",
        )
        return Response({
            "success": False,
            "error": {"code": "INVALID_REQUEST", "message": "Invalid request", "details": serializer.errors},
        }, status=400)

    driver = serializer.validated_data["driver"]
    version = str(serializer.validated_data["version"] or "").strip()
    alias = str(serializer.validated_data.get("alias") or "approved").strip() or "approved"
    reason = serializer.validated_data["reason"]
    if alias not in {"approved", "latest"}:
        record_driver_catalog_editor_error(driver, action="promote", code="INVALID_ALIAS")
        log_admin_action(
            request,
            action="driver_catalog.promote",
            outcome="error",
            target_type="driver_catalog",
            target_id=driver,
            metadata={"error": "INVALID_ALIAS", "driver": driver, "alias": alias, "version": version, "reason": reason},
            error_message="INVALID_ALIAS",
        )
        return Response({
            "success": False,
            "error": {"code": "INVALID_ALIAS", "message": f"Unsupported alias: {alias}"},
        }, status=400)

    try:
        promote_base_alias(driver, version=version, alias=alias)
    except Exception as exc:
        record_driver_catalog_editor_error(driver, action="promote", code="PROMOTE_FAILED")
        log_admin_action(
            request,
            action="driver_catalog.promote",
            outcome="error",
            target_type="driver_catalog",
            target_id=driver,
            metadata={"error": "PROMOTE_FAILED", "driver": driver, "alias": alias, "version": version, "reason": reason},
            error_message="PROMOTE_FAILED",
        )
        return Response({
            "success": False,
            "error": {"code": "PROMOTE_FAILED", "message": str(exc)},
        }, status=400)

    invalidate_driver_catalog_cache(driver)
    log_admin_action(
        request,
        action="driver_catalog.promote",
        outcome="success",
        target_type="driver_catalog",
        target_id=driver,
        metadata={"driver": driver, "alias": alias, "version": version, "reason": reason},
    )
    return Response({"driver": driver, "alias": alias, "version": version})


@extend_schema(
    tags=["v2"],
    summary="Get command schemas editor view (v2)",
    description=(
        "Return base/overrides versions and catalogs for Command Schemas Editor (staff-only).\n\n"
        "Supports conditional requests via ETag/If-None-Match (returns 304)."
    ),
    parameters=[
        OpenApiParameter(
            name="driver",
            type=str,
            required=True,
            description="Driver name (cli/ibcmd)",
        )
    ],
    responses={
        200: CommandSchemasEditorViewResponseSerializer,
        304: OpenApiResponse(description="Not Modified"),
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAdminUser])
def get_command_schemas_editor_view(request):
    denied = _ensure_manage_driver_catalogs(request, action="editor.view")
    if denied:
        return denied

    driver = str(request.query_params.get("driver") or "").strip().lower()
    if driver not in {"cli", "ibcmd"}:
        record_driver_catalog_editor_error("unknown", action="editor.view", code="UNKNOWN_DRIVER")
        return Response({
            "success": False,
            "error": {"code": "UNKNOWN_DRIVER", "message": f"Unknown driver: {driver}"},
        }, status=400)

    artifacts = get_or_create_catalog_artifacts(driver, created_by=request.user)

    base_aliases = ArtifactAlias.objects.select_related("version").filter(
        artifact=artifacts.base,
        alias__in=["approved", "latest"],
    )
    base_versions: dict[str, ArtifactVersion | None] = {"approved": None, "latest": None}
    for alias_obj in base_aliases:
        base_versions[alias_obj.alias] = alias_obj.version

    overrides_alias = artifacts.overrides.aliases.select_related("version").get(alias="active")
    overrides_active = overrides_alias.version if overrides_alias else None

    base_resolved, base_resolved_alias = _resolve_driver_base_version(base_versions=base_versions)

    etag = compute_driver_catalog_etag(
        driver=driver,
        base_version_id=str(base_resolved.id) if base_resolved else None,
        overrides_version_id=str(overrides_active.id) if overrides_active else None,
        roles_hash=None,
    )

    if request.headers.get("If-None-Match") == etag:
        response = Response(status=304)
        response["ETag"] = etag
        return response

    try:
        base_catalog = load_catalog_json(base_resolved) if base_resolved else _build_empty_catalog_v2(driver)
        overrides_catalog = load_catalog_json(overrides_active) if overrides_active else {
            "catalog_version": 2,
            "driver": driver,
            "overrides": {"commands_by_id": {}},
        }
    except ArtifactStorageError as exc:
        record_driver_catalog_editor_error(driver, action="editor.view", code="STORAGE_ERROR")
        return Response(
            {"success": False, "error": {"code": "STORAGE_ERROR", "message": str(exc)}},
            status=500,
        )
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        record_driver_catalog_editor_error(driver, action="editor.view", code="CATALOG_INVALID")
        return Response(
            {"success": False, "error": {"code": "CATALOG_INVALID", "message": str(exc)}},
            status=500,
        )

    effective_payload: dict = {
        "base_version": str(base_resolved.version) if base_resolved else None,
        "base_version_id": str(base_resolved.id) if base_resolved else None,
        "base_alias": base_resolved_alias,
        "overrides_version": str(overrides_active.version) if overrides_active else None,
        "overrides_version_id": str(overrides_active.id) if overrides_active else None,
        "catalog": base_catalog,
        "source": "empty",
    }

    if base_resolved is not None:
        try:
            effective = get_effective_driver_catalog(
                driver=driver,
                base_version=base_resolved,
                overrides_version=overrides_active,
            )
            effective_payload = {
                "base_version": str(effective.base_version),
                "base_version_id": str(effective.base_version_id),
                "base_alias": base_resolved_alias,
                "overrides_version": str(effective.overrides_version) if effective.overrides_version else None,
                "overrides_version_id": str(effective.overrides_version_id) if effective.overrides_version_id else None,
                "catalog": effective.catalog,
                "source": effective.source,
            }
        except (ArtifactStorageError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            record_driver_catalog_editor_error(driver, action="editor.view", code="CATALOG_INVALID")
            return Response(
                {"success": False, "error": {"code": "CATALOG_INVALID", "message": str(exc)}},
                status=500,
            )

    payload = {
        "driver": driver,
        "etag": etag,
        "base": {
            "approved_version": str(base_versions["approved"].version) if base_versions["approved"] else None,
            "approved_version_id": str(base_versions["approved"].id) if base_versions["approved"] else None,
            "latest_version": str(base_versions["latest"].version) if base_versions["latest"] else None,
            "latest_version_id": str(base_versions["latest"].id) if base_versions["latest"] else None,
        },
        "overrides": {
            "active_version": str(overrides_active.version) if overrides_active else None,
            "active_version_id": str(overrides_active.id) if overrides_active else None,
        },
        "catalogs": {
            "base": base_catalog,
            "overrides": overrides_catalog,
            "effective": effective_payload,
        },
    }
    response = Response(payload)
    response["ETag"] = etag
    response["Cache-Control"] = "private, max-age=0"
    return response


@extend_schema(
    tags=["v2"],
    summary="List command schema artifact versions (v2)",
    description="List base/overrides versions for Command Schemas Editor (staff-only).",
    parameters=[
        OpenApiParameter(name="driver", type=str, required=True, description="Driver name (cli/ibcmd)"),
        OpenApiParameter(name="artifact", type=str, required=True, description="Artifact type (base/overrides)"),
        OpenApiParameter(name="limit", type=int, required=False, description="Max items (default 50, max 200)"),
        OpenApiParameter(name="offset", type=int, required=False, description="Offset (default 0)"),
    ],
    responses={
        200: CommandSchemasVersionsListResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAdminUser])
def list_command_schema_versions(request):
    denied = _ensure_manage_driver_catalogs(request, action="versions.list")
    if denied:
        return denied

    driver = str(request.query_params.get("driver") or "").strip().lower()
    if driver not in {"cli", "ibcmd"}:
        record_driver_catalog_editor_error("unknown", action="versions.list", code="UNKNOWN_DRIVER")
        return Response({
            "success": False,
            "error": {"code": "UNKNOWN_DRIVER", "message": f"Unknown driver: {driver}"},
        }, status=400)

    artifact_type = str(request.query_params.get("artifact") or "").strip().lower()
    if artifact_type not in {"base", "overrides"}:
        record_driver_catalog_editor_error(driver, action="versions.list", code="INVALID_ARTIFACT")
        return Response({
            "success": False,
            "error": {"code": "INVALID_ARTIFACT", "message": f"Unsupported artifact: {artifact_type}"},
        }, status=400)

    try:
        limit = int(request.query_params.get("limit") or 50)
        offset = int(request.query_params.get("offset") or 0)
    except (TypeError, ValueError):
        record_driver_catalog_editor_error(driver, action="versions.list", code="INVALID_PAGINATION")
        return Response({
            "success": False,
            "error": {"code": "INVALID_PAGINATION", "message": "limit/offset must be integers"},
        }, status=400)

    if limit < 1 or limit > 200 or offset < 0:
        record_driver_catalog_editor_error(driver, action="versions.list", code="INVALID_PAGINATION")
        return Response({
            "success": False,
            "error": {"code": "INVALID_PAGINATION", "message": "limit must be 1..200 and offset >= 0"},
        }, status=400)

    artifacts = get_or_create_catalog_artifacts(driver, created_by=request.user)
    artifact_obj = artifacts.base if artifact_type == "base" else artifacts.overrides

    versions_qs = artifact_obj.versions.order_by("-created_at")
    total = versions_qs.count()
    page = versions_qs[offset : offset + limit]

    versions = []
    for v in page:
        versions.append({
            "id": str(v.id),
            "version": str(v.version),
            "created_at": v.created_at.isoformat() if getattr(v, "created_at", None) else None,
            "created_by": getattr(v.created_by, "username", "") if getattr(v, "created_by", None) else "",
            "metadata": v.metadata if isinstance(v.metadata, dict) else {},
        })

    return Response({
        "driver": driver,
        "artifact": artifact_type,
        "versions": versions,
        "count": total,
    })


@extend_schema(
    tags=["v2"],
    summary="Update command schema overrides (v2)",
    description=(
        "Upload new overrides catalog version and move alias active (staff-only). Requires reason.\n\n"
        "Supports optimistic concurrency via If-Match header or expected_etag in request body."
    ),
    request=CommandSchemasOverridesUpdateRequestSerializer,
    responses={
        200: CommandSchemasOverridesUpdateResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        409: OpenApiResponse(description="Conflict"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def update_command_schema_overrides(request):
    denied = _ensure_manage_driver_catalogs(request, action="overrides.update")
    if denied:
        return denied

    serializer = CommandSchemasOverridesUpdateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        record_driver_catalog_editor_error("unknown", action="overrides.update", code="INVALID_REQUEST")
        log_admin_action(
            request,
            action="driver_catalog.overrides.update",
            outcome="error",
            target_type="driver_catalog",
            metadata={"error": "INVALID_REQUEST"},
            error_message="INVALID_REQUEST",
        )
        return Response({
            "success": False,
            "error": {"code": "INVALID_REQUEST", "message": "Invalid request", "details": serializer.errors},
        }, status=400)

    driver = serializer.validated_data["driver"]
    catalog = serializer.validated_data["catalog"]
    reason = serializer.validated_data["reason"]
    expected_etag = _extract_expected_etag(request, serializer.validated_data.get("expected_etag"))

    artifacts = get_or_create_catalog_artifacts(driver, created_by=request.user)
    overrides_alias = artifacts.overrides.aliases.select_related("version").get(alias="active")
    overrides_active = overrides_alias.version if overrides_alias else None

    base_aliases = ArtifactAlias.objects.select_related("version").filter(
        artifact=artifacts.base,
        alias__in=["approved", "latest"],
    )
    base_versions: dict[str, ArtifactVersion | None] = {"approved": None, "latest": None}
    for alias_obj in base_aliases:
        base_versions[alias_obj.alias] = alias_obj.version
    base_resolved, _base_alias = _resolve_driver_base_version(base_versions=base_versions)

    current_etag = compute_driver_catalog_etag(
        driver=driver,
        base_version_id=str(base_resolved.id) if base_resolved else None,
        overrides_version_id=str(overrides_active.id) if overrides_active else None,
        roles_hash=None,
    )
    if expected_etag is not None and expected_etag != current_etag:
        record_driver_catalog_editor_conflict(driver, action="overrides.update")
        record_driver_catalog_editor_error(driver, action="overrides.update", code="CONFLICT")
        log_admin_action(
            request,
            action="driver_catalog.overrides.update",
            outcome="error",
            target_type="driver_catalog",
            target_id=driver,
            metadata={"error": "CONFLICT", "driver": driver, "reason": reason},
            error_message="CONFLICT",
        )
        response = Response(
            {
                "success": False,
                "error": {
                    "code": "CONFLICT",
                    "message": "Active overrides changed since you opened the editor.",
                    "details": {
                        "expected_etag": expected_etag,
                        "current_etag": current_etag,
                        "base_version": str(base_resolved.version) if base_resolved else None,
                        "overrides_version": str(overrides_active.version) if overrides_active else None,
                    },
                },
            },
            status=409,
        )
        response["ETag"] = current_etag
        return response

    errors = _validate_overrides_catalog_v2(driver, catalog)
    if errors:
        record_driver_catalog_editor_validation_failed(driver, stage="overrides.update", kind="invalid_overrides")
        record_driver_catalog_editor_error(driver, action="overrides.update", code="INVALID_CATALOG")
        log_admin_action(
            request,
            action="driver_catalog.overrides.update",
            outcome="error",
            target_type="driver_catalog",
            target_id=driver,
            metadata={"error": "INVALID_CATALOG", "driver": driver, "reason": reason},
            error_message="INVALID_CATALOG",
        )
        return Response({
            "success": False,
            "error": {"code": "INVALID_CATALOG", "message": "Invalid overrides catalog", "details": errors},
        }, status=400)

    if driver == "ibcmd" and base_resolved is None:
        record_driver_catalog_editor_error(driver, action="overrides.update", code="BASE_CATALOG_MISSING")
        log_admin_action(
            request,
            action="driver_catalog.overrides.update",
            outcome="error",
            target_type="driver_catalog",
            target_id=driver,
            metadata={"error": "BASE_CATALOG_MISSING", "driver": driver, "reason": reason},
            error_message="BASE_CATALOG_MISSING",
        )
        return Response({
            "success": False,
            "error": {"code": "BASE_CATALOG_MISSING", "message": "Base catalog is required for ibcmd overrides."},
        }, status=400)

    if driver == "ibcmd" and base_resolved is not None:
        try:
            base_catalog = load_catalog_json(base_resolved)
        except (ArtifactStorageError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            record_driver_catalog_editor_error(driver, action="overrides.update", code="CATALOG_INVALID")
            log_admin_action(
                request,
                action="driver_catalog.overrides.update",
                outcome="error",
                target_type="driver_catalog",
                target_id=driver,
                metadata={"error": "CATALOG_INVALID", "driver": driver, "reason": reason},
                error_message="CATALOG_INVALID",
            )
            return Response(
                {"success": False, "error": {"code": "CATALOG_INVALID", "message": str(exc)}},
                status=500,
            )

        patch = catalog.get("overrides")
        if isinstance(patch, dict):
            effective = copy.deepcopy(base_catalog)
            _deep_merge_dict(effective, patch)
            validation_errors = validate_ibcmd_catalog_v2(effective)
            if validation_errors:
                record_driver_catalog_editor_validation_failed(driver, stage="overrides.update", kind="invalid_effective")
                record_driver_catalog_editor_error(driver, action="overrides.update", code="INVALID_EFFECTIVE_CATALOG")
                log_admin_action(
                    request,
                    action="driver_catalog.overrides.update",
                    outcome="error",
                    target_type="driver_catalog",
                    target_id=driver,
                    metadata={"error": "INVALID_EFFECTIVE_CATALOG", "driver": driver, "reason": reason},
                    error_message="INVALID_EFFECTIVE_CATALOG",
                )
                return Response({
                    "success": False,
                    "error": {
                        "code": "INVALID_EFFECTIVE_CATALOG",
                        "message": "Invalid effective catalog",
                        "details": validation_errors,
                    },
                }, status=400)

    if driver == "cli":
        try:
            cli_base_catalog = load_catalog_json(base_resolved) if base_resolved else _build_empty_catalog_v2(driver)
        except (ArtifactStorageError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            record_driver_catalog_editor_error(driver, action="overrides.update", code="CATALOG_INVALID")
            log_admin_action(
                request,
                action="driver_catalog.overrides.update",
                outcome="error",
                target_type="driver_catalog",
                target_id=driver,
                metadata={"error": "CATALOG_INVALID", "driver": driver, "reason": reason},
                error_message="CATALOG_INVALID",
            )
            return Response(
                {"success": False, "error": {"code": "CATALOG_INVALID", "message": str(exc)}},
                status=500,
            )

        patch = catalog.get("overrides")
        effective = copy.deepcopy(cli_base_catalog)
        if isinstance(patch, dict):
            _deep_merge_dict(effective, patch)

        validation_issues = _validate_cli_catalog_v2(effective)
        if any(item.get("severity") == "error" for item in validation_issues):
            record_driver_catalog_editor_validation_failed(driver, stage="overrides.update", kind="invalid_effective")
            record_driver_catalog_editor_error(driver, action="overrides.update", code="INVALID_EFFECTIVE_CATALOG")
            log_admin_action(
                request,
                action="driver_catalog.overrides.update",
                outcome="error",
                target_type="driver_catalog",
                target_id=driver,
                metadata={"error": "INVALID_EFFECTIVE_CATALOG", "driver": driver, "reason": reason},
                error_message="INVALID_EFFECTIVE_CATALOG",
            )
            return Response({
                "success": False,
                "error": {
                    "code": "INVALID_EFFECTIVE_CATALOG",
                    "message": "Invalid effective catalog",
                    "details": validation_issues,
                },
            }, status=400)

    try:
        version_obj = upload_overrides_catalog_version(
            driver=driver,
            catalog=catalog,
            created_by=request.user,
            metadata_extra={"reason": reason},
        )
        invalidate_driver_catalog_cache(driver)
    except Exception as exc:
        record_driver_catalog_editor_error(driver, action="overrides.update", code="SAVE_FAILED")
        log_admin_action(
            request,
            action="driver_catalog.overrides.update",
            outcome="error",
            target_type="driver_catalog",
            target_id=driver,
            metadata={"error": "SAVE_FAILED", "driver": driver, "reason": reason},
            error_message="SAVE_FAILED",
        )
        return Response(
            {"success": False, "error": {"code": "SAVE_FAILED", "message": str(exc)}},
            status=500,
        )

    new_etag = compute_driver_catalog_etag(
        driver=driver,
        base_version_id=str(base_resolved.id) if base_resolved else None,
        overrides_version_id=str(version_obj.id),
        roles_hash=None,
    )

    log_admin_action(
        request,
        action="driver_catalog.overrides.update",
        outcome="success",
        target_type="driver_catalog",
        target_id=driver,
        metadata={"driver": driver, "version": version_obj.version, "reason": reason},
    )
    response = Response({"driver": driver, "overrides_version": str(version_obj.version), "etag": new_etag})
    response["ETag"] = new_etag
    response["Cache-Control"] = "private, max-age=0"
    return response


@extend_schema(
    tags=["v2"],
    summary="Rollback command schema overrides (v2)",
    description="Move overrides alias active to a specific version (staff-only). Requires reason.",
    request=CommandSchemasOverridesRollbackRequestSerializer,
    responses={
        200: CommandSchemasOverridesRollbackResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        409: OpenApiResponse(description="Conflict"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def rollback_command_schema_overrides(request):
    denied = _ensure_manage_driver_catalogs(request, action="overrides.rollback")
    if denied:
        return denied

    serializer = CommandSchemasOverridesRollbackRequestSerializer(data=request.data)
    if not serializer.is_valid():
        record_driver_catalog_editor_error("unknown", action="overrides.rollback", code="INVALID_REQUEST")
        log_admin_action(
            request,
            action="driver_catalog.overrides.rollback",
            outcome="error",
            target_type="driver_catalog",
            metadata={"error": "INVALID_REQUEST"},
            error_message="INVALID_REQUEST",
        )
        return Response({
            "success": False,
            "error": {"code": "INVALID_REQUEST", "message": "Invalid request", "details": serializer.errors},
        }, status=400)

    driver = serializer.validated_data["driver"]
    reason = serializer.validated_data["reason"]
    expected_etag = _extract_expected_etag(request, serializer.validated_data.get("expected_etag"))

    artifacts = get_or_create_catalog_artifacts(driver, created_by=request.user)
    overrides_alias = artifacts.overrides.aliases.select_related("version").get(alias="active")
    overrides_active = overrides_alias.version if overrides_alias else None

    base_aliases = ArtifactAlias.objects.select_related("version").filter(
        artifact=artifacts.base,
        alias__in=["approved", "latest"],
    )
    base_versions: dict[str, ArtifactVersion | None] = {"approved": None, "latest": None}
    for alias_obj in base_aliases:
        base_versions[alias_obj.alias] = alias_obj.version
    base_resolved, _base_alias = _resolve_driver_base_version(base_versions=base_versions)

    current_etag = compute_driver_catalog_etag(
        driver=driver,
        base_version_id=str(base_resolved.id) if base_resolved else None,
        overrides_version_id=str(overrides_active.id) if overrides_active else None,
        roles_hash=None,
    )
    if expected_etag is not None and expected_etag != current_etag:
        record_driver_catalog_editor_conflict(driver, action="overrides.rollback")
        record_driver_catalog_editor_error(driver, action="overrides.rollback", code="CONFLICT")
        log_admin_action(
            request,
            action="driver_catalog.overrides.rollback",
            outcome="error",
            target_type="driver_catalog",
            target_id=driver,
            metadata={"error": "CONFLICT", "driver": driver, "reason": reason},
            error_message="CONFLICT",
        )
        response = Response(
            {
                "success": False,
                "error": {
                    "code": "CONFLICT",
                    "message": "Active overrides changed since you opened the editor.",
                    "details": {"expected_etag": expected_etag, "current_etag": current_etag},
                },
            },
            status=409,
        )
        response["ETag"] = current_etag
        return response

    target_version: ArtifactVersion | None = None
    version_id = serializer.validated_data.get("version_id")
    if version_id is not None:
        target_version = artifacts.overrides.versions.filter(id=version_id).first()
    else:
        version_str = str(serializer.validated_data.get("version") or "").strip()
        if version_str:
            target_version = artifacts.overrides.versions.filter(version=version_str).first()

    if target_version is None:
        record_driver_catalog_editor_error(driver, action="overrides.rollback", code="VERSION_NOT_FOUND")
        log_admin_action(
            request,
            action="driver_catalog.overrides.rollback",
            outcome="error",
            target_type="driver_catalog",
            target_id=driver,
            metadata={"error": "VERSION_NOT_FOUND", "driver": driver, "reason": reason},
            error_message="VERSION_NOT_FOUND",
        )
        return Response({
            "success": False,
            "error": {"code": "VERSION_NOT_FOUND", "message": "Requested overrides version not found"},
        }, status=400)

    try:
        ArtifactAlias.objects.update_or_create(
            artifact=artifacts.overrides,
            alias="active",
            defaults={"version": target_version},
        )

        invalidate_driver_catalog_cache(driver)

        new_etag = compute_driver_catalog_etag(
            driver=driver,
            base_version_id=str(base_resolved.id) if base_resolved else None,
            overrides_version_id=str(target_version.id),
            roles_hash=None,
        )
    except Exception as exc:
        record_driver_catalog_editor_error(driver, action="overrides.rollback", code="ROLLBACK_FAILED")
        log_admin_action(
            request,
            action="driver_catalog.overrides.rollback",
            outcome="error",
            target_type="driver_catalog",
            target_id=driver,
            metadata={"error": "ROLLBACK_FAILED", "driver": driver, "reason": reason},
            error_message="ROLLBACK_FAILED",
        )
        return Response(
            {"success": False, "error": {"code": "ROLLBACK_FAILED", "message": str(exc)}},
            status=500,
        )

    log_admin_action(
        request,
        action="driver_catalog.overrides.rollback",
        outcome="success",
        target_type="driver_catalog",
        target_id=driver,
        metadata={"driver": driver, "version": str(target_version.version), "reason": reason},
    )

    response = Response({"driver": driver, "overrides_version": str(target_version.version), "etag": new_etag})
    response["ETag"] = new_etag
    response["Cache-Control"] = "private, max-age=0"
    return response


@extend_schema(
    tags=["v2"],
    summary="Import ITS command schemas (v2)",
    description=(
        "Parse ITS JSON into driver command schema catalog and optionally save (staff-only).\n\n"
        "driver=cli: updates legacy file-backed catalog (v1) and uploads v2 base catalog artifact.\n"
        "driver=ibcmd: generates schema-driven catalog v2 and uploads it as a versioned artifact."
    ),
    request=CommandSchemasImportRequestSerializer,
    responses={
        200: CommandSchemasImportResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def import_its_command_schemas(request):
    denied = _ensure_manage_driver_catalogs(request, action="import_its")
    if denied:
        return denied

    serializer = CommandSchemasImportRequestSerializer(data=request.data)
    if not serializer.is_valid():
        record_driver_catalog_editor_error("unknown", action="import_its", code="INVALID_REQUEST")
        log_admin_action(
            request,
            action="driver_catalog.import_its",
            outcome="error",
            target_type="driver_catalog",
            metadata={"error": "INVALID_REQUEST"},
            error_message="INVALID_REQUEST",
        )
        return Response({
            "success": False,
            "error": {"code": "INVALID_REQUEST", "message": "Invalid request", "details": serializer.errors},
        }, status=400)

    driver = serializer.validated_data["driver"]
    its_payload = serializer.validated_data["its_payload"]
    reason = serializer.validated_data["reason"]

    if driver == "cli":
        catalog = build_cli_catalog_from_its(its_payload)
        errors = validate_cli_catalog(catalog)
        if errors:
            record_driver_catalog_editor_validation_failed(driver, stage="import_its", kind="invalid_parsed")
            record_driver_catalog_editor_error(driver, action="import_its", code="INVALID_CATALOG")
            log_admin_action(
                request,
                action="driver_catalog.import_its",
                outcome="error",
                target_type="driver_catalog",
                target_id=driver,
                metadata={"error": "INVALID_CATALOG", "driver": driver, "reason": reason},
                error_message="INVALID_CATALOG",
            )
            return Response({
                "success": False,
                "error": {"code": "INVALID_CATALOG", "message": "Parsed CLI catalog is invalid", "details": errors},
            }, status=400)
        if serializer.validated_data.get("save", True):
            try:
                save_cli_command_catalog(catalog)
                upload_base_catalog_version(
                    driver="cli",
                    catalog=cli_catalog_v1_to_v2(catalog),
                    created_by=request.user,
                    metadata_extra={"reason": reason},
                )
                invalidate_driver_catalog_cache("cli")
            except Exception as exc:
                record_driver_catalog_editor_error(driver, action="import_its", code="IMPORT_FAILED")
                log_admin_action(
                    request,
                    action="driver_catalog.import_its",
                    outcome="error",
                    target_type="driver_catalog",
                    target_id=driver,
                    metadata={"error": "IMPORT_FAILED", "driver": driver, "reason": reason},
                    error_message="IMPORT_FAILED",
                )
                return Response(
                    {"success": False, "error": {"code": "IMPORT_FAILED", "message": str(exc)}},
                    status=500,
                )
    else:
        catalog = build_ibcmd_catalog_v2_from_its(its_payload)
        errors = validate_ibcmd_catalog_v2(catalog)
        if errors:
            record_driver_catalog_editor_validation_failed(driver, stage="import_its", kind="invalid_parsed")
            record_driver_catalog_editor_error(driver, action="import_its", code="INVALID_CATALOG")
            log_admin_action(
                request,
                action="driver_catalog.import_its",
                outcome="error",
                target_type="driver_catalog",
                target_id=driver,
                metadata={"error": "INVALID_CATALOG", "driver": driver, "reason": reason},
                error_message="INVALID_CATALOG",
            )
            return Response({
                "success": False,
                "error": {"code": "INVALID_CATALOG", "message": "Parsed IBCMD catalog is invalid", "details": errors},
            }, status=400)
        if serializer.validated_data.get("save", True):
            try:
                upload_base_catalog_version(
                    driver="ibcmd",
                    catalog=catalog,
                    created_by=request.user,
                    metadata_extra={"reason": reason},
                )
                invalidate_driver_catalog_cache("ibcmd")
            except Exception as exc:
                record_driver_catalog_editor_error(driver, action="import_its", code="IMPORT_FAILED")
                log_admin_action(
                    request,
                    action="driver_catalog.import_its",
                    outcome="error",
                    target_type="driver_catalog",
                    target_id=driver,
                    metadata={"error": "IMPORT_FAILED", "driver": driver, "reason": reason},
                    error_message="IMPORT_FAILED",
                )
                return Response(
                    {"success": False, "error": {"code": "IMPORT_FAILED", "message": str(exc)}},
                    status=500,
                )

    log_admin_action(
        request,
        action="driver_catalog.import_its",
        outcome="success",
        target_type="driver_catalog",
        target_id=driver,
        metadata={
            "driver": driver,
            "version": catalog.get("version") or catalog.get("platform_version"),
            "reason": reason,
        },
    )
    return Response({"driver": driver, "catalog": catalog})


@extend_schema(
    tags=["v2"],
    summary="Promote command schemas base alias (v2)",
    description="Move base alias (approved/latest) to a specific version (staff-only). Requires reason.",
    request=CommandSchemasPromoteRequestSerializer,
    responses={
        200: CommandSchemasPromoteResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def promote_command_schemas_base(request):
    denied = _ensure_manage_driver_catalogs(request, action="promote")
    if denied:
        return denied

    serializer = CommandSchemasPromoteRequestSerializer(data=request.data)
    if not serializer.is_valid():
        record_driver_catalog_editor_error("unknown", action="promote", code="INVALID_REQUEST")
        log_admin_action(
            request,
            action="driver_catalog.promote",
            outcome="error",
            target_type="driver_catalog",
            metadata={"error": "INVALID_REQUEST"},
            error_message="INVALID_REQUEST",
        )
        return Response({
            "success": False,
            "error": {"code": "INVALID_REQUEST", "message": "Invalid request", "details": serializer.errors},
        }, status=400)

    driver = serializer.validated_data["driver"]
    version = str(serializer.validated_data["version"] or "").strip()
    alias = str(serializer.validated_data.get("alias") or "approved").strip() or "approved"
    reason = serializer.validated_data["reason"]
    if alias not in {"approved", "latest"}:
        record_driver_catalog_editor_error(driver, action="promote", code="INVALID_ALIAS")
        log_admin_action(
            request,
            action="driver_catalog.promote",
            outcome="error",
            target_type="driver_catalog",
            target_id=driver,
            metadata={"error": "INVALID_ALIAS", "driver": driver, "alias": alias, "version": version, "reason": reason},
            error_message="INVALID_ALIAS",
        )
        return Response({
            "success": False,
            "error": {"code": "INVALID_ALIAS", "message": f"Unsupported alias: {alias}"},
        }, status=400)

    try:
        promote_base_alias(driver, version=version, alias=alias)
    except Exception as exc:
        record_driver_catalog_editor_error(driver, action="promote", code="PROMOTE_FAILED")
        log_admin_action(
            request,
            action="driver_catalog.promote",
            outcome="error",
            target_type="driver_catalog",
            target_id=driver,
            metadata={
                "error": "PROMOTE_FAILED",
                "driver": driver,
                "alias": alias,
                "version": version,
                "reason": reason,
            },
            error_message="PROMOTE_FAILED",
        )
        return Response({
            "success": False,
            "error": {"code": "PROMOTE_FAILED", "message": str(exc)},
        }, status=400)

    invalidate_driver_catalog_cache(driver)
    log_admin_action(
        request,
        action="driver_catalog.promote",
        outcome="success",
        target_type="driver_catalog",
        target_id=driver,
        metadata={"driver": driver, "alias": alias, "version": version, "reason": reason},
    )
    return Response({"driver": driver, "alias": alias, "version": version})


@extend_schema(
    tags=["v2"],
    summary="Validate command schemas (v2)",
    description=(
        "Validate effective driver command schema catalog.\n\n"
        "If catalog is provided in request body, validates draft overrides without saving."
    ),
    request=CommandSchemasValidateRequestSerializer,
    responses={
        200: CommandSchemasValidateResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def validate_command_schemas(request):
    denied = _ensure_manage_driver_catalogs(request, action="validate")
    if denied:
        return denied

    serializer = CommandSchemasValidateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        record_driver_catalog_editor_error("unknown", action="validate", code="INVALID_REQUEST")
        return Response({
            "success": False,
            "error": {"code": "INVALID_REQUEST", "message": "Invalid request", "details": serializer.errors},
        }, status=400)

    driver = serializer.validated_data["driver"]
    draft_overrides = serializer.validated_data.get("catalog")

    artifacts = get_or_create_catalog_artifacts(driver, created_by=request.user)

    base_aliases = ArtifactAlias.objects.select_related("version").filter(
        artifact=artifacts.base,
        alias__in=["approved", "latest"],
    )
    base_versions: dict[str, ArtifactVersion | None] = {"approved": None, "latest": None}
    for alias_obj in base_aliases:
        base_versions[alias_obj.alias] = alias_obj.version

    overrides_alias = artifacts.overrides.aliases.select_related("version").get(alias="active")
    overrides_active = overrides_alias.version if overrides_alias else None

    base_resolved, _base_alias = _resolve_driver_base_version(base_versions=base_versions)
    if base_resolved is None:
        record_driver_catalog_editor_error(driver, action="validate", code="BASE_CATALOG_MISSING")
        return Response({
            "success": False,
            "error": {"code": "BASE_CATALOG_MISSING", "message": "Base catalog is not imported yet"},
        }, status=400)

    try:
        base_catalog = load_catalog_json(base_resolved)
    except ArtifactStorageError as exc:
        record_driver_catalog_editor_error(driver, action="validate", code="STORAGE_ERROR")
        return Response(
            {"success": False, "error": {"code": "STORAGE_ERROR", "message": str(exc)}},
            status=500,
        )
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        record_driver_catalog_editor_error(driver, action="validate", code="CATALOG_INVALID")
        return Response(
            {"success": False, "error": {"code": "CATALOG_INVALID", "message": str(exc)}},
            status=500,
        )

    overrides_version = str(overrides_active.version) if overrides_active else None
    overrides_version_id = str(overrides_active.id) if overrides_active else None
    overrides_catalog = None

    if draft_overrides is not None:
        errors = _validate_overrides_catalog_v2(driver, draft_overrides)
        if errors:
            record_driver_catalog_editor_validation_failed(driver, stage="validate", kind="invalid_overrides")
            record_driver_catalog_editor_error(driver, action="validate", code="INVALID_CATALOG")
            return Response({
                "success": False,
                "error": {"code": "INVALID_CATALOG", "message": "Invalid overrides catalog", "details": errors},
            }, status=400)
        overrides_catalog = draft_overrides
        overrides_version = None
        overrides_version_id = None
    else:
        try:
            overrides_catalog = load_catalog_json(overrides_active) if overrides_active else {
                "catalog_version": 2,
                "driver": driver,
                "overrides": {"commands_by_id": {}},
            }
        except ArtifactStorageError as exc:
            record_driver_catalog_editor_error(driver, action="validate", code="STORAGE_ERROR")
            return Response(
                {"success": False, "error": {"code": "STORAGE_ERROR", "message": str(exc)}},
                status=500,
            )
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            record_driver_catalog_editor_error(driver, action="validate", code="CATALOG_INVALID")
            return Response(
                {"success": False, "error": {"code": "CATALOG_INVALID", "message": str(exc)}},
                status=500,
            )

    patch = overrides_catalog.get("overrides") if isinstance(overrides_catalog, dict) else None
    if isinstance(patch, dict):
        _deep_merge_dict(base_catalog, patch)

    issues: list[dict] = []
    if driver == "ibcmd":
        for err in validate_ibcmd_catalog_v2(base_catalog):
            issues.append(_issue("error", "IBCMD_CATALOG_INVALID", err))
        for cmd_id, cmd in _get_commands_by_id(base_catalog).items():
            if isinstance(cmd_id, str) and isinstance(cmd, dict):
                issues.extend(_collect_command_param_issues(cmd_id, cmd))
    else:
        issues.extend(_validate_cli_catalog_v2(base_catalog))

    errors_count = sum(1 for item in issues if item.get("severity") == "error")
    warnings_count = sum(1 for item in issues if item.get("severity") == "warning")

    if errors_count:
        record_driver_catalog_editor_validation_failed(driver, stage="validate", kind="invalid_effective")

    return Response({
        "driver": driver,
        "ok": errors_count == 0,
        "base_version": str(base_resolved.version),
        "base_version_id": str(base_resolved.id),
        "overrides_version": overrides_version,
        "overrides_version_id": overrides_version_id,
        "issues": issues,
        "errors_count": errors_count,
        "warnings_count": warnings_count,
    })


@extend_schema(
    tags=["v2"],
    summary="Preview command argv (v2)",
    description=(
        "Build argv/argv_masked for a single command using effective catalog.\n\n"
        "If catalog is provided in request body, uses draft overrides without saving."
    ),
    request=CommandSchemasPreviewRequestSerializer,
    responses={
        200: CommandSchemasPreviewResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def preview_command_schemas(request):
    denied = _ensure_manage_driver_catalogs(request, action="preview")
    if denied:
        return denied

    serializer = CommandSchemasPreviewRequestSerializer(data=request.data)
    if not serializer.is_valid():
        record_driver_catalog_editor_error("unknown", action="preview", code="INVALID_REQUEST")
        return Response({
            "success": False,
            "error": {"code": "INVALID_REQUEST", "message": "Invalid request", "details": serializer.errors},
        }, status=400)

    driver = serializer.validated_data["driver"]
    command_id = str(serializer.validated_data["command_id"] or "").strip()
    if not command_id:
        record_driver_catalog_editor_error(driver, action="preview", code="MISSING_COMMAND_ID")
        return Response({
            "success": False,
            "error": {"code": "MISSING_COMMAND_ID", "message": "command_id is required"},
        }, status=400)

    mode = serializer.validated_data.get("mode") or "guided"
    strict = mode == "guided"
    params = serializer.validated_data.get("params") or {}
    additional_args = serializer.validated_data.get("additional_args") or []
    draft_overrides = serializer.validated_data.get("catalog")

    artifacts = get_or_create_catalog_artifacts(driver, created_by=request.user)

    base_aliases = ArtifactAlias.objects.select_related("version").filter(
        artifact=artifacts.base,
        alias__in=["approved", "latest"],
    )
    base_versions: dict[str, ArtifactVersion | None] = {"approved": None, "latest": None}
    for alias_obj in base_aliases:
        base_versions[alias_obj.alias] = alias_obj.version

    overrides_alias = artifacts.overrides.aliases.select_related("version").get(alias="active")
    overrides_active = overrides_alias.version if overrides_alias else None

    base_resolved, _base_alias = _resolve_driver_base_version(base_versions=base_versions)
    if base_resolved is None:
        record_driver_catalog_editor_error(driver, action="preview", code="BASE_CATALOG_MISSING")
        return Response({
            "success": False,
            "error": {"code": "BASE_CATALOG_MISSING", "message": "Base catalog is not imported yet"},
        }, status=400)

    try:
        base_catalog = load_catalog_json(base_resolved)
    except ArtifactStorageError as exc:
        record_driver_catalog_editor_error(driver, action="preview", code="STORAGE_ERROR")
        return Response(
            {"success": False, "error": {"code": "STORAGE_ERROR", "message": str(exc)}},
            status=500,
        )
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        record_driver_catalog_editor_error(driver, action="preview", code="CATALOG_INVALID")
        return Response(
            {"success": False, "error": {"code": "CATALOG_INVALID", "message": str(exc)}},
            status=500,
        )

    overrides_catalog = None
    if draft_overrides is not None:
        errors = _validate_overrides_catalog_v2(driver, draft_overrides)
        if errors:
            record_driver_catalog_editor_error(driver, action="preview", code="INVALID_CATALOG")
            return Response({
                "success": False,
                "error": {"code": "INVALID_CATALOG", "message": "Invalid overrides catalog", "details": errors},
            }, status=400)
        overrides_catalog = draft_overrides
    else:
        try:
            overrides_catalog = load_catalog_json(overrides_active) if overrides_active else {
                "catalog_version": 2,
                "driver": driver,
                "overrides": {"commands_by_id": {}},
            }
        except ArtifactStorageError as exc:
            record_driver_catalog_editor_error(driver, action="preview", code="STORAGE_ERROR")
            return Response(
                {"success": False, "error": {"code": "STORAGE_ERROR", "message": str(exc)}},
                status=500,
            )
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            record_driver_catalog_editor_error(driver, action="preview", code="CATALOG_INVALID")
            return Response(
                {"success": False, "error": {"code": "CATALOG_INVALID", "message": str(exc)}},
                status=500,
            )

    base_command = _get_commands_by_id(base_catalog).get(command_id)

    overrides_patch = None
    if isinstance(overrides_catalog, dict):
        patch = overrides_catalog.get("overrides")
        if isinstance(patch, dict):
            commands_patch = patch.get("commands_by_id")
            if isinstance(commands_patch, dict):
                overrides_patch = commands_patch.get(command_id)

    if not isinstance(base_command, dict) and not isinstance(overrides_patch, dict):
        record_driver_catalog_editor_error(driver, action="preview", code="COMMAND_NOT_FOUND")
        return Response({
            "success": False,
            "error": {"code": "COMMAND_NOT_FOUND", "message": f"Unknown command_id: {command_id}"},
        }, status=400)

    effective_command: dict = copy.deepcopy(base_command) if isinstance(base_command, dict) else {}
    if isinstance(overrides_patch, dict):
        _deep_merge_dict(effective_command, overrides_patch)

    try:
        argv, argv_masked = _build_command_argv(
            command=effective_command,
            params=params,
            additional_args=additional_args,
            strict=strict,
        )
    except ValueError as exc:
        record_driver_catalog_editor_error(driver, action="preview", code="INVALID_PREVIEW")
        return Response({
            "success": False,
            "error": {"code": "INVALID_PREVIEW", "message": str(exc)},
        }, status=400)

    return Response({
        "driver": driver,
        "command_id": command_id,
        "argv": argv,
        "argv_masked": argv_masked,
        "risk_level": str(effective_command.get("risk_level") or "").strip() or None,
        "scope": str(effective_command.get("scope") or "").strip() or None,
        "disabled": bool(effective_command.get("disabled")) if "disabled" in effective_command else None,
    })


@extend_schema(
    tags=["v2"],
    summary="Diff command schema (v2)",
    description=(
        "Return base -> effective diff for a single command.\n\n"
        "If catalog is provided in request body, uses draft overrides without saving."
    ),
    request=CommandSchemasDiffRequestSerializer,
    responses={
        200: CommandSchemasDiffResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def diff_command_schemas(request):
    denied = _ensure_manage_driver_catalogs(request, action="diff")
    if denied:
        return denied

    serializer = CommandSchemasDiffRequestSerializer(data=request.data)
    if not serializer.is_valid():
        record_driver_catalog_editor_error("unknown", action="diff", code="INVALID_REQUEST")
        return Response({
            "success": False,
            "error": {"code": "INVALID_REQUEST", "message": "Invalid request", "details": serializer.errors},
        }, status=400)

    driver = serializer.validated_data["driver"]
    command_id = str(serializer.validated_data["command_id"] or "").strip()
    if not command_id:
        record_driver_catalog_editor_error(driver, action="diff", code="MISSING_COMMAND_ID")
        return Response({
            "success": False,
            "error": {"code": "MISSING_COMMAND_ID", "message": "command_id is required"},
        }, status=400)

    draft_overrides = serializer.validated_data.get("catalog")

    artifacts = get_or_create_catalog_artifacts(driver, created_by=request.user)

    base_aliases = ArtifactAlias.objects.select_related("version").filter(
        artifact=artifacts.base,
        alias__in=["approved", "latest"],
    )
    base_versions: dict[str, ArtifactVersion | None] = {"approved": None, "latest": None}
    for alias_obj in base_aliases:
        base_versions[alias_obj.alias] = alias_obj.version

    overrides_alias = artifacts.overrides.aliases.select_related("version").get(alias="active")
    overrides_active = overrides_alias.version if overrides_alias else None

    base_resolved, _base_alias = _resolve_driver_base_version(base_versions=base_versions)
    if base_resolved is None:
        record_driver_catalog_editor_error(driver, action="diff", code="BASE_CATALOG_MISSING")
        return Response({
            "success": False,
            "error": {"code": "BASE_CATALOG_MISSING", "message": "Base catalog is not imported yet"},
        }, status=400)

    try:
        base_catalog = load_catalog_json(base_resolved)
    except ArtifactStorageError as exc:
        record_driver_catalog_editor_error(driver, action="diff", code="STORAGE_ERROR")
        return Response(
            {"success": False, "error": {"code": "STORAGE_ERROR", "message": str(exc)}},
            status=500,
        )
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        record_driver_catalog_editor_error(driver, action="diff", code="CATALOG_INVALID")
        return Response(
            {"success": False, "error": {"code": "CATALOG_INVALID", "message": str(exc)}},
            status=500,
        )

    overrides_catalog = None
    if draft_overrides is not None:
        errors = _validate_overrides_catalog_v2(driver, draft_overrides)
        if errors:
            record_driver_catalog_editor_error(driver, action="diff", code="INVALID_CATALOG")
            return Response({
                "success": False,
                "error": {"code": "INVALID_CATALOG", "message": "Invalid overrides catalog", "details": errors},
            }, status=400)
        overrides_catalog = draft_overrides
    else:
        try:
            overrides_catalog = load_catalog_json(overrides_active) if overrides_active else {
                "catalog_version": 2,
                "driver": driver,
                "overrides": {"commands_by_id": {}},
            }
        except ArtifactStorageError as exc:
            record_driver_catalog_editor_error(driver, action="diff", code="STORAGE_ERROR")
            return Response(
                {"success": False, "error": {"code": "STORAGE_ERROR", "message": str(exc)}},
                status=500,
            )
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            record_driver_catalog_editor_error(driver, action="diff", code="CATALOG_INVALID")
            return Response(
                {"success": False, "error": {"code": "CATALOG_INVALID", "message": str(exc)}},
                status=500,
            )

    base_command = _get_commands_by_id(base_catalog).get(command_id)

    has_overrides = False
    overrides_patch = None
    if isinstance(overrides_catalog, dict):
        patch = overrides_catalog.get("overrides")
        if isinstance(patch, dict):
            commands_patch = patch.get("commands_by_id")
            if isinstance(commands_patch, dict):
                has_overrides = command_id in commands_patch
                overrides_patch = commands_patch.get(command_id)

    if not isinstance(base_command, dict) and not isinstance(overrides_patch, dict):
        record_driver_catalog_editor_error(driver, action="diff", code="COMMAND_NOT_FOUND")
        return Response({
            "success": False,
            "error": {"code": "COMMAND_NOT_FOUND", "message": f"Unknown command_id: {command_id}"},
        }, status=400)

    effective_command: dict = copy.deepcopy(base_command) if isinstance(base_command, dict) else {}
    if isinstance(overrides_patch, dict):
        _deep_merge_dict(effective_command, overrides_patch)

    changes: list[dict] = []
    _diff_values(
        base=base_command if isinstance(base_command, dict) else {},
        effective=effective_command,
        path=f"commands_by_id.{command_id}",
        out=changes,
    )

    return Response({
        "driver": driver,
        "command_id": command_id,
        "has_overrides": has_overrides,
        "changes": changes,
        "count": len(changes),
    })


@extend_schema(
    tags=["v2"],
    summary="List command schemas audit log entries",
    parameters=[
        OpenApiParameter(name="driver", type=str, required=False, description="Driver name (cli/ibcmd)"),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: CommandSchemasAuditListResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAdminUser])
def list_command_schemas_audit(request):
    denied = _ensure_manage_driver_catalogs(request, action="audit.list")
    if denied:
        return denied

    driver = (request.query_params.get("driver") or "").strip().lower()
    if driver and driver not in {"cli", "ibcmd"}:
        record_driver_catalog_editor_error("unknown", action="audit.list", code="UNKNOWN_DRIVER")
        return Response({
            "success": False,
            "error": {"code": "UNKNOWN_DRIVER", "message": f"Unknown driver: {driver}"},
        }, status=400)

    try:
        limit = int(request.query_params.get("limit") or 100)
        offset = int(request.query_params.get("offset") or 0)
    except (TypeError, ValueError):
        record_driver_catalog_editor_error(driver if driver else "all", action="audit.list", code="INVALID_PAGINATION")
        return Response({
            "success": False,
            "error": {"code": "INVALID_PAGINATION", "message": "limit/offset must be integers"},
        }, status=400)

    if limit < 1 or limit > 500 or offset < 0:
        record_driver_catalog_editor_error(driver if driver else "all", action="audit.list", code="INVALID_PAGINATION")
        return Response({
            "success": False,
            "error": {"code": "INVALID_PAGINATION", "message": "limit must be 1..500 and offset >= 0"},
        }, status=400)

    qs = AdminActionAuditLog.objects.select_related("actor").filter(
        target_type="driver_catalog",
        action__startswith="driver_catalog.",
    )
    if driver:
        qs = qs.filter(target_id=driver)

    total = qs.count()
    rows = list(qs.order_by("-created_at")[offset : offset + limit])

    items = [
        {
            "id": row.id,
            "created_at": row.created_at,
            "action": row.action,
            "outcome": row.outcome,
            "actor_username": row.actor_username,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "metadata": row.metadata or {},
            "error_message": row.error_message or "",
        }
        for row in rows
    ]

    return Response({"items": items, "count": len(items), "total": total})
