"""Command schemas preview endpoint."""

from __future__ import annotations

import copy
import json

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse


from .common import (
    CommandSchemasPreviewRequestSerializer,
    CommandSchemasPreviewResponseSerializer,
    ErrorResponseSerializer,
    ArtifactAlias,
    ArtifactStorageError,
    ArtifactVersion,
    build_ibcmd_cli_argv,
    build_ibcmd_cli_argv_manual,
    build_ibcmd_connection_args,
    detect_connection_option_conflicts,
    flatten_connection_params,
    get_or_create_catalog_artifacts,
    load_catalog_json,
    record_driver_catalog_editor_error,
    _ensure_manage_driver_catalogs,
)
from .helpers import (
    _build_command_argv,
    _deep_merge_dict,
    _get_commands_by_id,
    _resolve_driver_base_version,
    _validate_overrides_catalog_v2,
)

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
    connection = serializer.validated_data.get("connection") or {}
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
                "overrides": {"commands_by_id": {}, "driver_schema": {}},
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

    patch = overrides_catalog.get("overrides") if isinstance(overrides_catalog, dict) else None
    if isinstance(patch, dict):
        _deep_merge_dict(base_catalog, patch)

    effective_command = _get_commands_by_id(base_catalog).get(command_id)
    if not isinstance(effective_command, dict):
        record_driver_catalog_editor_error(driver, action="preview", code="COMMAND_NOT_FOUND")
        return Response({
            "success": False,
            "error": {"code": "COMMAND_NOT_FOUND", "message": f"Unknown command_id: {command_id}"},
        }, status=400)

    try:
        if driver == "ibcmd":
            connection_dict = dict(connection) if isinstance(connection, dict) else {}

            for token in additional_args:
                t = str(token or "").strip().lower()
                if (
                    t in {"--pid", "-p"}
                    or t.startswith("--pid=")
                    or t.startswith("-p=")
                    or t.startswith("-p ")
                    or (t.startswith("-p") and len(t) > 2 and t[2].isdigit())
                ):
                    raise ValueError("Use connection.pid instead of --pid in additional_args")

            for token in additional_args:
                t = str(token or "").strip().lower()
                if (
                    t in {"--request-db-pwd", "--request-database-password", "-w"}
                    or t.startswith("--request-db-pwd=")
                    or t.startswith("--request-database-password=")
                ):
                    raise ValueError(
                        "stdin flag --request-db-pwd (-W) is not allowed; DBMS credentials are resolved via DBMS user mapping"
                    )

            flattened_connection = flatten_connection_params(connection_dict) if connection_dict else {}
            if flattened_connection:
                conflicts = detect_connection_option_conflicts(
                    connection_params=flattened_connection,
                    additional_args=list(additional_args or []),
                )
                if conflicts:
                    conflict_list = ", ".join(sorted(set(conflicts)))
                    raise ValueError(f"duplicate driver-level options in additional_args: {conflict_list}")

                if isinstance(params, dict) and params:
                    overlap = [
                        key
                        for key in flattened_connection.keys()
                        if key in params and params.get(key) not in (None, "")
                    ]
                    if overlap:
                        overlap_list = ", ".join(sorted(set(str(k) for k in overlap)))
                        raise ValueError(f"driver-level options must be provided via connection (not params): {overlap_list}")

            pre_args = build_ibcmd_connection_args(
                driver_schema=base_catalog.get("driver_schema") if isinstance(base_catalog, dict) else None,
                connection=connection_dict,
            )
            builder = build_ibcmd_cli_argv if strict else build_ibcmd_cli_argv_manual
            argv, argv_masked = builder(
                command=copy.deepcopy(effective_command),
                params=params,
                additional_args=additional_args,
                pre_args=pre_args,
            )
        else:
            argv, argv_masked = _build_command_argv(
                command=copy.deepcopy(effective_command),
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

