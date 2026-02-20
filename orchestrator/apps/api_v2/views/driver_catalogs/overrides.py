"""Command schemas overrides endpoints."""

from __future__ import annotations

import copy
import json

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.operations.ibcmd_catalog_v2 import validate_catalog_v2 as validate_ibcmd_catalog_v2
from apps.operations.services.admin_action_audit import log_admin_action
from apps.operations.prometheus_metrics import (
    record_driver_catalog_editor_conflict,
    record_driver_catalog_editor_validation_failed,
)

from .common import (
    ArtifactAlias,
    ArtifactStorageError,
    ArtifactVersion,
    CommandSchemasOverridesRollbackRequestSerializer,
    CommandSchemasOverridesRollbackResponseSerializer,
    CommandSchemasOverridesUpdateRequestSerializer,
    CommandSchemasOverridesUpdateResponseSerializer,
    ErrorResponseSerializer,
    get_or_create_catalog_artifacts,
    load_catalog_json,
    _ensure_manage_driver_catalogs,
)
from .helpers import (
    _build_empty_catalog_v2,
    _collect_command_param_issues,
    _collect_ibcmd_driver_schema_issues,
    _compute_command_schemas_etag,
    _deep_merge_dict,
    _extract_expected_etag,
    _get_commands_by_id,
    _invalidate_driver_catalog_cache,
    _issue,
    _record_driver_catalog_editor_error,
    _resolve_driver_base_version,
    _upload_overrides_catalog_version,
    _validate_cli_catalog_v2,
    _validate_overrides_catalog_v2,
)

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
        _record_driver_catalog_editor_error("unknown", action="overrides.update", code="INVALID_REQUEST")
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

    current_etag = _compute_command_schemas_etag(
        driver=driver,
        base_versions=base_versions,
        overrides_version=overrides_active,
    )
    if expected_etag is not None and expected_etag != current_etag:
        record_driver_catalog_editor_conflict(driver, action="overrides.update")
        _record_driver_catalog_editor_error(driver, action="overrides.update", code="CONFLICT")
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
        _record_driver_catalog_editor_error(driver, action="overrides.update", code="INVALID_CATALOG")
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
        _record_driver_catalog_editor_error(driver, action="overrides.update", code="BASE_CATALOG_MISSING")
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
            _record_driver_catalog_editor_error(driver, action="overrides.update", code="CATALOG_INVALID")
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
            validation_issues: list[dict] = []
            for err in validate_ibcmd_catalog_v2(effective):
                validation_issues.append(_issue("error", "IBCMD_CATALOG_INVALID", err))
            validation_issues.extend(_collect_ibcmd_driver_schema_issues(effective))
            for cmd_id, cmd in _get_commands_by_id(effective).items():
                if isinstance(cmd_id, str) and isinstance(cmd, dict):
                    validation_issues.extend(_collect_command_param_issues(cmd_id, cmd))

            if any(item.get("severity") == "error" for item in validation_issues):
                record_driver_catalog_editor_validation_failed(driver, stage="overrides.update", kind="invalid_effective")
                _record_driver_catalog_editor_error(driver, action="overrides.update", code="INVALID_EFFECTIVE_CATALOG")
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

    if driver == "cli":
        try:
            cli_base_catalog = load_catalog_json(base_resolved) if base_resolved else _build_empty_catalog_v2(driver)
        except (ArtifactStorageError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            _record_driver_catalog_editor_error(driver, action="overrides.update", code="CATALOG_INVALID")
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
            _record_driver_catalog_editor_error(driver, action="overrides.update", code="INVALID_EFFECTIVE_CATALOG")
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
        version_obj = _upload_overrides_catalog_version(
            driver=driver,
            catalog=catalog,
            created_by=request.user,
            metadata_extra={"reason": reason},
        )
        _invalidate_driver_catalog_cache(driver)
    except Exception as exc:
        _record_driver_catalog_editor_error(driver, action="overrides.update", code="SAVE_FAILED")
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

    new_etag = _compute_command_schemas_etag(
        driver=driver,
        base_versions=base_versions,
        overrides_version=version_obj,
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
        _record_driver_catalog_editor_error("unknown", action="overrides.rollback", code="INVALID_REQUEST")
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

    current_etag = _compute_command_schemas_etag(
        driver=driver,
        base_versions=base_versions,
        overrides_version=overrides_active,
    )
    if expected_etag is not None and expected_etag != current_etag:
        record_driver_catalog_editor_conflict(driver, action="overrides.rollback")
        _record_driver_catalog_editor_error(driver, action="overrides.rollback", code="CONFLICT")
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
        _record_driver_catalog_editor_error(driver, action="overrides.rollback", code="VERSION_NOT_FOUND")
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

        _invalidate_driver_catalog_cache(driver)

        new_etag = _compute_command_schemas_etag(
            driver=driver,
            base_versions=base_versions,
            overrides_version=target_version,
        )
    except Exception as exc:
        _record_driver_catalog_editor_error(driver, action="overrides.rollback", code="ROLLBACK_FAILED")
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
