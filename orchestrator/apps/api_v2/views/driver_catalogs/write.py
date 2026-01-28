"""Command schemas write endpoints (base/effective/import/promote)."""

from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.artifacts.models import ArtifactAlias, ArtifactVersion
from apps.operations.cli_catalog import build_cli_catalog_from_its, validate_cli_catalog
from apps.operations.driver_catalog_artifacts import (
    build_empty_overrides_catalog,
    get_or_create_catalog_artifacts,
    promote_base_alias,
    upload_base_catalog_version,
)
from apps.operations.ibcmd_catalog_v2 import build_base_catalog_from_its as build_ibcmd_catalog_v2_from_its
from apps.operations.ibcmd_catalog_v2 import validate_catalog_v2 as validate_ibcmd_catalog_v2
from apps.operations.driver_catalog_v2 import cli_catalog_v1_to_v2
from apps.operations.prometheus_metrics import (
    record_driver_catalog_editor_conflict,
    record_driver_catalog_editor_validation_failed,
)
from apps.operations.services.admin_action_audit import log_admin_action

from .common import (
    COMMAND_SCHEMA_DRIVERS,
    CommandSchemasBaseUpdateRequestSerializer,
    CommandSchemasBaseUpdateResponseSerializer,
    CommandSchemasEffectiveUpdateRequestSerializer,
    CommandSchemasEffectiveUpdateResponseSerializer,
    CommandSchemasImportRequestSerializer,
    CommandSchemasImportResponseSerializer,
    CommandSchemasPromoteRequestSerializer,
    CommandSchemasPromoteResponseSerializer,
    ErrorResponseSerializer,
    _ensure_manage_driver_catalogs,
)
from .helpers import (
    _collect_command_param_issues,
    _compute_command_schemas_etag,
    _invalidate_driver_catalog_cache,
    _get_commands_by_id,
    _issue,
    _extract_expected_etag,
    _record_driver_catalog_editor_error,
    _resolve_driver_base_version,
    _upload_overrides_catalog_version,
    _validate_cli_catalog_v2,
    _collect_ibcmd_driver_schema_issues,
)

@extend_schema(
    tags=["v2"],
    summary="Import ITS command schemas (v2)",
    description=(
        "Parse ITS JSON into driver command schema catalog and optionally save (staff-only).\n\n"
        "driver=cli: uploads v2 base catalog artifact.\n"
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
        _record_driver_catalog_editor_error("unknown", action="import_its", code="INVALID_REQUEST")
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
        legacy_catalog = build_cli_catalog_from_its(its_payload)
        errors = validate_cli_catalog(legacy_catalog)
        if errors:
            record_driver_catalog_editor_validation_failed(driver, stage="import_its", kind="invalid_parsed")
            _record_driver_catalog_editor_error(driver, action="import_its", code="INVALID_CATALOG")
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

        base_catalog = cli_catalog_v1_to_v2(legacy_catalog)
        validation_issues = _validate_cli_catalog_v2(base_catalog)
        if any(item.get("severity") == "error" for item in validation_issues):
            record_driver_catalog_editor_validation_failed(driver, stage="import_its", kind="invalid_base")
            _record_driver_catalog_editor_error(driver, action="import_its", code="INVALID_CATALOG")
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
                "error": {
                    "code": "INVALID_CATALOG",
                    "message": "Parsed CLI base catalog is invalid",
                    "details": validation_issues,
                },
            }, status=400)
        if serializer.validated_data.get("save", True):
            try:
                version_obj = upload_base_catalog_version(
                    driver="cli",
                    catalog=base_catalog,
                    created_by=request.user,
                    metadata_extra={"reason": reason},
                )
                artifacts = get_or_create_catalog_artifacts("cli", created_by=request.user)
                if not ArtifactAlias.objects.filter(artifact=artifacts.base, alias="approved").exists():
                    promote_base_alias("cli", version=str(version_obj.version), alias="approved")
                _invalidate_driver_catalog_cache("cli")
            except Exception as exc:
                _record_driver_catalog_editor_error(driver, action="import_its", code="IMPORT_FAILED")
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
        base_catalog = build_ibcmd_catalog_v2_from_its(its_payload)
        errors = validate_ibcmd_catalog_v2(base_catalog)
        if errors:
            record_driver_catalog_editor_validation_failed(driver, stage="import_its", kind="invalid_parsed")
            _record_driver_catalog_editor_error(driver, action="import_its", code="INVALID_CATALOG")
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
                version_obj = upload_base_catalog_version(
                    driver="ibcmd",
                    catalog=base_catalog,
                    created_by=request.user,
                    metadata_extra={"reason": reason},
                )
                artifacts = get_or_create_catalog_artifacts("ibcmd", created_by=request.user)
                if not ArtifactAlias.objects.filter(artifact=artifacts.base, alias="approved").exists():
                    promote_base_alias("ibcmd", version=str(version_obj.version), alias="approved")
                _invalidate_driver_catalog_cache("ibcmd")
            except Exception as exc:
                _record_driver_catalog_editor_error(driver, action="import_its", code="IMPORT_FAILED")
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
            "version": base_catalog.get("platform_version") if isinstance(base_catalog, dict) else None,
            "reason": reason,
        },
    )
    return Response({"driver": driver, "catalog": base_catalog})


@extend_schema(
    tags=["v2"],
    summary="Update command schemas base (v2)",
    description=(
        "Upload new base catalog version (v2) and move base alias latest only (approved is not touched) "
        "(staff-only). Requires reason.\n\n"
        "Supports optimistic concurrency via If-Match header or expected_etag in request body."
    ),
    request=CommandSchemasBaseUpdateRequestSerializer,
    responses={
        200: CommandSchemasBaseUpdateResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        409: OpenApiResponse(description="Conflict"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def update_command_schemas_base(request):
    denied = _ensure_manage_driver_catalogs(request, action="base.update")
    if denied:
        return denied

    serializer = CommandSchemasBaseUpdateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        _record_driver_catalog_editor_error("unknown", action="base.update", code="INVALID_REQUEST")
        log_admin_action(
            request,
            action="driver_catalog.base.update",
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

    if not COMMAND_SCHEMA_DRIVERS.get(driver, {}).get("supports_raw_base_edit"):
        _record_driver_catalog_editor_error(driver, action="base.update", code="UNSUPPORTED_DRIVER")
        return Response({
            "success": False,
            "error": {"code": "UNSUPPORTED_DRIVER", "message": f"Raw base edit is not supported for {driver}"},
        }, status=400)

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
        record_driver_catalog_editor_conflict(driver, action="base.update")
        _record_driver_catalog_editor_error(driver, action="base.update", code="CONFLICT")
        log_admin_action(
            request,
            action="driver_catalog.base.update",
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
                    "message": "Base catalog changed since you opened the editor.",
                    "details": {"expected_etag": expected_etag, "current_etag": current_etag},
                },
            },
            status=409,
        )
        response["ETag"] = current_etag
        return response

    validation_issues: list[dict] = []
    if driver == "ibcmd":
        for err in validate_ibcmd_catalog_v2(catalog):
            validation_issues.append(_issue("error", "IBCMD_CATALOG_INVALID", err))
        for cmd_id, cmd in _get_commands_by_id(catalog).items():
            if isinstance(cmd_id, str) and isinstance(cmd, dict):
                validation_issues.extend(_collect_command_param_issues(cmd_id, cmd))
    else:
        validation_issues.extend(_validate_cli_catalog_v2(catalog))

    if any(item.get("severity") == "error" for item in validation_issues):
        record_driver_catalog_editor_validation_failed(driver, stage="base.update", kind="invalid_base")
        _record_driver_catalog_editor_error(driver, action="base.update", code="INVALID_CATALOG")
        log_admin_action(
            request,
            action="driver_catalog.base.update",
            outcome="error",
            target_type="driver_catalog",
            target_id=driver,
            metadata={"error": "INVALID_CATALOG", "driver": driver, "reason": reason},
            error_message="INVALID_CATALOG",
        )
        return Response({
            "success": False,
            "error": {
                "code": "INVALID_CATALOG",
                "message": "Invalid base catalog",
                "details": validation_issues,
            },
        }, status=400)

    try:
        version_obj = upload_base_catalog_version(
            driver=driver,
            catalog=catalog,
            created_by=request.user,
            metadata_extra={"reason": reason},
        )
        _invalidate_driver_catalog_cache(driver)
    except Exception as exc:
        _record_driver_catalog_editor_error(driver, action="base.update", code="SAVE_FAILED")
        log_admin_action(
            request,
            action="driver_catalog.base.update",
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

    base_versions_after = dict(base_versions)
    base_versions_after["latest"] = version_obj
    new_etag = _compute_command_schemas_etag(
        driver=driver,
        base_versions=base_versions_after,
        overrides_version=overrides_active,
    )

    log_admin_action(
        request,
        action="driver_catalog.base.update",
        outcome="success",
        target_type="driver_catalog",
        target_id=driver,
        metadata={"driver": driver, "version": version_obj.version, "reason": reason},
    )
    response = Response({"driver": driver, "base_version": str(version_obj.version), "etag": new_etag})
    response["ETag"] = new_etag
    response["Cache-Control"] = "private, max-age=0"
    return response


@extend_schema(
    tags=["v2"],
    summary="Update command schemas effective (v2)",
    description=(
        "DANGEROUS: Replace effective catalog by uploading it as a new base version and resetting overrides "
        "(staff-only). Requires reason.\n\n"
        "Supports optimistic concurrency via If-Match header or expected_etag in request body."
    ),
    request=CommandSchemasEffectiveUpdateRequestSerializer,
    responses={
        200: CommandSchemasEffectiveUpdateResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        409: OpenApiResponse(description="Conflict"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def update_command_schemas_effective(request):
    denied = _ensure_manage_driver_catalogs(request, action="effective.update")
    if denied:
        return denied

    serializer = CommandSchemasEffectiveUpdateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        _record_driver_catalog_editor_error("unknown", action="effective.update", code="INVALID_REQUEST")
        log_admin_action(
            request,
            action="driver_catalog.effective.update",
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

    if not COMMAND_SCHEMA_DRIVERS.get(driver, {}).get("supports_raw_effective_edit"):
        _record_driver_catalog_editor_error(driver, action="effective.update", code="UNSUPPORTED_DRIVER")
        return Response({
            "success": False,
            "error": {"code": "UNSUPPORTED_DRIVER", "message": f"Raw effective edit is not supported for {driver}"},
        }, status=400)

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
        record_driver_catalog_editor_conflict(driver, action="effective.update")
        _record_driver_catalog_editor_error(driver, action="effective.update", code="CONFLICT")
        log_admin_action(
            request,
            action="driver_catalog.effective.update",
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
                    "message": "Effective catalog changed since you opened the editor.",
                    "details": {"expected_etag": expected_etag, "current_etag": current_etag},
                },
            },
            status=409,
        )
        response["ETag"] = current_etag
        return response

    validation_issues: list[dict] = []
    if driver == "ibcmd":
        for err in validate_ibcmd_catalog_v2(catalog):
            validation_issues.append(_issue("error", "IBCMD_CATALOG_INVALID", err))
        for cmd_id, cmd in _get_commands_by_id(catalog).items():
            if isinstance(cmd_id, str) and isinstance(cmd, dict):
                validation_issues.extend(_collect_command_param_issues(cmd_id, cmd))
    else:
        validation_issues.extend(_validate_cli_catalog_v2(catalog))

    if any(item.get("severity") == "error" for item in validation_issues):
        record_driver_catalog_editor_validation_failed(driver, stage="effective.update", kind="invalid_effective")
        _record_driver_catalog_editor_error(driver, action="effective.update", code="INVALID_CATALOG")
        log_admin_action(
            request,
            action="driver_catalog.effective.update",
            outcome="error",
            target_type="driver_catalog",
            target_id=driver,
            metadata={"error": "INVALID_CATALOG", "driver": driver, "reason": reason},
            error_message="INVALID_CATALOG",
        )
        return Response({
            "success": False,
            "error": {
                "code": "INVALID_CATALOG",
                "message": "Invalid effective catalog",
                "details": validation_issues,
            },
        }, status=400)

    try:
        base_version_obj = upload_base_catalog_version(
            driver=driver,
            catalog=catalog,
            created_by=request.user,
            metadata_extra={"reason": reason, "dangerous_effective_update": True},
        )
        promote_base_alias(driver, version=str(base_version_obj.version), alias="approved")

        empty_overrides = build_empty_overrides_catalog(driver)
        overrides_version_obj = _upload_overrides_catalog_version(
            driver=driver,
            catalog=empty_overrides,
            created_by=request.user,
            metadata_extra={"reason": reason, "reset": True},
        )

        _invalidate_driver_catalog_cache(driver)
    except Exception as exc:
        _record_driver_catalog_editor_error(driver, action="effective.update", code="SAVE_FAILED")
        log_admin_action(
            request,
            action="driver_catalog.effective.update",
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

    base_versions_after: dict[str, ArtifactVersion | None] = {
        "approved": base_version_obj,
        "latest": base_version_obj,
    }
    new_etag = _compute_command_schemas_etag(
        driver=driver,
        base_versions=base_versions_after,
        overrides_version=overrides_version_obj,
    )

    log_admin_action(
        request,
        action="driver_catalog.effective.update",
        outcome="success",
        target_type="driver_catalog",
        target_id=driver,
        metadata={
            "driver": driver,
            "base_version": base_version_obj.version,
            "overrides_version": overrides_version_obj.version if overrides_version_obj else None,
            "reason": reason,
        },
    )
    response = Response({
        "driver": driver,
        "base_version": str(base_version_obj.version),
        "overrides_version": str(overrides_version_obj.version) if overrides_version_obj else None,
        "etag": new_etag,
    })
    response["ETag"] = new_etag
    response["Cache-Control"] = "private, max-age=0"
    return response


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
        _record_driver_catalog_editor_error("unknown", action="promote", code="INVALID_REQUEST")
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
        _record_driver_catalog_editor_error(driver, action="promote", code="INVALID_ALIAS")
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
        _record_driver_catalog_editor_error(driver, action="promote", code="PROMOTE_FAILED")
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

    _invalidate_driver_catalog_cache(driver)
    log_admin_action(
        request,
        action="driver_catalog.promote",
        outcome="success",
        target_type="driver_catalog",
        target_id=driver,
        metadata={"driver": driver, "alias": alias, "version": version, "reason": reason},
    )
    return Response({"driver": driver, "alias": alias, "version": version})
