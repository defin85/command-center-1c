"""
Driver catalog management endpoints (staff-only).

Supports:
- list/get/update driver catalogs (file-backed)
- import ITS JSON to CLI catalog (and publish v2 base artifact)
- import ITS JSON to IBCMD catalog v2 base artifact
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from django.conf import settings
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

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
from apps.operations.driver_catalog_effective import invalidate_driver_catalog_cache, load_catalog_json
from apps.operations.services.admin_action_audit import log_admin_action
from apps.api_v2.serializers.common import ErrorResponseSerializer
from apps.artifacts.storage import ArtifactStorageError

logger = logging.getLogger(__name__)


DRIVER_CATALOGS = {
    "cli": {"path": "config/cli_commands.json", "kind": "cli"},
    "ras": {"path": "config/driver_catalogs/ras.json", "kind": "generic"},
    "odata": {"path": "config/driver_catalogs/odata.json", "kind": "generic"},
    "ibcmd": {"path": "config/driver_catalogs/ibcmd.json", "kind": "generic"},
}


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


def _resolve_catalog(driver: str) -> dict:
    if driver == "cli":
        return load_cli_command_catalog()
    cfg = DRIVER_CATALOGS.get(driver)
    if not cfg:
        return {}
    return _load_catalog(_catalog_path(cfg["path"]))


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
    driver = str(request.query_params.get("driver") or "").strip()
    if not driver:
        return Response({
            "success": False,
            "error": {"code": "MISSING_DRIVER", "message": "driver is required"},
        }, status=400)
    if driver not in DRIVER_CATALOGS:
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
    serializer = DriverCatalogUpdateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            "success": False,
            "error": {"code": "INVALID_REQUEST", "message": "Invalid request", "details": serializer.errors},
        }, status=400)
    driver = serializer.validated_data["driver"]
    catalog = serializer.validated_data["catalog"]
    reason = serializer.validated_data["reason"]
    if driver not in DRIVER_CATALOGS:
        return Response({
            "success": False,
            "error": {"code": "UNKNOWN_DRIVER", "message": f"Unknown driver: {driver}"},
        }, status=400)
    if driver == "cli":
        errors = validate_cli_catalog(catalog)
        if errors:
            return Response({
                "success": False,
                "error": {"code": "INVALID_CATALOG", "message": "Invalid CLI catalog", "details": errors},
            }, status=400)
        save_cli_command_catalog(catalog)
        upload_base_catalog_version(driver="cli", catalog=cli_catalog_v1_to_v2(catalog), created_by=request.user)
        invalidate_driver_catalog_cache("cli")
    else:
        _save_catalog(_catalog_path(DRIVER_CATALOGS[driver]["path"]), catalog)
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
    serializer = DriverCatalogImportRequestSerializer(data=request.data)
    if not serializer.is_valid():
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
            return Response({
                "success": False,
                "error": {"code": "INVALID_CATALOG", "message": "Parsed CLI catalog is invalid", "details": errors},
            }, status=400)
        if serializer.validated_data.get("save", True):
            save_cli_command_catalog(catalog)
            upload_base_catalog_version(driver="cli", catalog=cli_catalog_v1_to_v2(catalog), created_by=request.user)
            invalidate_driver_catalog_cache("cli")
    else:
        catalog = build_ibcmd_catalog_v2_from_its(its_payload)
        errors = validate_ibcmd_catalog_v2(catalog)
        if errors:
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
            upload_base_catalog_version(driver="ibcmd", catalog=catalog, created_by=request.user)
            invalidate_driver_catalog_cache("ibcmd")

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
    driver = str(request.query_params.get("driver") or "").strip().lower()
    if not driver:
        return Response({
            "success": False,
            "error": {"code": "MISSING_DRIVER", "message": "driver is required"},
        }, status=400)
    if driver not in {"cli", "ibcmd"}:
        return Response({
            "success": False,
            "error": {"code": "UNKNOWN_DRIVER", "message": f"Unknown driver: {driver}"},
        }, status=400)

    artifacts = get_or_create_catalog_artifacts(driver, created_by=request.user)
    alias_obj = artifacts.overrides.aliases.select_related("version").get(alias="active")
    try:
        catalog = load_catalog_json(alias_obj.version)
    except ArtifactStorageError as exc:
        return Response(
            {"success": False, "error": {"code": "STORAGE_ERROR", "message": str(exc)}},
            status=500,
        )
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
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
    serializer = DriverCatalogOverridesUpdateRequestSerializer(data=request.data)
    if not serializer.is_valid():
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
        log_admin_action(
            request,
            action="driver_catalog.overrides.update",
            outcome="error",
            target_type="driver_catalog",
            target_id=driver,
            metadata={"error": "INVALID_CATALOG", "driver": driver},
            error_message="INVALID_CATALOG",
        )
        return Response({
            "success": False,
            "error": {"code": "INVALID_CATALOG", "message": "Invalid overrides catalog", "details": errors},
        }, status=400)

    version_obj = upload_overrides_catalog_version(driver=driver, catalog=catalog, created_by=request.user)
    invalidate_driver_catalog_cache(driver)
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
    serializer = DriverCatalogPromoteRequestSerializer(data=request.data)
    if not serializer.is_valid():
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
        return Response({
            "success": False,
            "error": {"code": "INVALID_ALIAS", "message": f"Unsupported alias: {alias}"},
        }, status=400)

    try:
        promote_base_alias(driver, version=version, alias=alias)
    except Exception as exc:
        log_admin_action(
            request,
            action="driver_catalog.promote",
            outcome="error",
            target_type="driver_catalog",
            target_id=driver,
            metadata={"error": "PROMOTE_FAILED", "driver": driver, "alias": alias, "version": version},
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
