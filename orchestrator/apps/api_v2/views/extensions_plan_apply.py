"""
Extensions plan/apply endpoints for API v2 (tenant-scoped).
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.api_v2.serializers.common import ErrorResponseSerializer, ExecutionPlanWithBindingsSerializer
from apps.core import permission_codes as perms
from apps.databases.extensions_snapshot import normalize_extensions_snapshot
from apps.databases.models import Database, DatabaseExtensionsSnapshot, PermissionLevel
from apps.databases.services import PermissionService
from apps.mappings.extensions_inventory import build_canonical_extensions_inventory
from apps.mappings.models import TenantMappingSpec
from apps.operations.models import ExtensionsPlan
from apps.operations.waiter import OperationTimeoutError, ResultWaiter
from apps.operations.snapshot_hash import canonical_json_hash
from apps.runtime_settings.action_catalog import UI_ACTION_CATALOG_KEY, ensure_valid_action_catalog
from apps.runtime_settings.effective import get_effective_runtime_setting
from apps.tenancy.permissions import TenantContextPermission

from .ui.preview import _preview_ibcmd_cli
from .operations.execute_ibcmd_cli_impl import _execute_ibcmd_cli_validated


def _permission_denied(message: str):
    return Response(
        {"success": False, "error": {"code": "PERMISSION_DENIED", "message": message}},
        status=http_status.HTTP_403_FORBIDDEN,
    )


def _is_staff(user) -> bool:
    return bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))


def _accessible_databases_qs(request):
    qs = Database.objects.all()
    if not _is_staff(request.user):
        qs = PermissionService.filter_accessible_databases(request.user, qs, PermissionLevel.VIEW)
    return qs


def _get_published_extensions_mapping_spec(tenant_id: str) -> dict:
    spec = TenantMappingSpec.objects.filter(
        tenant_id=tenant_id,
        entity_kind=TenantMappingSpec.ENTITY_EXTENSIONS_INVENTORY,
        status=TenantMappingSpec.STATUS_PUBLISHED,
    ).values_list("spec", flat=True).first()
    return spec if isinstance(spec, dict) else {}


def _compute_extensions_snapshot_precondition(db: Database) -> dict[str, Any]:
    snapshot = {}
    updated_at = None
    try:
        snapshot_obj: DatabaseExtensionsSnapshot = db.extensions_snapshot
        snapshot = normalize_extensions_snapshot(snapshot_obj.snapshot or {})
        updated_at = snapshot_obj.updated_at
    except DatabaseExtensionsSnapshot.DoesNotExist:
        snapshot = {"extensions": [], "raw": {}, "parse_error": None}

    spec = _get_published_extensions_mapping_spec(str(db.tenant_id))
    canonical = build_canonical_extensions_inventory(snapshot, spec)
    h = canonical_json_hash(canonical)
    at = updated_at.isoformat() if updated_at is not None else None
    return {"hash": h, "at": at}


def _get_action_executor_from_catalog(catalog: dict[str, Any], action_id: str) -> dict[str, Any] | None:
    extensions = catalog.get("extensions")
    if not isinstance(extensions, dict):
        return None
    actions = extensions.get("actions")
    if not isinstance(actions, list):
        return None
    for action in actions:
        if not isinstance(action, dict):
            continue
        if str(action.get("id") or "").strip() != action_id:
            continue
        executor = action.get("executor")
        return executor if isinstance(executor, dict) else None
    return None


class ExtensionsPlanRequestSerializer(serializers.Serializer):
    database_ids = serializers.ListField(child=serializers.UUIDField(format="hex_verbose"), min_length=1, max_length=500)


class ExtensionsPlanResponseSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField()
    preconditions = serializers.JSONField()
    execution_plan = serializers.JSONField(required=False)
    bindings = serializers.JSONField(required=False)


@extend_schema(
    tags=["v2"],
    summary="Extensions plan",
    description="Build plan for extensions apply (captures base snapshot hashes per database).",
    request=ExtensionsPlanRequestSerializer,
    responses={
        200: ExtensionsPlanResponseSerializer,
        400: OpenApiResponse(description="Validation error"),
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, TenantContextPermission])
def extensions_plan(request):
    if not request.user.has_perm(perms.PERM_DATABASES_VIEW_DATABASE):
        return _permission_denied("You do not have permission to view databases.")

    tenant_id = str(request.tenant_id)

    serializer = ExtensionsPlanRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    database_ids = [str(x) for x in serializer.validated_data["database_ids"]]

    accessible = _accessible_databases_qs(request).filter(id__in=database_ids)
    db_by_id = {str(db.id): db for db in accessible}
    missing = [db_id for db_id in database_ids if db_id not in db_by_id]
    if missing:
        return Response(
            {"success": False, "error": {"code": "DATABASE_NOT_FOUND", "message": f"Databases not found: {missing}"}},
            status=http_status.HTTP_404_NOT_FOUND,
        )

    preconditions: dict[str, Any] = {}
    for db_id, db in db_by_id.items():
        preconditions[db_id] = _compute_extensions_snapshot_precondition(db)

    raw_catalog = get_effective_runtime_setting(UI_ACTION_CATALOG_KEY, tenant_id).value
    catalog, _errors = ensure_valid_action_catalog(raw_catalog)
    executor = _get_action_executor_from_catalog(catalog, "extensions.sync")
    if executor is None:
        return Response(
            {"success": False, "error": {"code": "MISSING_ACTION", "message": "extensions.sync is not configured"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )
    if executor.get("kind") != "ibcmd_cli":
        return Response(
            {"success": False, "error": {"code": "NOT_SUPPORTED", "message": "Only ibcmd_cli executor is supported"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    command_id = str(executor.get("command_id") or "").strip()
    mode = str(executor.get("mode") or "guided").strip().lower()
    params = executor.get("params") if isinstance(executor.get("params"), dict) else {}
    additional_args = executor.get("additional_args") if isinstance(executor.get("additional_args"), list) else []
    stdin = executor.get("stdin") if isinstance(executor.get("stdin"), str) else None

    preview, err, err_code = _preview_ibcmd_cli(
        user=request.user,
        command_id=command_id,
        mode=mode,
        connection=None,
        params=params,
        additional_args=additional_args,
        stdin=stdin,
        database_ids=database_ids,
    )
    if err:
        return Response(err, status=err_code or 400)

    plan = ExtensionsPlan.objects.create(
        tenant_id=tenant_id,
        created_by=request.user if getattr(request.user, "id", None) else None,
        database_ids=database_ids,
        preconditions=preconditions,
        executor={"action_id": "extensions.sync", "executor": executor},
    )

    return Response(
        {
            "plan_id": plan.id,
            "preconditions": preconditions,
            "execution_plan": (preview or {}).get("execution_plan") if isinstance(preview, dict) else None,
            "bindings": (preview or {}).get("bindings") if isinstance(preview, dict) else None,
        }
    )


class ExtensionsApplyRequestSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField()
    strict = serializers.BooleanField(required=False, default=True)
    preflight_timeout_seconds = serializers.IntegerField(required=False, default=120, min_value=1, max_value=600)


class ExtensionsApplyConflictSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=False)
    error = serializers.JSONField()
    drift = serializers.JSONField()


@extend_schema(
    tags=["v2"],
    summary="Extensions apply",
    description="Apply extensions sync for planned databases with drift check (observed vs base snapshot hash).",
    request=ExtensionsApplyRequestSerializer,
    responses={
        202: serializers.DictField(),
        400: OpenApiResponse(description="Validation error"),
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: OpenApiResponse(description="Not found"),
        409: ExtensionsApplyConflictSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, TenantContextPermission])
def extensions_apply(request):
    if not request.user.has_perm(perms.PERM_DATABASES_VIEW_DATABASE):
        return _permission_denied("You do not have permission to view databases.")

    tenant_id = str(request.tenant_id)

    serializer = ExtensionsApplyRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    plan_id = serializer.validated_data["plan_id"]
    strict = bool(serializer.validated_data.get("strict", True))
    preflight_timeout_seconds = int(serializer.validated_data.get("preflight_timeout_seconds") or 120)

    plan = ExtensionsPlan.objects.filter(tenant_id=tenant_id, id=plan_id).first()
    if plan is None:
        return Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Plan not found"}},
            status=http_status.HTTP_404_NOT_FOUND,
        )

    database_ids = [str(x) for x in (plan.database_ids or [])]
    accessible = _accessible_databases_qs(request).filter(id__in=database_ids)
    db_by_id = {str(db.id): db for db in accessible}
    missing = [db_id for db_id in database_ids if db_id not in db_by_id]
    if missing:
        return Response(
            {"success": False, "error": {"code": "DATABASE_NOT_FOUND", "message": f"Databases not found: {missing}"}},
            status=http_status.HTTP_404_NOT_FOUND,
        )

    if strict:
        raw_catalog = get_effective_runtime_setting(UI_ACTION_CATALOG_KEY, tenant_id).value
        catalog, _errors = ensure_valid_action_catalog(raw_catalog)
        list_executor = _get_action_executor_from_catalog(catalog, "extensions.list")
        if list_executor is None:
            return Response(
                {"success": False, "error": {"code": "MISSING_ACTION", "message": "extensions.list is not configured"}},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        if list_executor.get("kind") != "ibcmd_cli":
            return Response(
                {"success": False, "error": {"code": "NOT_SUPPORTED", "message": "Only ibcmd_cli executor is supported"}},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        fixed = list_executor.get("fixed") if isinstance(list_executor.get("fixed"), dict) else {}
        preflight = {
            "command_id": list_executor.get("command_id"),
            "mode": list_executor.get("mode") or "guided",
            "database_ids": database_ids,
            "params": list_executor.get("params") if isinstance(list_executor.get("params"), dict) else {},
            "additional_args": list_executor.get("additional_args") if isinstance(list_executor.get("additional_args"), list) else [],
            "stdin": list_executor.get("stdin") if isinstance(list_executor.get("stdin"), str) else "",
            "confirm_dangerous": bool(fixed.get("confirm_dangerous") or False),
            "timeout_seconds": int(fixed.get("timeout_seconds") or 300),
        }

        preflight_resp = _execute_ibcmd_cli_validated(request, preflight)
        if getattr(preflight_resp, "status_code", None) != http_status.HTTP_202_ACCEPTED:
            return preflight_resp

        operation_id = None
        try:
            operation_id = (preflight_resp.data or {}).get("operation_id")  # type: ignore[attr-defined]
        except Exception:
            operation_id = None
        if not operation_id:
            return Response(
                {"success": False, "error": {"code": "PREFLIGHT_FAILED", "message": "Preflight did not return operation_id"}},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            result = ResultWaiter.wait(operation_id, timeout_seconds=preflight_timeout_seconds, poll_interval_seconds=0.5)
        except OperationTimeoutError:
            return Response(
                {"success": False, "error": {"code": "PREFLIGHT_TIMEOUT", "message": "Preflight timed out"}, "operation_id": operation_id},
                status=http_status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except Exception as exc:
            return Response(
                {
                    "success": False,
                    "error": {"code": "PREFLIGHT_FAILED", "message": "Preflight failed"},
                    "operation_id": operation_id,
                    "details": str(exc),
                },
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not bool(result.get("success")):
            return Response(
                {
                    "success": False,
                    "error": {"code": "PREFLIGHT_FAILED", "message": "Preflight operation failed"},
                    "operation_id": operation_id,
                    "result": result,
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

    drift: dict[str, Any] = {}
    for db_id, db in db_by_id.items():
        current = _compute_extensions_snapshot_precondition(db)
        base = (plan.preconditions or {}).get(db_id) or {}
        base_hash = base.get("hash")
        if base_hash and current.get("hash") != base_hash:
            drift[db_id] = {"base": base, "current": current}

    if drift:
        return Response(
            {
                "success": False,
                "error": {"code": "DRIFT_CONFLICT", "message": "State changed; re-plan required"},
                "drift": drift,
            },
            status=http_status.HTTP_409_CONFLICT,
        )

    executor = (plan.executor or {}).get("executor") if isinstance(plan.executor, dict) else None
    if not isinstance(executor, dict):
        return Response(
            {"success": False, "error": {"code": "PLAN_INVALID", "message": "Invalid plan executor"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    if executor.get("kind") != "ibcmd_cli":
        return Response(
            {"success": False, "error": {"code": "NOT_SUPPORTED", "message": "Only ibcmd_cli executor is supported"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    fixed = executor.get("fixed") if isinstance(executor.get("fixed"), dict) else {}
    validated_data = {
        "command_id": executor.get("command_id"),
        "mode": executor.get("mode") or "guided",
        "database_ids": database_ids,
        "params": executor.get("params") if isinstance(executor.get("params"), dict) else {},
        "additional_args": executor.get("additional_args") if isinstance(executor.get("additional_args"), list) else [],
        "stdin": executor.get("stdin") if isinstance(executor.get("stdin"), str) else "",
        "confirm_dangerous": bool(fixed.get("confirm_dangerous") or False),
        "timeout_seconds": int(fixed.get("timeout_seconds") or 900),
    }

    return _execute_ibcmd_cli_validated(request, validated_data)
