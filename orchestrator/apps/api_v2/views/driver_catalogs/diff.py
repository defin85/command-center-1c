"""Command schemas diff endpoint."""

from __future__ import annotations

import copy
import json

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse


from .common import (
    CommandSchemasDiffRequestSerializer,
    CommandSchemasDiffResponseSerializer,
    ErrorResponseSerializer,
    ArtifactAlias,
    ArtifactStorageError,
    ArtifactVersion,
    get_or_create_catalog_artifacts,
    load_catalog_json,
    record_driver_catalog_editor_error,
    _ensure_manage_driver_catalogs,
)
from .helpers import (
    _deep_merge_dict,
    _diff_values,
    _get_commands_by_id,
    _resolve_driver_base_version,
    _validate_overrides_catalog_v2,
)

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


