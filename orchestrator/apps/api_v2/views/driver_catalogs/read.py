"""Read-only command schemas endpoints."""

from __future__ import annotations

import json

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.operations.driver_catalog_effective import get_effective_driver_catalog
from apps.operations.prometheus_metrics import (
    record_driver_catalog_editor_error,
)

from .common import (
    ArtifactAlias,
    ArtifactStorageError,
    ArtifactVersion,
    CommandSchemasEditorViewResponseSerializer,
    CommandSchemasVersionsListResponseSerializer,
    COMMAND_SCHEMA_DRIVER_CHOICES,
    ErrorResponseSerializer,
    get_or_create_catalog_artifacts,
    load_catalog_json,
    _ensure_manage_driver_catalogs,
)
from .helpers import (
    _build_empty_catalog_v2,
    _compute_command_schemas_etag,
    _resolve_driver_base_version,
)

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
        ),
        OpenApiParameter(
            name="mode",
            type=str,
            required=False,
            description="Editor mode (guided/raw). In raw mode, base catalog is loaded from base alias latest.",
        ),
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
    if driver not in COMMAND_SCHEMA_DRIVER_CHOICES:
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

    etag = _compute_command_schemas_etag(
        driver=driver,
        base_versions=base_versions,
        overrides_version=overrides_active,
    )

    if request.headers.get("If-None-Match") == etag:
        response = Response(status=304)
        response["ETag"] = etag
        return response

    mode = str(request.query_params.get("mode") or "").strip().lower()
    display_base = base_resolved
    if mode == "raw":
        latest = base_versions.get("latest")
        if latest is not None:
            display_base = latest

    try:
        base_catalog = load_catalog_json(display_base) if display_base else _build_empty_catalog_v2(driver)
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
    if driver not in COMMAND_SCHEMA_DRIVER_CHOICES:
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

