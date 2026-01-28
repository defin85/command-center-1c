"""Command schemas validation endpoint."""

from __future__ import annotations

import json

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.operations.cli_catalog import validate_cli_catalog
from apps.operations.ibcmd_catalog_v2 import validate_catalog_v2 as validate_ibcmd_catalog_v2

from .common import (
    CommandSchemasValidateRequestSerializer,
    CommandSchemasValidateResponseSerializer,
    ErrorResponseSerializer,
    ArtifactAlias,
    ArtifactStorageError,
    ArtifactVersion,
    get_or_create_catalog_artifacts,
    load_catalog_json,
    record_driver_catalog_editor_error,
    record_driver_catalog_editor_validation_failed,
    _ensure_manage_driver_catalogs,
)
from .helpers import (
    _collect_command_param_issues,
    _collect_ibcmd_driver_schema_issues,
    _collect_params_by_name_issues,
    _deep_merge_dict,
    _get_commands_by_id,
    _issue,
    _resolve_driver_base_version,
    _validate_cli_catalog_v2,
    _validate_overrides_catalog_v2,
)

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
    draft_effective = serializer.validated_data.get("effective_catalog")

    if draft_overrides is not None and draft_effective is not None:
        record_driver_catalog_editor_error(driver, action="validate", code="INVALID_REQUEST")
        return Response({
            "success": False,
            "error": {"code": "INVALID_REQUEST", "message": "Provide catalog or effective_catalog, not both"},
        }, status=400)

    if draft_effective is not None:
        issues: list[dict] = []
        if driver == "ibcmd":
            for err in validate_ibcmd_catalog_v2(draft_effective):
                issues.append(_issue("error", "IBCMD_CATALOG_INVALID", err))
            issues.extend(_collect_ibcmd_driver_schema_issues(draft_effective))
            for cmd_id, cmd in _get_commands_by_id(draft_effective).items():
                if isinstance(cmd_id, str) and isinstance(cmd, dict):
                    issues.extend(_collect_command_param_issues(cmd_id, cmd))
        else:
            issues.extend(_validate_cli_catalog_v2(draft_effective))

        errors_count = sum(1 for item in issues if item.get("severity") == "error")
        warnings_count = sum(1 for item in issues if item.get("severity") == "warning")

        if errors_count:
            record_driver_catalog_editor_validation_failed(driver, stage="validate", kind="invalid_effective")

        return Response({
            "driver": driver,
            "ok": errors_count == 0,
            "base_version": None,
            "base_version_id": None,
            "overrides_version": None,
            "overrides_version_id": None,
            "issues": issues,
            "errors_count": errors_count,
            "warnings_count": warnings_count,
        })

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
                "overrides": {"commands_by_id": {}, "driver_schema": {}},
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
        issues.extend(_collect_ibcmd_driver_schema_issues(base_catalog))
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

