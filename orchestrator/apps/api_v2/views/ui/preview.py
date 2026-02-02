"""Execution plan preview endpoint."""

from __future__ import annotations

import uuid
from typing import Any

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework import status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.api_v2.serializers.common import ErrorResponseSerializer
from apps.api_v2.serializers.common import ExecutionPlanWithBindingsSerializer
from apps.core import permission_codes as perms
from apps.operations.ibcmd_cli_builder import (
    build_ibcmd_cli_argv,
    build_ibcmd_cli_argv_manual,
    build_ibcmd_connection_args,
    detect_connection_option_conflicts,
    flatten_connection_params,
)
from apps.operations.driver_catalog_effective import (
    filter_catalog_for_user,
    get_effective_driver_catalog,
    resolve_driver_catalog_versions,
)
from apps.templates.workflow.models import WorkflowTemplate

from .common import UiErrorResponseSerializer, _is_sensitive_key, _mask_json_dict


class ExecutionPlanPreviewRequestSerializer(serializers.Serializer):
    executor = serializers.DictField()
    connection = serializers.DictField(required=False)
    database_ids = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True
    )

def _normalize_ibcmd_connection_profile(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    mode = str(raw.get("mode") or "").strip().lower() or "auto"
    if mode not in {"auto", "remote", "offline"}:
        mode = "auto"
    remote_url = str(raw.get("remote_url") or "").strip()
    offline_in = raw.get("offline")
    offline: dict[str, str] | None = None
    if isinstance(offline_in, dict):
        offline = {str(k): str(v).strip() for k, v in offline_in.items() if v not in (None, "")}
        offline.pop("db_user", None)
        offline.pop("db_pwd", None)
        offline.pop("db_password", None)
        if not offline:
            offline = None
    out: dict[str, Any] = {"mode": mode}
    if remote_url:
        out["remote_url"] = remote_url
    if offline:
        out["offline"] = offline
    return out

def _resolve_effective_ibcmd_connection_profile(profile: dict[str, Any] | None) -> tuple[str | None, dict[str, Any]]:
    if not isinstance(profile, dict):
        return None, {}
    mode = str(profile.get("mode") or "").strip().lower() or "auto"
    if mode not in {"auto", "remote", "offline"}:
        mode = "auto"
    remote_url = str(profile.get("remote_url") or "").strip()
    offline = profile.get("offline") if isinstance(profile.get("offline"), dict) else None
    if mode == "remote":
        return ("remote", {"remote_url": remote_url}) if remote_url else (None, {})
    if mode == "offline":
        return ("offline", {"offline": dict(offline)}) if offline else (None, {})
    if remote_url:
        return "remote", {"remote_url": remote_url}
    if offline:
        return "offline", {"offline": dict(offline)}
    return None, {}

def _validate_derived_ibcmd_profiles_preview(
    *,
    user,
    database_ids: list[str],
) -> tuple[list[Any] | None, dict[str, Any] | None, int | None]:
    from apps.databases.models import Database, DbmsUserMapping

    databases = list(Database.objects.filter(id__in=database_ids))
    found = {str(db.id) for db in databases}
    missing_ids = [db_id for db_id in database_ids if db_id not in found]
    if missing_ids:
        return None, {
            "success": False,
            "error": {"code": "UNKNOWN_DATABASE", "message": f"Unknown database_ids: {', '.join(missing_ids[:5])}"},
        }, 400

    missing_profiles: list[dict[str, Any]] = []
    offline_missing_meta: list[dict[str, Any]] = []
    offline_needs_dbms: list[Any] = []
    remote_count = 0
    offline_count = 0

    for db in databases:
        db_meta = getattr(db, "metadata", None)
        db_meta_dict = db_meta if isinstance(db_meta, dict) else {}
        raw_profile = db_meta_dict.get("ibcmd_connection")
        profile = _normalize_ibcmd_connection_profile(raw_profile)
        if profile is None:
            missing_profiles.append(
                {
                    "database_id": str(getattr(db, "id", "")),
                    "database_name": getattr(db, "name", None),
                    "reason": "missing_profile",
                    "missing_keys": ["ibcmd_connection"],
                }
            )
            continue

        effective_mode, details = _resolve_effective_ibcmd_connection_profile(profile)
        if effective_mode is None:
            missing_profiles.append(
                {
                    "database_id": str(getattr(db, "id", "")),
                    "database_name": getattr(db, "name", None),
                    "reason": "unresolvable_profile",
                    "missing_keys": ["remote_url or offline"],
                    "mode": str(profile.get("mode") or "auto"),
                }
            )
            continue

        if effective_mode == "remote":
            remote_count += 1
            remote_url = str(details.get("remote_url") or "").strip()
            if not remote_url:
                missing_profiles.append(
                    {
                        "database_id": str(getattr(db, "id", "")),
                        "database_name": getattr(db, "name", None),
                        "reason": "remote_missing_remote_url",
                        "missing_keys": ["remote_url"],
                        "mode": str(profile.get("mode") or "remote"),
                    }
                )
            continue

        offline_count += 1
        offline = details.get("offline") if isinstance(details.get("offline"), dict) else None
        if not isinstance(offline, dict):
            missing_profiles.append(
                {
                    "database_id": str(getattr(db, "id", "")),
                    "database_name": getattr(db, "name", None),
                    "reason": "offline_missing_profile",
                    "missing_keys": ["offline"],
                    "mode": str(profile.get("mode") or "offline"),
                }
            )
            continue

        if not str(offline.get("config") or "").strip() or not str(offline.get("data") or "").strip():
            missing_profiles.append(
                {
                    "database_id": str(getattr(db, "id", "")),
                    "database_name": getattr(db, "name", None),
                    "reason": "offline_missing_paths",
                    "missing_keys": ["offline.config", "offline.data"],
                    "mode": str(profile.get("mode") or "offline"),
                }
            )
            continue

        offline_db_path = str(offline.get("db_path") or "").strip()
        if offline_db_path:
            continue

        missing_keys: list[str] = []
        for key in ("dbms", "db_server", "db_name"):
            if str(offline.get(key) or "").strip():
                continue
            if not str(db_meta_dict.get(key) or "").strip():
                missing_keys.append(key)
        if missing_keys:
            offline_missing_meta.append(
                {
                    "database_id": str(getattr(db, "id", "")),
                    "database_name": getattr(db, "name", None),
                    "missing_keys": missing_keys,
                }
            )
            continue

        offline_needs_dbms.append(db)

    if missing_profiles:
        limit = 25
        details: dict[str, Any] = {"missing": missing_profiles[:limit], "missing_total": len(missing_profiles)}
        if len(missing_profiles) > limit:
            details["omitted"] = len(missing_profiles) - limit
        return None, {
            "success": False,
            "error": {
                "code": "IBCMD_CONNECTION_PROFILE_INVALID",
                "message": "IBCMD connection profile is missing or incomplete for some databases",
                "details": details,
            },
        }, 400

    if offline_missing_meta:
        limit = 25
        details: dict[str, Any] = {"missing": offline_missing_meta[:limit], "missing_total": len(offline_missing_meta)}
        if len(offline_missing_meta) > limit:
            details["omitted"] = len(offline_missing_meta) - limit
        return None, {
            "success": False,
            "error": {
                "code": "OFFLINE_DB_METADATA_NOT_CONFIGURED",
                "message": "Offline DBMS metadata is not configured for some databases",
                "details": details,
            },
        }, 400

    if offline_needs_dbms:
        qs = DbmsUserMapping.objects.filter(database__in=offline_needs_dbms, user=user)
        configured = {str(row.database_id) for row in qs}
        missing_dbs = [db for db in offline_needs_dbms if str(db.id) not in configured]
        if missing_dbs:
            preview = ", ".join((db.name or str(db.id)) for db in missing_dbs[:5])
            msg = f"DBMS user mapping is not configured for {len(missing_dbs)} database(s): {preview}"
            if len(missing_dbs) > 5:
                msg += f" and {len(missing_dbs) - 5} more"
            return None, {"success": False, "error": {"code": "DBMS_MAPPING_NOT_CONFIGURED", "message": msg}}, 400

    meta = {
        "remote_count": remote_count,
        "offline_count": offline_count,
        "mixed_mode": bool(remote_count and offline_count),
    }
    return databases, meta, None

def _preview_ibcmd_cli(
    *,
    user,
    command_id: str,
    mode: str,
    connection: dict | None,
    params: dict | None,
    additional_args: list[str] | None,
    stdin: str | None,
    database_ids: list[str],
):
    driver = "ibcmd"
    versions = resolve_driver_catalog_versions(driver)
    if versions.base_version is None:
        return None, {
            "success": False,
            "error": {"code": "CATALOG_NOT_AVAILABLE", "message": "ibcmd catalog is not imported yet"},
        }, 400

    effective = get_effective_driver_catalog(
        driver=driver,
        base_version=versions.base_version,
        overrides_version=versions.overrides_version,
    )
    filtered_catalog = filter_catalog_for_user(user, effective.catalog)
    commands_by_id = filtered_catalog.get("commands_by_id") if isinstance(filtered_catalog, dict) else None
    if not isinstance(commands_by_id, dict):
        return None, {"success": False, "error": {"code": "CATALOG_INVALID", "message": "ibcmd catalog is invalid"}}, 500

    command = commands_by_id.get(command_id)
    if not isinstance(command, dict) or command.get("disabled") is True:
        return None, {"success": False, "error": {"code": "UNKNOWN_COMMAND", "message": f"Unknown command_id: {command_id}"}}, 400

    strict = str(mode or "guided").strip().lower() != "manual"
    connection_dict = dict(connection) if isinstance(connection, dict) else {}
    additional_args = list(additional_args or [])
    params = dict(params) if isinstance(params, dict) else {}

    flattened_connection = flatten_connection_params(connection_dict) if connection_dict else {}
    has_explicit_connection = bool(flattened_connection)
    command_scope = str(command.get("scope") or "").strip()
    derived_meta: dict[str, Any] | None = None
    if command_scope == "per_database" and not has_explicit_connection:
        if not database_ids:
            return None, {
                "success": False,
                "error": {
                    "code": "MISSING_DATABASE_IDS",
                    "message": "database_ids are required for per_database preview when connection is derived from database profiles",
                },
            }, 400
        _, derived_meta, err_status = _validate_derived_ibcmd_profiles_preview(user=user, database_ids=database_ids)
        if err_status is not None:
            return None, derived_meta, err_status

    if flattened_connection:
        conflicts = detect_connection_option_conflicts(
            connection_params=flattened_connection,
            additional_args=additional_args,
        )
        if conflicts:
            conflict_list = ", ".join(sorted(set(conflicts)))
            return None, {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"duplicate driver-level options in additional_args: {conflict_list}",
                },
            }, 400

        overlap = [
            key
            for key in flattened_connection.keys()
            if key in params and params.get(key) not in (None, "")
        ]
        if overlap:
            overlap_list = ", ".join(sorted(set(str(k) for k in overlap)))
            return None, {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"driver-level options must be provided via connection (not params): {overlap_list}",
                },
            }, 400

    pre_args = build_ibcmd_connection_args(
        driver_schema=filtered_catalog.get("driver_schema") if isinstance(filtered_catalog, dict) else None,
        connection=connection_dict,
    )

    try:
        builder = build_ibcmd_cli_argv if strict else build_ibcmd_cli_argv_manual
        argv, argv_masked = builder(
            command=command,
            params=params,
            additional_args=additional_args,
            pre_args=pre_args,
        )
    except ValueError as exc:
        return None, {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}, 400

    bindings = []
    bindings.append(
        {
            "target_ref": "command_id",
            "source_ref": "request.executor.command_id",
            "resolve_at": "api",
            "sensitive": False,
            "status": "applied",
        }
    )
    for key in sorted(params.keys()):
        bindings.append(
            {
                "target_ref": f"params.{key}",
                "source_ref": f"request.executor.params.{key}",
                "resolve_at": "api",
                "sensitive": _is_sensitive_key(str(key)),
                "status": "applied",
            }
        )
    for idx, token in enumerate(additional_args):
        bindings.append(
            {
                "target_ref": f"additional_args[{idx}]",
                "source_ref": f"request.executor.additional_args[{idx}]",
                "resolve_at": "api",
                "sensitive": _is_sensitive_key(str(token)),
                "status": "applied",
            }
        )
    for key in sorted(flattened_connection.keys()):
        bindings.append(
            {
                "target_ref": f"connection.{key}",
                "source_ref": f"request.connection.{key}",
                "resolve_at": "api",
                "sensitive": _is_sensitive_key(str(key)),
                "status": "applied",
            }
        )

    # For per_database ibcmd_cli, connection may be resolved at runtime per target database.
    if command_scope == "per_database" and database_ids and not has_explicit_connection:
        bindings.append(
            {
                "target_ref": "connection_source",
                "source_ref": "target_db.metadata.ibcmd_connection",
                "resolve_at": "worker",
                "sensitive": False,
                "status": "pending",
            }
        )
        bindings.append(
            {
                "target_ref": "connection.remote",
                "source_ref": "target_db.metadata.ibcmd_connection.remote_url",
                "resolve_at": "worker",
                "sensitive": False,
                "status": "pending",
            }
        )
        for key in (
            "config",
            "data",
            "db_path",
            "dbms",
            "db_server",
            "db_name",
            "ftext2_data",
            "ftext_data",
            "lock",
            "log_data",
            "openid_data",
            "session_data",
            "stt_data",
            "system",
            "temp",
            "users_data",
        ):
            bindings.append(
                {
                    "target_ref": f"connection.offline.{key}",
                    "source_ref": f"target_db.metadata.ibcmd_connection.offline.{key}",
                    "resolve_at": "worker",
                    "sensitive": False,
                    "status": "pending",
                }
            )
        bindings.append(
            {
                "target_ref": "connection.offline.db_user",
                "source_ref": "credentials.db_user_mapping",
                "resolve_at": "worker",
                "sensitive": True,
                "status": "pending",
            }
        )
        bindings.append(
            {
                "target_ref": "connection.offline.db_pwd",
                "source_ref": "credentials.db_user_mapping",
                "resolve_at": "worker",
                "sensitive": True,
                "status": "pending",
            }
        )
    else:
        connection_remote = str(connection_dict.get("remote") or "").strip()
        connection_pid = connection_dict.get("pid")
        offline = connection_dict.get("offline") if isinstance(connection_dict.get("offline"), dict) else None
        offline_db_path = str((offline or {}).get("db_path") or "").strip() if isinstance(offline, dict) else ""
        if command_scope == "per_database" and database_ids and not connection_remote and not connection_pid and not offline_db_path:
            offline_defaults = dict(offline) if isinstance(offline, dict) else {}
            for key, source_key in (("dbms", "dbms"), ("db_server", "db_server"), ("db_name", "db_name")):
                if str(offline_defaults.get(key) or "").strip():
                    continue
                bindings.append(
                    {
                        "target_ref": f"connection.offline.{key}",
                        "source_ref": f"target_db.metadata.{source_key}",
                        "resolve_at": "worker",
                        "sensitive": False,
                        "status": "pending",
                    }
                )
            bindings.append(
                {
                    "target_ref": "connection.offline.db_user",
                    "source_ref": "credentials.db_user_mapping",
                    "resolve_at": "worker",
                    "sensitive": True,
                    "status": "pending",
                }
            )
            bindings.append(
                {
                    "target_ref": "connection.offline.db_pwd",
                    "source_ref": "credentials.db_user_mapping",
                    "resolve_at": "worker",
                    "sensitive": True,
                    "status": "pending",
                }
            )
    if stdin:
        bindings.append(
            {
                "target_ref": "stdin",
                "source_ref": "request.executor.stdin",
                "resolve_at": "api",
                "sensitive": True,
                "status": "applied",
            }
        )

    execution_plan = {
        "kind": "ibcmd_cli",
        "plan_version": 1,
        "argv_masked": argv_masked,
        "stdin_masked": "***" if stdin else None,
        "targets": {
            "scope": str(command.get("scope") or "").strip() or None,
            "database_ids_count": len(database_ids),
        },
    }
    if derived_meta is not None:
        execution_plan["targets"]["connection_source"] = "database_profile"
        execution_plan["targets"]["mixed_mode"] = bool(derived_meta.get("mixed_mode"))
    return {"execution_plan": execution_plan, "bindings": bindings}, None, None


def _preview_designer_cli(
    *,
    executor: dict,
    database_ids: list[str],
):
    command = str(executor.get("command_id") or "").strip()
    if not command:
        return None, {"success": False, "error": {"code": "MISSING_COMMAND_ID", "message": "command_id is required"}}, 400

    args = executor.get("additional_args")
    args_list = [str(x) for x in (args or []) if x is not None]
    argv_masked = [command] + ["/P***" if a.startswith("/P") and len(a) > 2 else a for a in args_list]

    bindings = [
        {
            "target_ref": "command",
            "source_ref": "request.executor.command_id",
            "resolve_at": "api",
            "sensitive": False,
            "status": "applied",
        }
    ]
    for idx, token in enumerate(args_list):
        bindings.append(
            {
                "target_ref": f"args[{idx}]",
                "source_ref": f"request.executor.additional_args[{idx}]",
                "resolve_at": "api",
                "sensitive": _is_sensitive_key(token),
                "status": "applied",
            }
        )

    execution_plan = {
        "kind": "designer_cli",
        "plan_version": 1,
        "argv_masked": argv_masked,
        "targets": {"database_ids_count": len(database_ids)},
    }
    return {"execution_plan": execution_plan, "bindings": bindings}, None, None


def _preview_workflow(
    *,
    user,
    executor: dict,
    database_ids: list[str],
):
    workflow_id = str(executor.get("workflow_id") or "").strip()
    if not workflow_id:
        return None, {"success": False, "error": {"code": "MISSING_WORKFLOW_ID", "message": "workflow_id is required"}}, 400

    try:
        workflow_uuid = uuid.UUID(workflow_id)
    except (ValueError, AttributeError):
        return None, {"success": False, "error": {"code": "WORKFLOW_ID_INVALID", "message": "workflow_id must be a UUID"}}, 400

    workflow = WorkflowTemplate.objects.filter(id=workflow_uuid).first()
    if workflow is None or not workflow.is_active or not workflow.is_valid:
        return None, {"success": False, "error": {"code": "WORKFLOW_NOT_FOUND", "message": "workflow not found"}}, 400
    if not user.has_perm(perms.PERM_TEMPLATES_EXECUTE_WORKFLOW_TEMPLATE, workflow):
        return None, {"success": False, "error": {"code": "FORBIDDEN", "message": "workflow execution is not allowed"}}, 403

    base_context = executor.get("params")
    base_context_dict = dict(base_context) if isinstance(base_context, dict) else {}
    input_context = {
        **base_context_dict,
        "database_ids": list(database_ids),
    }

    bindings = [
        {
            "target_ref": "workflow_id",
            "source_ref": "request.executor.workflow_id",
            "resolve_at": "api",
            "sensitive": False,
            "status": "applied",
        },
        {
            "target_ref": "input_context.database_ids",
            "source_ref": "request.database_ids",
            "resolve_at": "api",
            "sensitive": False,
            "status": "applied",
        },
    ]
    for key in sorted(base_context_dict.keys()):
        bindings.append(
            {
                "target_ref": f"input_context.{key}",
                "source_ref": f"request.executor.params.{key}",
                "resolve_at": "api",
                "sensitive": _is_sensitive_key(str(key)),
                "status": "applied",
            }
        )

    execution_plan = {
        "kind": "workflow",
        "plan_version": 1,
        "workflow_id": workflow_id,
        "input_context_masked": _mask_json_dict(input_context),
        "targets": {"database_ids_count": len(database_ids)},
    }
    return {"execution_plan": execution_plan, "bindings": bindings}, None, None


@extend_schema(
    tags=["v2"],
    summary="Preview execution plan",
    description="Build safe Execution Plan + Binding Provenance (staff-only).",
    request=ExecutionPlanPreviewRequestSerializer,
    responses={
        200: ExecutionPlanWithBindingsSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def preview_execution_plan(request):
    if not getattr(request.user, "is_staff", False):
        return Response(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "Staff only"}},
            status=http_status.HTTP_403_FORBIDDEN,
        )

    serializer = ExecutionPlanPreviewRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "error": {"code": "INVALID_REQUEST", "message": "Invalid request"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    executor = serializer.validated_data["executor"]
    kind = str(executor.get("kind") or "").strip()
    database_ids = [str(x) for x in (serializer.validated_data.get("database_ids") or [])]

    if kind == "ibcmd_cli":
        command_id = str(executor.get("command_id") or "").strip()
        if not command_id:
            return Response(
                {"success": False, "error": {"code": "MISSING_COMMAND_ID", "message": "command_id is required"}},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        mode = str(executor.get("mode") or "guided").strip().lower()
        params = executor.get("params")
        additional_args = executor.get("additional_args")
        stdin = executor.get("stdin")
        connection = serializer.validated_data.get("connection") or {}

        result, error_body, error_status = _preview_ibcmd_cli(
            user=request.user,
            command_id=command_id,
            mode=mode,
            connection=connection,
            params=params,
            additional_args=additional_args,
            stdin=stdin,
            database_ids=database_ids,
        )
        if error_body is not None:
            return Response(error_body, status=error_status)
        return Response(result)

    if kind == "designer_cli":
        result, error_body, error_status = _preview_designer_cli(executor=executor, database_ids=database_ids)
        if error_body is not None:
            return Response(error_body, status=error_status)
        return Response(result)

    if kind == "workflow":
        result, error_body, error_status = _preview_workflow(
            user=request.user,
            executor=executor,
            database_ids=database_ids,
        )
        if error_body is not None:
            return Response(error_body, status=error_status)
        return Response(result)

    return Response(
        {"success": False, "error": {"code": "UNSUPPORTED_KIND", "message": f"Unsupported executor kind: {kind}"}},
        status=http_status.HTTP_400_BAD_REQUEST,
    )

