"""Operations endpoints: driver command shortcuts."""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.operations.driver_catalog_effective import (
    filter_catalog_for_user,
    get_effective_driver_catalog,
    resolve_driver_catalog_versions,
)
from apps.operations.models import DriverCommandShortcut

from .schemas import (
    CreateDriverCommandShortcutRequestSerializer,
    DeleteDriverCommandShortcutRequestSerializer,
    DriverCommandShortcutSerializer,
    ListDriverCommandShortcutsResponseSerializer,
    OperationErrorResponseSerializer,
)

@extend_schema(
    tags=["v2"],
    summary="List driver command shortcuts",
    description="List current user's saved command shortcuts (per driver).",
    parameters=[
        OpenApiParameter(
            name="driver",
            type=str,
            required=False,
            description="Driver name (currently: ibcmd).",
        ),
    ],
    responses={
        200: ListDriverCommandShortcutsResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_driver_command_shortcuts(request):
    driver = str(request.query_params.get("driver") or "ibcmd").strip().lower()
    if driver != "ibcmd":
        return Response(
            {"success": False, "error": {"code": "INVALID_DRIVER", "message": "Only driver=ibcmd is supported"}},
            status=400,
        )

    qs = DriverCommandShortcut.objects.filter(user=request.user, driver=driver).order_by("title", "created_at")

    resolved = resolve_driver_catalog_versions(driver)
    if resolved.base_version is not None:
        try:
            effective = get_effective_driver_catalog(
                driver=driver,
                base_version=resolved.base_version,
                overrides_version=resolved.overrides_version,
            )
            catalog = filter_catalog_for_user(request.user, effective.catalog)
            commands_by_id = catalog.get("commands_by_id") if isinstance(catalog, dict) else None
            if isinstance(commands_by_id, dict) and commands_by_id:
                qs = qs.filter(command_id__in=list(commands_by_id.keys()))
        except Exception:
            pass
    items = []
    for row in qs:
        items.append(
            {
                "id": row.id,
                "driver": row.driver,
                "command_id": row.command_id,
                "title": row.title,
                "payload": row.payload or {},
                "catalog_base_version": row.catalog_base_version or "",
                "catalog_overrides_version": row.catalog_overrides_version or "",
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
        )

    return Response({"items": items, "count": len(items)})


@extend_schema(
    tags=["v2"],
    summary="Create driver command shortcut",
    description="Create a per-user shortcut to a schema-driven driver command (command_id).",
    request=CreateDriverCommandShortcutRequestSerializer,
    responses={
        201: DriverCommandShortcutSerializer,
        400: OperationErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_driver_command_shortcut(request):
    def _sanitize_shortcut_payload(value):
        if not isinstance(value, dict):
            return {}

        def sanitize_config(cfg):
            if not isinstance(cfg, dict):
                return {}
            out = dict(cfg)
            # Do not store stdin in shortcuts by default.
            out.pop("stdin", None)

            connection = out.get("connection")
            if isinstance(connection, dict):
                offline = connection.get("offline")
                if isinstance(offline, dict):
                    next_offline = dict(offline)
                    next_offline.pop("db_user", None)
                    next_offline.pop("db_pwd", None)
                    next_offline.pop("db_password", None)
                    next_connection = dict(connection)
                    next_connection["offline"] = next_offline
                    out["connection"] = next_connection

            ib_auth = out.get("ib_auth")
            if isinstance(ib_auth, dict):
                next_ib_auth = dict(ib_auth)
                next_ib_auth.pop("user", None)
                next_ib_auth.pop("password", None)
                out["ib_auth"] = next_ib_auth

            return out

        # Support both payload formats:
        # - {"mode": "...", "connection": {...}, ...}
        # - {"version": 1, "config": {...}}
        if isinstance(value.get("config"), dict):
            out = dict(value)
            out["config"] = sanitize_config(out["config"])
            return out
        return sanitize_config(value)

    serializer = CreateDriverCommandShortcutRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    driver = str(serializer.validated_data["driver"] or "").strip().lower()
    command_id = str(serializer.validated_data["command_id"] or "").strip()
    title = str(serializer.validated_data["title"] or "").strip()
    payload = _sanitize_shortcut_payload(serializer.validated_data.get("payload"))

    if not command_id:
        return Response(
            {"success": False, "error": {"code": "MISSING_COMMAND_ID", "message": "command_id is required"}},
            status=400,
        )
    if not title:
        return Response(
            {"success": False, "error": {"code": "MISSING_TITLE", "message": "title is required"}},
            status=400,
        )

    resolved = resolve_driver_catalog_versions(driver)
    if resolved.base_version is None:
        return Response(
            {"success": False, "error": {"code": "CATALOG_NOT_AVAILABLE", "message": f"{driver} catalog is not imported yet"}},
            status=400,
        )

    effective = get_effective_driver_catalog(
        driver=driver,
        base_version=resolved.base_version,
        overrides_version=resolved.overrides_version,
    )
    catalog = filter_catalog_for_user(request.user, effective.catalog)
    commands_by_id = catalog.get("commands_by_id") if isinstance(catalog, dict) else None
    if not isinstance(commands_by_id, dict):
        return Response(
            {"success": False, "error": {"code": "CATALOG_INVALID", "message": f"{driver} catalog is invalid"}},
            status=500,
        )

    cmd = commands_by_id.get(command_id)
    if not isinstance(cmd, dict) or cmd.get("disabled") is True:
        return Response(
            {"success": False, "error": {"code": "UNKNOWN_COMMAND", "message": f"Unknown command_id: {command_id}"}},
            status=400,
        )

    shortcut = DriverCommandShortcut.objects.create(
        user=request.user,
        driver=driver,
        command_id=command_id,
        title=title,
        payload=payload,
        catalog_base_version=str(resolved.base_version or ""),
        catalog_overrides_version=str(resolved.overrides_version or "") if resolved.overrides_version else "",
    )

    return Response(
        {
            "id": shortcut.id,
            "driver": shortcut.driver,
            "command_id": shortcut.command_id,
            "title": shortcut.title,
            "payload": shortcut.payload or {},
            "catalog_base_version": shortcut.catalog_base_version or "",
            "catalog_overrides_version": shortcut.catalog_overrides_version or "",
            "created_at": shortcut.created_at,
            "updated_at": shortcut.updated_at,
        },
        status=201,
    )


@extend_schema(
    tags=["v2"],
    summary="Delete driver command shortcut",
    description="Delete a per-user command shortcut by id.",
    request=DeleteDriverCommandShortcutRequestSerializer,
    responses={
        200: OpenApiResponse(description="OK"),
        400: OperationErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        404: OperationErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def delete_driver_command_shortcut(request):
    serializer = DeleteDriverCommandShortcutRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    shortcut_id = serializer.validated_data["shortcut_id"]
    qs = DriverCommandShortcut.objects.filter(id=shortcut_id, user=request.user)
    if not qs.exists():
        return Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Shortcut not found"}},
            status=404,
        )

    qs.delete()
    return Response({"success": True, "deleted": True})


