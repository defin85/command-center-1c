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

from apps.core import permission_codes as perms
from apps.databases.extensions_snapshot import normalize_extensions_snapshot
from apps.databases.models import Database, DatabaseExtensionsSnapshot, PermissionLevel
from apps.databases.services import PermissionService
from apps.mappings.extensions_inventory import build_canonical_extensions_inventory
from apps.mappings.models import TenantMappingSpec
from apps.operations.models import ExtensionsPlan
from apps.operations.waiter import OperationTimeoutError, ResultWaiter
from apps.operations.snapshot_hash import canonical_json_hash
from apps.tenancy.authentication import TENANT_HEADER
from apps.templates.operation_catalog_service import (
    build_effective_action_catalog_payload,
    validate_set_flags_binding,
)

from .ui.preview import _preview_ibcmd_cli
from .operations.execute_ibcmd_cli_impl import _execute_ibcmd_cli_validated


def _normalize_action_id(value: Any) -> str:
    return str(value or "").strip()


def _iter_extensions_actions(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    extensions = catalog.get("extensions")
    if not isinstance(extensions, dict):
        return []
    actions = extensions.get("actions")
    if not isinstance(actions, list):
        return []
    out: list[dict[str, Any]] = []
    for action in actions:
        if isinstance(action, dict):
            out.append(action)
    return out


def _match_extensions_action_capability(action: dict[str, Any], capability: str) -> bool:
    action_capability = action.get("capability")
    if isinstance(action_capability, str) and action_capability.strip():
        return action_capability.strip() == capability
    # Legacy fallback: reserved capabilities were stored in `action.id`.
    return _normalize_action_id(action.get("id")) == capability


def _resolve_extensions_action_from_catalog(
    *,
    catalog: dict[str, Any],
    capability: str | None,
    action_id: str | None,
) -> tuple[dict[str, Any] | None, Response | None]:
    actions = _iter_extensions_actions(catalog)

    normalized_action_id = _normalize_action_id(action_id)
    normalized_capability = str(capability or "").strip()

    if normalized_action_id:
        for action in actions:
            if _normalize_action_id(action.get("id")) == normalized_action_id:
                return action, None
        return None, Response(
            {"success": False, "error": {"code": "MISSING_ACTION", "message": f"Action not found: {normalized_action_id}"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    if not normalized_capability:
        normalized_capability = "extensions.sync"

    matched = [a for a in actions if _match_extensions_action_capability(a, normalized_capability)]
    if not matched:
        return None, Response(
            {"success": False, "error": {"code": "MISSING_ACTION", "message": f"{normalized_capability} is not configured"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )
    if len(matched) > 1:
        candidates = sorted([_normalize_action_id(a.get("id")) for a in matched if _normalize_action_id(a.get("id"))])
        return None, Response(
            {
                "success": False,
                "error": {
                    "code": "AMBIGUOUS_ACTION",
                    "message": f"Multiple actions match capability: {normalized_capability}. Specify action_id.",
                    "candidates": candidates,
                },
            },
            status=http_status.HTTP_400_BAD_REQUEST,
        )
    return matched[0], None


def _permission_denied(message: str):
    return Response(
        {"success": False, "error": {"code": "PERMISSION_DENIED", "message": message}},
        status=http_status.HTTP_403_FORBIDDEN,
    )


def _is_staff(user) -> bool:
    return bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))


def _has_explicit_tenant_header(request) -> bool:
    raw = None
    try:
        raw = request.META.get(TENANT_HEADER)
    except Exception:
        raw = None
    if raw is None and getattr(request, "_request", None) is not None:
        try:
            raw = request._request.META.get(TENANT_HEADER)
        except Exception:
            raw = None
    return bool(str(raw).strip()) if raw is not None else False


def _require_tenant_header_for_staff_mutating(request) -> Response | None:
    if _is_staff(request.user) and not _has_explicit_tenant_header(request):
        return Response(
            {"success": False, "error": {"code": "TENANT_CONTEXT_REQUIRED", "message": "X-CC1C-Tenant-ID is required"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )
    return None


def _require_manage_permission(request) -> Response | None:
    # set_flags is a governance / mutating action: require manage_database permission.
    if not request.user.has_perm(perms.PERM_DATABASES_MANAGE_DATABASE):
        return Response(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "Permission denied"}},
            status=http_status.HTTP_403_FORBIDDEN,
        )
    return None


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


def _get_extensions_action_from_catalog(catalog: dict[str, Any], capability: str) -> dict[str, Any] | None:
    # Backward-compatible helper for legacy call sites (prefer _resolve_extensions_action_from_catalog).
    actions = _iter_extensions_actions(catalog)
    matched = [a for a in actions if _match_extensions_action_capability(a, capability)]
    if len(matched) == 1:
        return matched[0]
    return None


def _get_sync_executor_or_error(*, request, tenant_id: str) -> tuple[dict[str, Any] | None, Response | None]:
    catalog = build_effective_action_catalog_payload(tenant_id=tenant_id)
    action, err = _resolve_extensions_action_from_catalog(catalog=catalog, capability="extensions.sync", action_id=None)
    if err:
        return None, err
    executor = action.get("executor") if isinstance(action.get("executor"), dict) else None
    if not isinstance(executor, dict):
        return None, Response(
            {"success": False, "error": {"code": "MISSING_ACTION", "message": "extensions.sync is not configured"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )
    if executor.get("kind") != "ibcmd_cli":
        return None, Response(
            {"success": False, "error": {"code": "NOT_SUPPORTED", "message": "extensions.sync must use ibcmd_cli executor"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )
    if str(executor.get("driver") or "ibcmd").strip().lower() != "ibcmd":
        return None, Response(
            {"success": False, "error": {"code": "NOT_SUPPORTED", "message": "extensions.sync must use ibcmd driver"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )
    command_id = str(executor.get("command_id") or "").strip()
    if not command_id:
        return None, Response(
            {"success": False, "error": {"code": "INVALID_PARAMETER", "message": "extensions.sync command_id is required"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )
    return executor, None

_SET_FLAGS_KEYS: tuple[str, str, str] = ("active", "safe_mode", "unsafe_action_protection")


class _SetFlagsTripleSerializer(serializers.Serializer):
    active = serializers.BooleanField(required=True)
    safe_mode = serializers.BooleanField(required=True)
    unsafe_action_protection = serializers.BooleanField(required=True)


class _SetFlagsApplyMaskSerializer(_SetFlagsTripleSerializer):
    pass


class _SetFlagsValuesSerializer(_SetFlagsTripleSerializer):
    pass


class ExtensionsPlanRequestSerializer(serializers.Serializer):
    database_ids = serializers.ListField(child=serializers.UUIDField(format="hex_verbose"), min_length=1, max_length=500)
    capability = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    action_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    extension_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    # NOTE: fields below are only supported for capability `extensions.set_flags`.
    flags_values = _SetFlagsValuesSerializer(required=False)
    apply_mask = _SetFlagsApplyMaskSerializer(required=False)


def _normalize_set_flags_apply_mask(raw: Any) -> tuple[dict[str, bool] | None, str | None]:
    if raw is None:
        return None, None
    if not isinstance(raw, dict):
        return None, "apply_mask must be an object"
    unknown = sorted([str(k) for k in raw.keys() if str(k) not in _SET_FLAGS_KEYS])
    if unknown:
        return None, f"apply_mask has unknown keys: {unknown}"
    mask: dict[str, bool] = {}
    for k in _SET_FLAGS_KEYS:
        v = raw.get(k)
        if not isinstance(v, bool):
            return None, f"apply_mask.{k} must be a boolean"
        mask[k] = v
    if not any(mask.values()):
        return None, "apply_mask must select at least one flag"
    return mask, None


def _normalize_set_flags_values(raw: Any) -> tuple[dict[str, bool] | None, str | None]:
    if raw is None:
        return None, None
    if not isinstance(raw, dict):
        return None, "flags_values must be an object"
    unknown = sorted([str(k) for k in raw.keys() if str(k) not in _SET_FLAGS_KEYS])
    if unknown:
        return None, f"flags_values has unknown keys: {unknown}"
    values: dict[str, bool] = {}
    for k in _SET_FLAGS_KEYS:
        v = raw.get(k)
        if not isinstance(v, bool):
            return None, f"flags_values.{k} must be a boolean"
        values[k] = v
    return values, None


def _resolve_set_flags_runtime_value(value: Any, *, flags_values: dict[str, bool]) -> tuple[Any, str | None]:
    if not isinstance(value, str):
        return value, None
    token = value.strip()
    if "$policy." in token:
        return None, "set_flags does not support $policy.* tokens; use $flags.* tokens"
    if token == "$flags.active":
        return flags_values["active"], None
    if token == "$flags.safe_mode":
        return flags_values["safe_mode"], None
    if token == "$flags.unsafe_action_protection":
        return flags_values["unsafe_action_protection"], None
    return value, None


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
@permission_classes([IsAuthenticated])
def extensions_plan(request):
    if not request.user.has_perm(perms.PERM_DATABASES_VIEW_DATABASE):
        return _permission_denied("You do not have permission to view databases.")

    tenant_id = str(request.tenant_id)

    serializer = ExtensionsPlanRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    database_ids = [str(x) for x in serializer.validated_data["database_ids"]]
    capability_raw = str(serializer.validated_data.get("capability") or "").strip()
    action_id = _normalize_action_id(serializer.validated_data.get("action_id"))
    extension_name = str(serializer.validated_data.get("extension_name") or "").strip()
    flags_values_raw = serializer.validated_data.get("flags_values")
    apply_mask_raw = serializer.validated_data.get("apply_mask")

    # NOTE: capability can be omitted when action_id is provided.
    if capability_raw and capability_raw not in {"extensions.sync", "extensions.set_flags"}:
        return Response(
            {"success": False, "error": {"code": "INVALID_PARAMETER", "message": f"Unsupported capability: {capability_raw}"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    if capability_raw == "extensions.set_flags":
        denied = _require_manage_permission(request)
        if denied:
            return denied
        denied = _require_tenant_header_for_staff_mutating(request)
        if denied:
            return denied
        if not action_id:
            return Response(
                {"success": False, "error": {"code": "MISSING_PARAMETER", "message": "action_id is required"}},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

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

    catalog = build_effective_action_catalog_payload(tenant_id=tenant_id)
    action, err = _resolve_extensions_action_from_catalog(
        catalog=catalog,
        capability=capability_raw or None,
        action_id=action_id or None,
    )
    if err:
        return err

    capability = str(action.get("capability") or "").strip()
    if not capability:
        # Legacy reserved actions used `id == capability`.
        if capability_raw:
            capability = capability_raw
        elif not action_id:
            capability = "extensions.sync"
    if capability_raw and capability != capability_raw:
        return Response(
            {
                "success": False,
                "error": {"code": "INVALID_PARAMETER", "message": f"capability mismatch for action_id: {capability_raw} != {capability}"},
            },
            status=http_status.HTTP_400_BAD_REQUEST,
        )
    if capability not in {"extensions.sync", "extensions.set_flags"}:
        return Response(
            {"success": False, "error": {"code": "CONFIGURATION_ERROR", "message": f"Unsupported action capability: {capability}"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    if capability == "extensions.set_flags" and capability_raw != "extensions.set_flags":
        denied = _require_manage_permission(request)
        if denied:
            return denied
        denied = _require_tenant_header_for_staff_mutating(request)
        if denied:
            return denied

    executor = action.get("executor") if isinstance(action.get("executor"), dict) else None
    if not isinstance(executor, dict):
        return Response(
            {"success": False, "error": {"code": "MISSING_ACTION", "message": f"{capability} is not configured"}},
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

    executor_for_plan = dict(executor)
    flags_values: dict[str, bool] | None = None

    if capability == "extensions.set_flags":
        if not action_id:
            return Response(
                {"success": False, "error": {"code": "MISSING_PARAMETER", "message": "action_id is required"}},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        apply_mask, mask_err = _normalize_set_flags_apply_mask(apply_mask_raw)
        if mask_err:
            return Response(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "message": mask_err}},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        if apply_mask_raw is None or apply_mask is None:
            return Response(
                {"success": False, "error": {"code": "MISSING_PARAMETER", "message": "apply_mask is required"}},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        flags_values, flags_err = _normalize_set_flags_values(flags_values_raw)
        if flags_err:
            return Response(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "message": flags_err}},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        if flags_values_raw is None or flags_values is None:
            return Response(
                {"success": False, "error": {"code": "MISSING_PARAMETER", "message": "flags_values is required"}},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        if not extension_name:
            return Response(
                {"success": False, "error": {"code": "MISSING_PARAMETER", "message": "extension_name is required"}},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        fixed = executor.get("fixed") if isinstance(executor.get("fixed"), dict) else {}
        if isinstance(fixed, dict) and "apply_mask" in fixed:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "CONFIGURATION_ERROR",
                        "message": "extensions.set_flags does not allow executor.fixed.apply_mask preset",
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        target_binding = executor.get("target_binding") if isinstance(executor.get("target_binding"), dict) else {}
        binding_errors = validate_set_flags_binding(
            definition_payload=executor,
            capability_config={"target_binding": target_binding},
        )
        if binding_errors:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "CONFIGURATION_ERROR",
                        "message": binding_errors[0]["message"],
                        "details": binding_errors,
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        bound_param = str(target_binding.get("extension_name_param") or "").strip()

        selective_apply = not all(bool(apply_mask.get(k)) for k in _SET_FLAGS_KEYS)

        if not isinstance(params, dict):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "CONFIGURATION_ERROR",
                        "message": "set_flags requires params-based executor",
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        params = dict(params)

        missing = [k for k in _SET_FLAGS_KEYS if bool(apply_mask.get(k)) and str(k) not in params]
        if missing:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "CONFIGURATION_ERROR",
                        "message": f"Selective apply requires params-based executor for set_flags (missing params: {missing})",
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        invalid_runtime_tokens: list[str] = []
        for k in _SET_FLAGS_KEYS:
            if not bool(apply_mask.get(k)):
                continue
            expected = f"$flags.{k}"
            actual = str(params.get(k) or "").strip()
            if actual != expected:
                invalid_runtime_tokens.append(k)
        if invalid_runtime_tokens:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "CONFIGURATION_ERROR",
                        "message": f"Selected flags must be mapped via $flags.* tokens in params: {invalid_runtime_tokens}",
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        forbidden_args = {"--active", "--safe-mode", "--unsafe-action-protection"}
        if selective_apply:
            for token in additional_args or []:
                if str(token) in forbidden_args:
                    return Response(
                        {
                            "success": False,
                            "error": {
                                "code": "CONFIGURATION_ERROR",
                                "message": "Selective apply is not supported when set_flags uses flag switches in additional_args",
                            },
                        },
                        status=http_status.HTTP_400_BAD_REQUEST,
                    )

        # Remove unselected flags from params so executor cannot modify them.
        for k in _SET_FLAGS_KEYS:
            if not bool(apply_mask.get(k)):
                params.pop(k, None)

        # Explicit contract binding: extension_name is set only through bound command param.
        params[bound_param] = extension_name

        def _sub(value):
            return _resolve_set_flags_runtime_value(value, flags_values=flags_values)

        resolved_params: dict[str, Any] = {}
        for k, v in (params or {}).items():
            if isinstance(v, list):
                resolved_values: list[Any] = []
                for item in v:
                    resolved, resolve_err = _sub(item)
                    if resolve_err:
                        return Response(
                            {"success": False, "error": {"code": "CONFIGURATION_ERROR", "message": resolve_err}},
                            status=http_status.HTTP_400_BAD_REQUEST,
                        )
                    resolved_values.append(resolved)
                resolved_params[str(k)] = resolved_values
            else:
                resolved, resolve_err = _sub(v)
                if resolve_err:
                    return Response(
                        {"success": False, "error": {"code": "CONFIGURATION_ERROR", "message": resolve_err}},
                        status=http_status.HTTP_400_BAD_REQUEST,
                    )
                resolved_params[str(k)] = resolved
        params = resolved_params

        bad_types: list[str] = []
        for k in _SET_FLAGS_KEYS:
            if not bool(apply_mask.get(k)):
                continue
            if not isinstance(params.get(k), bool):
                bad_types.append(k)
        if bad_types:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": f"Selected flags must resolve to booleans from flags_values: {bad_types}",
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        resolved_args: list[str] = []
        for token in additional_args or []:
            rendered, resolve_err = _sub(str(token))
            if resolve_err:
                return Response(
                    {"success": False, "error": {"code": "CONFIGURATION_ERROR", "message": resolve_err}},
                    status=http_status.HTTP_400_BAD_REQUEST,
                )
            if rendered is None:
                continue
            resolved_args.append(str(rendered))
        additional_args = resolved_args
        executor_for_plan["params"] = params
        executor_for_plan["additional_args"] = additional_args

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
        executor={
            "capability": capability,
            "action_id": str(action.get("id") or "").strip(),
            "extension_name": extension_name if capability == "extensions.set_flags" else None,
            "flags_values": flags_values if capability == "extensions.set_flags" else None,
            "apply_mask": apply_mask if capability == "extensions.set_flags" else None,
            "executor": executor_for_plan,
        },
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
@permission_classes([IsAuthenticated])
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

    plan_executor = plan.executor if isinstance(plan.executor, dict) else {}
    action_capability = str(plan_executor.get("capability") or "extensions.sync").strip() or "extensions.sync"
    extension_name = str(plan_executor.get("extension_name") or "").strip()
    plan_apply_mask_raw = plan_executor.get("apply_mask")
    plan_apply_mask, plan_mask_err = _normalize_set_flags_apply_mask(plan_apply_mask_raw)
    plan_flags_values_raw = plan_executor.get("flags_values")
    plan_flags_values, plan_flags_err = _normalize_set_flags_values(plan_flags_values_raw)
    if plan_mask_err:
        return Response(
            {"success": False, "error": {"code": "PLAN_INVALID", "message": plan_mask_err}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )
    if plan_flags_err:
        return Response(
            {"success": False, "error": {"code": "PLAN_INVALID", "message": plan_flags_err}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    if action_capability == "extensions.set_flags":
        denied = _require_manage_permission(request)
        if denied:
            return denied
        denied = _require_tenant_header_for_staff_mutating(request)
        if denied:
            return denied
        if plan_apply_mask is None:
            return Response(
                {"success": False, "error": {"code": "PLAN_INVALID", "message": "set_flags plan requires apply_mask"}},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        if plan_flags_values is None:
            return Response(
                {"success": False, "error": {"code": "PLAN_INVALID", "message": "set_flags plan requires flags_values"}},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

    catalog = None
    if strict or action_capability == "extensions.set_flags":
        catalog = build_effective_action_catalog_payload(tenant_id=tenant_id)

    if strict:
        list_action, list_err = _resolve_extensions_action_from_catalog(catalog=catalog, capability="extensions.list", action_id=None)
        if list_err:
            return list_err
        list_executor = list_action.get("executor") if isinstance(list_action.get("executor"), dict) else None
        if not isinstance(list_executor, dict) or list_executor.get("kind") != "ibcmd_cli":
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

        preflight_resp = _execute_ibcmd_cli_validated(
            request,
            preflight,
            metadata_overrides={
                "snapshot_kinds": ["extensions"],
                "action_capability": "extensions.list",
                "snapshot_source": "extensions_plan_apply",
            },
        )
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

    executor = plan_executor.get("executor") if isinstance(plan_executor, dict) else None
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

    metadata_overrides: dict[str, Any] = {
        "action_capability": action_capability,
        "snapshot_source": "extensions_plan_apply",
    }
    if action_capability == "extensions.sync":
        metadata_overrides["snapshot_kinds"] = ["extensions"]
    elif action_capability == "extensions.set_flags":
        # For set_flags we rely on post-completion extensions.sync to refresh snapshots; fail closed if not configured.
        sync_executor, denied = _get_sync_executor_or_error(request=request, tenant_id=tenant_id)
        if denied:
            return denied
        metadata_overrides["post_completion_extensions_sync_executor"] = sync_executor
        metadata_overrides["post_completion_extensions_sync"] = True
        metadata_overrides["post_completion_extensions_sync_database_ids"] = database_ids
        if extension_name:
            metadata_overrides["extension_name"] = extension_name

        apply_mask = plan_apply_mask or {}
        selective_apply = not all(bool(apply_mask.get(k)) for k in _SET_FLAGS_KEYS)
        forbidden_args = {"--active", "--safe-mode", "--unsafe-action-protection"}
        if selective_apply:
            for token in (validated_data.get("additional_args") or []):
                if str(token) in forbidden_args:
                    return Response(
                        {
                            "success": False,
                            "error": {
                                "code": "PLAN_INVALID",
                                "message": "Selective apply plan is not supported when set_flags uses flag switches in additional_args",
                            },
                        },
                        status=http_status.HTTP_400_BAD_REQUEST,
                    )
        params_obj = validated_data.get("params")
        if not isinstance(params_obj, dict):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "PLAN_INVALID",
                        "message": "set_flags plan requires params-based executor",
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        params_obj = dict(params_obj)
        for k in _SET_FLAGS_KEYS:
            if not bool(apply_mask.get(k)):
                params_obj.pop(k, None)
        validated_data["params"] = params_obj
        metadata_overrides["apply_mask"] = plan_apply_mask
        metadata_overrides["flags_values"] = plan_flags_values

    return _execute_ibcmd_cli_validated(
        request,
        validated_data,
        metadata_overrides=metadata_overrides,
    )
