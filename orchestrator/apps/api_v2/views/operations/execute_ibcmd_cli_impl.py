"""Operations: ibcmd_cli validation + enqueue implementation."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from rest_framework import status as http_status
from rest_framework.response import Response

from apps.artifacts.storage import ArtifactStorageError
from apps.core import permission_codes as perms
from apps.operations.driver_catalog_effective import (
    compute_actor_roles_hash,
    compute_driver_catalog_etag,
    explain_command_denied,
    filter_catalog_for_user,
    get_actor_roles,
    get_command_min_db_level,
    get_effective_driver_catalog,
    get_effective_driver_catalog_lkg,
    resolve_driver_catalog_versions,
)
from apps.operations.ibcmd_cli_builder import (
    build_ibcmd_cli_argv,
    build_ibcmd_cli_argv_manual,
    build_ibcmd_connection_args,
    detect_connection_option_conflicts,
    flatten_connection_params,
)
from apps.operations.prometheus_metrics import record_driver_command_denied
from apps.operations.services import OperationsService

from .utils import _is_sensitive_key

logger = logging.getLogger(__name__)

def _op_error(
    code: str,
    message: str,
    *,
    status: int = 400,
    details: dict[str, Any] | None = None,
) -> Response:
    payload: dict[str, Any] = {"success": False, "error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return Response(payload, status=status)

def _normalize_ibcmd_connection_profile(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    remote_raw = raw.get("remote")
    if remote_raw in (None, ""):
        remote_raw = raw.get("remote_url")
    remote = str(remote_raw).strip() if remote_raw not in (None, "") else ""
    if remote and not remote.lower().startswith("ssh://"):
        remote = ""

    pid_raw = raw.get("pid")
    pid = pid_raw if isinstance(pid_raw, int) and pid_raw > 0 else None

    offline_in = raw.get("offline")
    offline: dict[str, str] | None = None
    if isinstance(offline_in, dict):
        offline_safe: dict[str, str] = {}
        for k, v in offline_in.items():
            key = str(k).strip()
            if not key:
                continue
            lowered = key.lower()
            if lowered in {"db_user", "db_pwd", "db_password"}:
                continue
            if v in (None, ""):
                continue
            rendered = str(v).strip()
            if not rendered:
                continue
            offline_safe[key] = rendered
        offline = offline_safe or None

    out: dict[str, Any] = {}
    if remote:
        out["remote"] = remote
    if pid is not None:
        out["pid"] = pid
    if offline:
        out["offline"] = offline
    return out

def _is_empty_ibcmd_profile(profile: dict[str, Any] | None) -> bool:
    if not isinstance(profile, dict) or not profile:
        return True
    remote = str(profile.get("remote") or "").strip()
    pid = profile.get("pid")
    offline = profile.get("offline") if isinstance(profile.get("offline"), dict) else None
    if remote:
        return False
    if isinstance(pid, int) and pid > 0:
        return False
    if isinstance(offline, dict) and len(offline) > 0:
        return False
    return True

def _validate_ibcmd_connection_profiles_or_error(
    *,
    databases: list[Any],
) -> Response | None:
    """
    Fail-closed validation for per-target ibcmd connection profiles.

    - Ensures each database has a non-empty profile.
    - Does not attempt to validate semantic correctness of flag combinations.
    """
    missing: list[dict[str, Any]] = []

    for db in databases:
        db_meta = getattr(db, "metadata", None)
        db_meta_dict = db_meta if isinstance(db_meta, dict) else {}
        raw_profile = db_meta_dict.get("ibcmd_connection")
        profile = _normalize_ibcmd_connection_profile(raw_profile)
        if profile is None or _is_empty_ibcmd_profile(profile):
            missing.append(
                {
                    "database_id": str(getattr(db, "id", "")),
                    "database_name": getattr(db, "name", None),
                    "reason": "missing_or_empty_profile",
                    "missing_keys": ["ibcmd_connection"],
                }
            )
            continue

    if missing:
        limit = 25
        details: dict[str, Any] = {"missing": missing[:limit], "missing_total": len(missing)}
        if len(missing) > limit:
            details["omitted"] = len(missing) - limit
        return _op_error(
            "IBCMD_CONNECTION_PROFILE_INVALID",
            "IBCMD connection profile is missing or empty for some databases",
            details=details,
        )

    return None

def _execute_ibcmd_cli_validated(
    request,
    validated_data: dict[str, Any],
    *,
    legacy_operation_type: str | None = None,
    metadata_overrides: dict[str, Any] | None = None,
):
    from apps.databases.models import Database, PermissionLevel, DbmsUserMapping
    from apps.databases.services import PermissionService
    from apps.operations.models import BatchOperation, Task
    command_id = str(validated_data.get('command_id') or '').strip()
    mode = str(validated_data.get('mode') or 'guided').strip().lower()
    database_ids = [str(db_id) for db_id in (validated_data.get('database_ids') or [])]
    auth_database_id = validated_data.get('auth_database_id')
    connection = validated_data.get('connection') or {}
    ib_auth = validated_data.get("ib_auth") or {}
    dbms_auth = validated_data.get("dbms_auth") or {}
    params = validated_data.get('params') or {}
    additional_args = validated_data.get('additional_args') or []
    stdin = validated_data.get('stdin') or ""
    confirm_dangerous = bool(validated_data.get('confirm_dangerous') or False)
    timeout_seconds = int(validated_data.get('timeout_seconds') or 900)
    if not command_id:
        return _op_error("MISSING_COMMAND_ID", "command_id is required")
    resolved = resolve_driver_catalog_versions("ibcmd")
    if resolved.base_version is None:
        return _op_error("CATALOG_NOT_AVAILABLE", "ibcmd catalog is not imported yet")
    effective = get_effective_driver_catalog(
        driver="ibcmd",
        base_version=resolved.base_version,
        overrides_version=resolved.overrides_version,
    )
    catalog = filter_catalog_for_user(request.user, effective.catalog)
    raw_commands_by_id = effective.catalog.get("commands_by_id") if isinstance(effective.catalog, dict) else None
    if not isinstance(raw_commands_by_id, dict):
        raw_commands_by_id = None
    commands_by_id = catalog.get("commands_by_id") if isinstance(catalog, dict) else None
    if not isinstance(commands_by_id, dict):
        return _op_error("CATALOG_INVALID", "ibcmd catalog is invalid", status=500)
    command = commands_by_id.get(command_id)
    if not isinstance(command, dict):
        raw_command = raw_commands_by_id.get(command_id) if raw_commands_by_id else None
        if isinstance(raw_command, dict):
            reason = explain_command_denied(request.user, raw_command) or "denied"
            record_driver_command_denied("ibcmd", reason)
            logger.warning(
                "Driver command denied by RBAC filter",
                extra={
                    "driver": "ibcmd",
                    "command_id": command_id,
                    "reason": reason,
                    "user": getattr(request.user, "username", None),
                    "roles": get_actor_roles(request.user),
                },
            )
        return Response({
            "success": False,
            "error": {"code": "UNKNOWN_COMMAND", "message": f"Unknown command_id: {command_id}"},
        }, status=400)
    if command.get("disabled") is True:
        record_driver_command_denied("ibcmd", "disabled")
        return Response({
            "success": False,
            "error": {"code": "UNKNOWN_COMMAND", "message": f"Unknown command_id: {command_id}"},
        }, status=400)
    scope = str(command.get("scope") or "").strip().lower()
    if scope not in {"per_database", "global"}:
        return Response({
            "success": False,
            "error": {"code": "COMMAND_INVALID", "message": "Command scope is invalid"},
        }, status=500)
    risk_level = str(command.get("risk_level") or "").strip().lower()
    required_capability_perm = (
        perms.PERM_OPERATIONS_EXECUTE_DANGEROUS_OPERATION
        if risk_level == "dangerous"
        else perms.PERM_OPERATIONS_EXECUTE_SAFE_OPERATION
    )
    if not request.user.has_perm(required_capability_perm):
        reason = "capability_dangerous_denied" if risk_level == "dangerous" else "capability_safe_denied"
        record_driver_command_denied("ibcmd", reason)
        message = "You do not have permission to execute dangerous operations."
        if risk_level != "dangerous":
            message = "You do not have permission to execute operations."
        return Response(
            {"success": False, "error": {"code": "PERMISSION_DENIED", "message": message}},
            status=403,
        )
    if risk_level == "dangerous" and not confirm_dangerous:
        return Response({
            "success": False,
            "error": {
                "code": "DANGEROUS_CONFIRM_REQUIRED",
                "message": "confirm_dangerous=true is required for dangerous commands",
            },
        }, status=400)
    service_allowlist = {
        # Keep this intentionally tight; expand only with explicit approval.
        "infobase.extension.list",
        "infobase.extension.info",
    }
    ib_auth_strategy_raw = ""
    ib_auth_strategy_explicit = False
    if isinstance(ib_auth, dict):
        if "strategy" in ib_auth and ib_auth.get("strategy") is not None:
            ib_auth_strategy_explicit = True
        ib_auth_strategy_raw = str(ib_auth.get("strategy") or "").strip().lower()
    ib_auth_strategy = ib_auth_strategy_raw or ("actor" if scope == "per_database" else "none")
    if ib_auth_strategy not in {"actor", "service", "none"}:
        return Response({
            "success": False,
            "error": {"code": "IB_AUTH_STRATEGY_INVALID", "message": "ib_auth.strategy must be actor|service|none"},
        }, status=400)
    if scope != "per_database":
        if ib_auth_strategy_explicit and ib_auth_strategy != "none":
            return Response({
                "success": False,
                "error": {"code": "IB_AUTH_NOT_ALLOWED", "message": "ib_auth.strategy is not allowed for global scope commands"},
            }, status=400)
        ib_auth_strategy = "none"
    if ib_auth_strategy == "service":
        if risk_level != "safe":
            return Response({
                "success": False,
                "error": {"code": "IB_AUTH_SERVICE_NOT_ALLOWED", "message": "ib_auth.strategy=service is allowed only for safe commands"},
            }, status=400)
        if command_id not in service_allowlist:
            return Response({
                "success": False,
                "error": {"code": "IB_AUTH_SERVICE_NOT_ALLOWED", "message": f"ib_auth.strategy=service is not allowed for command_id={command_id}"},
            }, status=400)
        if not (getattr(request.user, "is_staff", False) or request.user.has_perm(perms.PERM_OPERATIONS_USE_SERVICE_IB_AUTH)):
            record_driver_command_denied("ibcmd", "ib_auth_service_denied")
            return Response(
                {"success": False, "error": {"code": "PERMISSION_DENIED", "message": "You do not have permission to use service infobase authentication."}},
                status=403,
            )
    dbms_auth_strategy_raw = ""
    dbms_auth_strategy_explicit = False
    if isinstance(dbms_auth, dict):
        if "strategy" in dbms_auth and dbms_auth.get("strategy") is not None:
            dbms_auth_strategy_explicit = True
        dbms_auth_strategy_raw = str(dbms_auth.get("strategy") or "").strip().lower()
    dbms_auth_strategy = dbms_auth_strategy_raw or "actor"
    if dbms_auth_strategy not in {"actor", "service"}:
        return Response({
            "success": False,
            "error": {"code": "DBMS_AUTH_STRATEGY_INVALID", "message": "dbms_auth.strategy must be actor|service"},
        }, status=400)
    if scope != "per_database" and dbms_auth_strategy_explicit:
        # Keep semantics tight: per-target DBMS creds resolution is meaningful only for per_database operations.
        return Response({
            "success": False,
            "error": {"code": "DBMS_AUTH_NOT_ALLOWED", "message": "dbms_auth.strategy is not allowed for global scope commands"},
        }, status=400)
    if dbms_auth_strategy == "service":
        if risk_level != "safe":
            return Response({
                "success": False,
                "error": {"code": "DBMS_AUTH_SERVICE_NOT_ALLOWED", "message": "dbms_auth.strategy=service is allowed only for safe commands"},
            }, status=400)
        if command_id not in service_allowlist:
            return Response({
                "success": False,
                "error": {"code": "DBMS_AUTH_SERVICE_NOT_ALLOWED", "message": f"dbms_auth.strategy=service is not allowed for command_id={command_id}"},
            }, status=400)
        if not (getattr(request.user, "is_staff", False) or request.user.has_perm(perms.PERM_OPERATIONS_USE_SERVICE_DBMS_AUTH)):
            record_driver_command_denied("ibcmd", "dbms_auth_service_denied")
            return Response(
                {"success": False, "error": {"code": "PERMISSION_DENIED", "message": "You do not have permission to use service DBMS authentication."}},
                status=403,
            )
    required_level = PermissionLevel.OPERATE
    if risk_level == "dangerous":
        required_level = PermissionLevel.MANAGE
    min_db_level = get_command_min_db_level(command)
    if min_db_level in {"operate", "manage", "admin"}:
        required_level = {
            "operate": PermissionLevel.OPERATE,
            "manage": PermissionLevel.MANAGE,
            "admin": PermissionLevel.ADMIN,
        }[min_db_level]
    if scope == "global":
        if database_ids:
            return Response({
                "success": False,
                "error": {"code": "DATABASE_IDS_NOT_ALLOWED", "message": "database_ids must be empty for global scope"},
            }, status=400)
        if auth_database_id is None:
            return Response({
                "success": False,
                "error": {"code": "MISSING_AUTH_DATABASE", "message": "auth_database_id is required for global scope"},
            }, status=400)
        auth_db_id = str(auth_database_id)
        allowed, denied = PermissionService.check_bulk_permission(
            request.user,
            [auth_db_id],
            required_level,
        )
        if not allowed:
            return Response({
                "success": False,
                "error": {"code": "PERMISSION_DENIED", "message": f"Access denied for database: {', '.join(denied)}"},
            }, status=403)
        if not Database.objects.filter(id=auth_db_id).exists():
            return Response({
                "success": False,
                "error": {"code": "UNKNOWN_DATABASE", "message": f"Unknown auth_database_id: {auth_db_id}"},
            }, status=400)
    else:
        if not database_ids:
            return Response({
                "success": False,
                "error": {"code": "MISSING_DATABASE_IDS", "message": "database_ids cannot be empty for per_database scope"},
            }, status=400)
        allowed, denied = PermissionService.check_bulk_permission(
            request.user,
            database_ids,
            required_level,
        )
        if not allowed:
            denied_str = ", ".join(denied[:5])
            msg = f"Access denied for databases: {denied_str}"
            if len(denied) > 5:
                msg += f" and {len(denied) - 5} more"
            return Response({
                "success": False,
                "error": {"code": "PERMISSION_DENIED", "message": msg},
            }, status=403)
    merged_params = dict(params) if isinstance(params, dict) else {}
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
            return Response({
                "success": False,
                "error": {"code": "PID_IN_ARGS_NOT_ALLOWED", "message": "Use connection.pid instead of --pid in additional_args"},
            }, status=400)
    for token in additional_args:
        t = str(token or "").strip().lower()
        if (
            t in {"--request-db-pwd", "--request-database-password", "-w"}
            or t.startswith("--request-db-pwd=")
            or t.startswith("--request-database-password=")
        ):
            return Response({
                "success": False,
                "error": {
                    "code": "REQUEST_DB_PWD_NOT_ALLOWED",
                    "message": "stdin flag --request-db-pwd (-W) is not allowed; DBMS credentials are resolved via DBMS user mapping",
                },
            }, status=400)
    # DBMS credentials must not be provided via API/UI; they are resolved per database via DbmsUserMapping.
    if isinstance(connection_dict.get("offline"), dict):
        offline_dict = connection_dict.get("offline") or {}
        if any(k in offline_dict and offline_dict.get(k) not in (None, "") for k in ("db_user", "db_pwd", "db_password")):
            return Response({
                "success": False,
                "error": {
                    "code": "DBMS_CREDS_NOT_ALLOWED",
                    "message": "DBMS credentials must not be provided in connection.offline; configure DbmsUserMapping instead",
                },
            }, status=400)
    flattened_connection = flatten_connection_params(connection_dict) if connection_dict else {}
    if flattened_connection:
        conflicts = detect_connection_option_conflicts(
            connection_params=flattened_connection,
            additional_args=list(additional_args or []),
        )
        if conflicts:
            conflict_list = ", ".join(sorted(set(conflicts)))
            return Response({
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"duplicate driver-level options in additional_args: {conflict_list}",
                },
            }, status=400)
        if isinstance(params, dict) and params:
            overlap = [
                key
                for key in flattened_connection.keys()
                if key in params and params.get(key) not in (None, "")
            ]
            if overlap:
                overlap_list = ", ".join(sorted(set(str(k) for k in overlap)))
                return Response({
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": f"driver-level options must be provided via connection (not params): {overlap_list}",
                    },
                }, status=400)
    if "pid" not in connection_dict:
        for key, value in list(merged_params.items()):
            if str(key or "").strip().lower() != "pid":
                continue
            if value is None or value == "":
                break
            try:
                connection_dict["pid"] = int(value)
                merged_params.pop(key, None)
            except (TypeError, ValueError):
                return Response({
                    "success": False,
                    "error": {"code": "PID_INVALID", "message": "pid must be an integer"},
                }, status=400)
            break
    if connection_dict.get("pid") is not None:
        env = (os.environ.get("APP_ENV") or os.environ.get("ENVIRONMENT") or "").strip().lower()
        if env in {"prod", "production"}:
            return Response({
                "success": False,
                "error": {"code": "PID_NOT_ALLOWED", "message": "--pid is not allowed in production"},
            }, status=400)
    flattened_connection = flatten_connection_params(connection_dict) if connection_dict else {}
    raw_payload = getattr(request, "data", None)
    raw_has_connection = isinstance(raw_payload, dict) and "connection" in raw_payload
    has_explicit_connection = raw_has_connection or bool(flattened_connection)
    pre_args = build_ibcmd_connection_args(
        driver_schema=catalog.get("driver_schema") if isinstance(catalog, dict) else None,
        connection=connection_dict,
    )
    try:
        builder = build_ibcmd_cli_argv_manual if mode == "manual" else build_ibcmd_cli_argv
        argv, argv_masked = builder(command=command, params=merged_params, additional_args=additional_args, pre_args=pre_args)
    except ValueError as exc:
        return Response({
            "success": False,
            "error": {"code": "VALIDATION_ERROR", "message": str(exc)},
        }, status=400)
    payload_data = {
        "command_id": command_id,
        "mode": mode,
        "argv": argv,
        "argv_masked": argv_masked,
        "stdin": stdin,
        "connection": connection_dict,
        "ib_auth": {"strategy": ib_auth_strategy},
        "dbms_auth": {"strategy": dbms_auth_strategy},
    }
    payload_options: dict[str, Any] = {}
    if scope == "global":
        payload_options["target_scope"] = "global"
        payload_data["auth_database_id"] = str(auth_database_id)
        tmp_payload = {"data": payload_data, "filters": {}, "options": {}}
        target_ref = OperationsService._compute_global_target_ref(tmp_payload)
        if not target_ref:
            return Response({
                "success": False,
                "error": {"code": "MISSING_CONNECTION", "message": "connection is required for global scope"},
            }, status=400)
        payload_options["target_ref"] = target_ref
        if hasattr(OperationsService, "_extract_target_scope"):
            try:
                from apps.operations.redis_client import redis_client
                if redis_client.check_global_target_lock(target_ref):
                    return Response({
                        "success": False,
                        "error": {"code": "GLOBAL_TARGET_LOCKED", "message": "Global target already in progress"},
                    }, status=409)
            except Exception:
                pass
    payload = {"data": payload_data, "filters": {}, "options": payload_options}
    databases = []
    if scope == "per_database":
        if raw_has_connection and isinstance(connection_dict, dict) and not connection_dict:
            return Response({
                "success": False,
                "error": {"code": "MISSING_CONNECTION", "message": "connection is required for per_database scope"},
            }, status=400)
        databases = list(Database.objects.filter(id__in=database_ids))
        found = {str(db.id) for db in databases}
        missing = [db_id for db_id in database_ids if db_id not in found]
        if missing:
            return Response({
                "success": False,
                "error": {
                    "code": "UNKNOWN_DATABASE",
                    "message": f"Unknown database_ids: {', '.join(missing[:5])}",
                },
                }, status=400)
        if not has_explicit_connection:
            prof_err = _validate_ibcmd_connection_profiles_or_error(
                databases=databases,
            )
            if prof_err is not None:
                return prof_err
            payload_data["connection_source"] = "database_profile"
        else:
            # No additional preflight validation for explicit connection (raw flags).
            pass
    operation_id = str(uuid.uuid4())
    operation_name = f"ibcmd_cli {command_id}"
    if scope == "per_database":
        operation_name = f"{operation_name} - {len(databases)} databases"
    else:
        operation_name = f"{operation_name} (global)"
    execution_plan = {
        "kind": "ibcmd_cli",
        "plan_version": 1,
        "argv_masked": argv_masked,
        "stdin_masked": "***" if stdin else None,
        "targets": {
            "scope": scope,
            "database_ids_count": len(database_ids) if scope == "per_database" else 0,
        },
    }
    bindings = [
        {
            "target_ref": "command_id",
            "source_ref": "request.command_id",
            "resolve_at": "api",
            "sensitive": False,
            "status": "applied",
        },
        {
            "target_ref": "mode",
            "source_ref": "request.mode",
            "resolve_at": "api",
            "sensitive": False,
            "status": "applied",
        },
    ]
    if scope == "global":
        bindings.append(
            {
                "target_ref": "auth_database_id",
                "source_ref": "request.auth_database_id",
                "resolve_at": "api",
                "sensitive": False,
                "status": "applied",
            }
        )
    bindings.append(
        {
            "target_ref": "ib_auth.strategy",
            "source_ref": "request.ib_auth.strategy" if ib_auth_strategy_explicit else "default.ib_auth.strategy",
            "resolve_at": "api",
            "sensitive": False,
            "status": "applied",
        }
    )
    bindings.append(
        {
            "target_ref": "dbms_auth.strategy",
            "source_ref": "request.dbms_auth.strategy" if dbms_auth_strategy_explicit else "default.dbms_auth.strategy",
            "resolve_at": "api",
            "sensitive": False,
            "status": "applied",
        }
    )
    if ib_auth_strategy in {"actor", "service"} and scope == "per_database":
        bindings.append(
            {
                "target_ref": "infobase_auth",
                "source_ref": (
                    "credentials.ib_user_mapping" if ib_auth_strategy == "actor" else "credentials.ib_service_mapping"
                ),
                "resolve_at": "worker",
                "sensitive": True,
                "status": "unresolved",
            }
        )
    if scope == "per_database":
        if not has_explicit_connection:
            bindings.append(
                {
                    "target_ref": "connection_source",
                    "source_ref": "target_db.metadata.ibcmd_connection",
                    "resolve_at": "worker",
                    "sensitive": False,
                    "status": "unresolved",
                }
            )
            bindings.append(
                {
                    "target_ref": "connection.remote",
                    "source_ref": "target_db.metadata.ibcmd_connection.remote",
                    "resolve_at": "worker",
                    "sensitive": False,
                    "status": "unresolved",
                }
            )
            bindings.append(
                {
                    "target_ref": "connection.pid",
                    "source_ref": "target_db.metadata.ibcmd_connection.pid",
                    "resolve_at": "worker",
                    "sensitive": False,
                    "status": "unresolved",
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
                        "status": "unresolved",
                    }
                )
            dbms_source = "credentials.db_user_mapping" if dbms_auth_strategy == "actor" else "credentials.db_service_mapping"
            bindings.append(
                {
                    "target_ref": "connection.offline.db_user",
                    "source_ref": dbms_source,
                    "resolve_at": "worker",
                    "sensitive": True,
                    "status": "unresolved",
                }
            )
            bindings.append(
                {
                    "target_ref": "connection.offline.db_pwd",
                    "source_ref": dbms_source,
                    "resolve_at": "worker",
                    "sensitive": True,
                    "status": "unresolved",
                }
            )
    for key in sorted((merged_params or {}).keys()):
        bindings.append(
            {
                "target_ref": f"params.{key}",
                "source_ref": f"request.params.{key}",
                "resolve_at": "api",
                "sensitive": _is_sensitive_key(str(key)),
                "status": "applied",
            }
        )
    for idx, token in enumerate(additional_args or []):
        bindings.append(
            {
                "target_ref": f"additional_args[{idx}]",
                "source_ref": f"request.additional_args[{idx}]",
                "resolve_at": "api",
                "sensitive": _is_sensitive_key(str(token)),
                "status": "applied",
            }
        )
    if isinstance(connection_dict, dict):
        for key in sorted(k for k in connection_dict.keys() if k in {"remote", "pid"}):
            bindings.append(
                {
                    "target_ref": f"connection.{key}",
                    "source_ref": f"request.connection.{key}",
                    "resolve_at": "api",
                    "sensitive": _is_sensitive_key(str(key)),
                    "status": "applied",
                }
            )
        offline_dict = connection_dict.get("offline")
        if isinstance(offline_dict, dict):
            for key in sorted(str(k) for k in offline_dict.keys()):
                bindings.append(
                    {
                        "target_ref": f"connection.offline.{key}",
                        "source_ref": f"request.connection.offline.{key}",
                        "resolve_at": "api",
                        "sensitive": _is_sensitive_key(str(key)),
                        "status": "applied",
                    }
                )
    if stdin:
        bindings.append(
            {
                "target_ref": "stdin",
                "source_ref": "request.stdin",
                "resolve_at": "api",
                "sensitive": True,
                "status": "applied",
            }
        )
    metadata = {
        "tags": (
            ["ibcmd", "ibcmd_cli", command_id]
            if not legacy_operation_type
            else ["ibcmd", "ibcmd_cli", command_id, f"legacy:{legacy_operation_type}"]
        ),
        "command_id": command_id,
        "risk_level": risk_level,
        "scope": scope,
        "mode": mode,
        "actor_roles": get_actor_roles(request.user),
        "catalog_base_version": str(effective.base_version),
        "catalog_base_version_id": str(effective.base_version_id),
        "catalog_overrides_version": str(effective.overrides_version) if effective.overrides_version else None,
        "catalog_overrides_version_id": (
            str(effective.overrides_version_id) if effective.overrides_version_id else None
        ),
        "legacy_operation_type": legacy_operation_type,
        "execution_plan": execution_plan,
        "bindings": bindings,
    }

    try:
        tenant_id = str(getattr(request, "tenant_id", "") or "").strip()
        if tenant_id:
            from apps.runtime_settings.action_catalog import (
                UI_ACTION_CATALOG_KEY,
                compute_ibcmd_cli_snapshot_marker_from_action_catalog,
                ensure_valid_action_catalog,
            )
            from apps.runtime_settings.effective import get_effective_runtime_setting

            raw_catalog = get_effective_runtime_setting(UI_ACTION_CATALOG_KEY, tenant_id).value
            catalog, _errors = ensure_valid_action_catalog(raw_catalog)
            metadata.update(compute_ibcmd_cli_snapshot_marker_from_action_catalog(catalog, command_id))
    except Exception:
        pass

    if isinstance(metadata_overrides, dict) and metadata_overrides:
        try:
            if isinstance(metadata.get("snapshot_kinds"), list) and isinstance(metadata_overrides.get("snapshot_kinds"), list):
                base_kinds = [str(x) for x in metadata.get("snapshot_kinds") if str(x)]
                override_kinds = [str(x) for x in metadata_overrides.get("snapshot_kinds") if str(x)]
                merged = list(dict.fromkeys(base_kinds + override_kinds))
                merged_overrides = dict(metadata_overrides)
                merged_overrides["snapshot_kinds"] = merged
                metadata.update(merged_overrides)
            else:
                metadata.update(metadata_overrides)
        except Exception:
            metadata.update(metadata_overrides)

    batch_operation = BatchOperation.objects.create(
        id=operation_id,
        name=operation_name,
        operation_type=BatchOperation.TYPE_IBCMD_CLI,
        target_entity="Infobase" if scope == "per_database" else "StandaloneServer",
        status=BatchOperation.STATUS_PENDING,
        payload=payload,
        config={
            "batch_size": 1,
            "timeout_seconds": timeout_seconds,
            "retry_count": 1,
            "priority": "normal",
        },
        total_tasks=1 if scope == "global" else len(databases),
        created_by=request.user.username if request.user else "system",
        metadata=metadata,
    )
    if scope == "global":
        Task.objects.create(
            id=str(uuid.uuid4()),
            batch_operation=batch_operation,
            database=None,
            status=Task.STATUS_PENDING,
        )
    else:
        batch_operation.target_databases.set(databases)
        Task.objects.bulk_create([
            Task(
                id=str(uuid.uuid4()),
                batch_operation=batch_operation,
                database=db,
                status=Task.STATUS_PENDING,
            )
            for db in databases
        ])
    enqueue_res = OperationsService.enqueue_operation(operation_id)
    if not enqueue_res.success:
        enqueue_error_code = getattr(enqueue_res, "error_code", None) or "ENQUEUE_FAILED"
        if enqueue_res.status == "duplicate":
            batch_operation.status = BatchOperation.STATUS_CANCELLED
            batch_operation.metadata["error"] = enqueue_res.error or "duplicate"
            batch_operation.save(update_fields=["status", "metadata", "updated_at"])
            return Response({
                "success": False,
                "error": {"code": "DUPLICATE", "message": enqueue_res.error or "duplicate"},
            }, status=409)
        if enqueue_error_code == "REDIS_ERROR":
            batch_operation.status = BatchOperation.STATUS_FAILED
            batch_operation.metadata["error"] = "REDIS_ERROR"
            batch_operation.save(update_fields=["status", "metadata", "updated_at"])
            return Response(
                {"success": False, "error": {"code": "REDIS_ERROR", "message": "Redis is unavailable"}},
                status=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        batch_operation.status = BatchOperation.STATUS_FAILED
        batch_operation.metadata["error"] = enqueue_res.error or "enqueue_failed"
        batch_operation.save(update_fields=["status", "metadata", "updated_at"])
        return Response({
            "success": False,
            "error": {"code": "ENQUEUE_FAILED", "message": "Failed to queue operation"},
        }, status=500)
    return Response({
        "operation_id": operation_id,
        "status": "queued",
        "total_tasks": batch_operation.total_tasks,
        "message": f"ibcmd_cli queued: {command_id}",
    }, status=http_status.HTTP_202_ACCEPTED)
