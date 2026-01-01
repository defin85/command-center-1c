"""
Driver catalog management endpoints (staff-only).

Supports:
- list/get/update driver catalogs (file-backed)
- import ITS JSON to CLI catalog
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
from apps.operations.services.admin_action_audit import log_admin_action
from apps.api_v2.serializers.common import ErrorResponseSerializer

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


class DriverCatalogImportRequestSerializer(serializers.Serializer):
    driver = serializers.CharField(default="cli")
    its_payload = serializers.DictField()
    save = serializers.BooleanField(default=True)


class DriverCatalogImportResponseSerializer(serializers.Serializer):
    driver = serializers.CharField()
    catalog = serializers.DictField()


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
    description="Update driver catalog file (staff-only).",
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
    else:
        _save_catalog(_catalog_path(DRIVER_CATALOGS[driver]["path"]), catalog)
    log_admin_action(
        user=request.user,
        action="driver_catalog.update",
        details={"driver": driver},
    )
    return Response({"driver": driver, "catalog": catalog})


@extend_schema(
    tags=["v2"],
    summary="Import ITS catalog for CLI",
    description="Parse ITS JSON into CLI command catalog and optionally save (staff-only).",
    request=DriverCatalogImportRequestSerializer,
    responses={
        200: DriverCatalogImportResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def import_its_cli_catalog(request):
    serializer = DriverCatalogImportRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            "success": False,
            "error": {"code": "INVALID_REQUEST", "message": "Invalid request", "details": serializer.errors},
        }, status=400)
    driver = serializer.validated_data["driver"]
    if driver != "cli":
        return Response({
            "success": False,
            "error": {"code": "UNSUPPORTED_DRIVER", "message": "Only cli driver supports ITS import"},
        }, status=400)
    its_payload = serializer.validated_data["its_payload"]
    catalog = build_cli_catalog_from_its(its_payload)
    errors = validate_cli_catalog(catalog)
    if errors:
        return Response({
            "success": False,
            "error": {"code": "INVALID_CATALOG", "message": "Parsed CLI catalog is invalid", "details": errors},
        }, status=400)
    if serializer.validated_data.get("save", True):
        save_cli_command_catalog(catalog)
    log_admin_action(
        user=request.user,
        action="driver_catalog.import_its",
        details={"driver": driver, "version": catalog.get("version")},
    )
    return Response({"driver": driver, "catalog": catalog})
