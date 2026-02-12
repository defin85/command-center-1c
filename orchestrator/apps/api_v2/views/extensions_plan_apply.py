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
from apps.operations.snapshot_hash import canonical_json_hash
from apps.tenancy.authentication import TENANT_HEADER
from apps.templates.manual_operations import (
    MANUAL_OPERATION_EXTENSIONS_SET_FLAGS,
    MANUAL_OPERATION_EXTENSIONS_SYNC,
    is_supported_manual_operation,
)
from apps.templates.models import ManualOperationTemplateBinding, OperationExposure

from .operations.execute_ibcmd_cli_impl import _execute_ibcmd_cli_validated
from .ui.preview import _preview_ibcmd_cli


_SET_FLAGS_KEYS: tuple[str, str, str] = ("active", "safe_mode", "unsafe_action_protection")
_RESULT_CONTRACT_BY_MANUAL_OPERATION = {
    MANUAL_OPERATION_EXTENSIONS_SYNC: "extensions.inventory.v1",
    MANUAL_OPERATION_EXTENSIONS_SET_FLAGS: "extensions.inventory.v1",
}


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
            {
                "success": False,
                "error": {
                    "code": "TENANT_CONTEXT_REQUIRED",
                    "message": "X-CC1C-Tenant-ID is required",
                },
            },
            status=http_status.HTTP_400_BAD_REQUEST,
        )
    return None


def _require_manage_permission(request) -> Response | None:
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


def _get_published_extensions_mapping_ref(tenant_id: str) -> dict[str, Any] | None:
    row = (
        TenantMappingSpec.objects.filter(
            tenant_id=tenant_id,
            entity_kind=TenantMappingSpec.ENTITY_EXTENSIONS_INVENTORY,
            status=TenantMappingSpec.STATUS_PUBLISHED,
        )
        .only("id", "updated_at")
        .first()
    )
    if row is None:
        return None
    return {
        "mapping_spec_id": str(row.id),
        "mapping_spec_version": row.updated_at.isoformat() if row.updated_at else None,
        "entity_kind": TenantMappingSpec.ENTITY_EXTENSIONS_INVENTORY,
    }


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


def _resolve_template_exposure(*, tenant_id: str, template_id: str) -> OperationExposure | None:
    qs = OperationExposure.objects.select_related("definition").filter(
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias=template_id,
    )
    tenant_row = qs.filter(tenant_id=tenant_id).first()
    if tenant_row is not None:
        return tenant_row
    return qs.filter(tenant__isnull=True).first()


def _resolve_template_for_manual_operation(
    *,
    tenant_id: str,
    manual_operation: str,
    template_id_override: str | None,
) -> tuple[OperationExposure | None, str | None, Response | None]:
    if template_id_override:
        resolved = _resolve_template_exposure(tenant_id=tenant_id, template_id=template_id_override)
        if resolved is None:
            return (
                None,
                None,
                Response(
                    {"success": False, "error": {"code": "INVALID_PARAMETER", "message": "template_id not found"}},
                    status=http_status.HTTP_400_BAD_REQUEST,
                ),
            )
        if str(resolved.capability or "").strip() != manual_operation:
            return (
                None,
                None,
                Response(
                    {
                        "success": False,
                        "error": {
                            "code": "CONFIGURATION_ERROR",
                            "message": "template is not compatible with manual_operation",
                        },
                    },
                    status=http_status.HTTP_400_BAD_REQUEST,
                ),
            )
        return resolved, template_id_override, None

    binding = ManualOperationTemplateBinding.objects.filter(
        tenant_id=tenant_id,
        manual_operation=manual_operation,
    ).first()
    if binding is None:
        return (
            None,
            None,
            Response(
                {
                    "success": False,
                    "error": {
                        "code": "MISSING_TEMPLATE_BINDING",
                        "message": "preferred template binding is not configured",
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            ),
        )

    resolved = _resolve_template_exposure(tenant_id=tenant_id, template_id=binding.template_id)
    if resolved is None:
        return (
            None,
            None,
            Response(
                {
                    "success": False,
                    "error": {
                        "code": "MISSING_TEMPLATE_BINDING",
                        "message": "preferred template binding points to a missing template",
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            ),
        )

    if str(resolved.capability or "").strip() != manual_operation:
        return (
            None,
            None,
            Response(
                {
                    "success": False,
                    "error": {
                        "code": "MISSING_TEMPLATE_BINDING",
                        "message": "preferred template binding is stale",
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            ),
        )

    return resolved, str(binding.template_id), None


def _extract_ibcmd_executor(definition_payload: dict[str, Any]) -> tuple[dict[str, Any] | None, Response | None]:
    kind = str(definition_payload.get("kind") or "").strip()
    if kind != "ibcmd_cli":
        return (
            None,
            Response(
                {
                    "success": False,
                    "error": {
                        "code": "CONFIGURATION_ERROR",
                        "message": "manual operation template must use ibcmd_cli executor",
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            ),
        )

    driver = str(definition_payload.get("driver") or "").strip().lower()
    if driver != "ibcmd":
        return (
            None,
            Response(
                {
                    "success": False,
                    "error": {
                        "code": "CONFIGURATION_ERROR",
                        "message": "manual operation template must use ibcmd driver",
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            ),
        )

    command_id = str(definition_payload.get("command_id") or "").strip()
    if not command_id:
        return (
            None,
            Response(
                {
                    "success": False,
                    "error": {
                        "code": "CONFIGURATION_ERROR",
                        "message": "command_id is required",
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            ),
        )

    return (
        {
            "kind": kind,
            "driver": driver,
            "command_id": command_id,
            "mode": str(definition_payload.get("mode") or "guided").strip().lower() or "guided",
            "params": definition_payload.get("params") if isinstance(definition_payload.get("params"), dict) else {},
            "additional_args": definition_payload.get("additional_args") if isinstance(definition_payload.get("additional_args"), list) else [],
            "stdin": definition_payload.get("stdin") if isinstance(definition_payload.get("stdin"), str) else None,
            "fixed": definition_payload.get("fixed") if isinstance(definition_payload.get("fixed"), dict) else {},
            "template_data": definition_payload.get("template_data") if isinstance(definition_payload.get("template_data"), dict) else {},
        },
        None,
    )


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
    manual_operation = serializers.CharField(required=True)
    template_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    extension_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    flags_values = _SetFlagsValuesSerializer(required=False)
    apply_mask = _SetFlagsApplyMaskSerializer(required=False)


class ExtensionsPlanResponseSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField()
    preconditions = serializers.JSONField()
    execution_plan = serializers.JSONField(required=False)
    bindings = serializers.JSONField(required=False)


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
    if token == "$flags.active":
        return flags_values["active"], None
    if token == "$flags.safe_mode":
        return flags_values["safe_mode"], None
    if token == "$flags.unsafe_action_protection":
        return flags_values["unsafe_action_protection"], None
    if "$policy." in token:
        return None, "set_flags does not support $policy.* tokens; use $flags.* tokens"
    return value, None


def _apply_set_flags_runtime_contract(
    *,
    executor_for_plan: dict[str, Any],
    extension_name: str,
    flags_values: dict[str, bool],
    apply_mask: dict[str, bool],
) -> tuple[dict[str, Any] | None, Response | None]:
    template_data = executor_for_plan.get("template_data") if isinstance(executor_for_plan.get("template_data"), dict) else {}
    target_binding = template_data.get("target_binding") if isinstance(template_data.get("target_binding"), dict) else {}
    bound_param = str(target_binding.get("extension_name_param") or "").strip()
    if not bound_param:
        return (
            None,
            Response(
                {
                    "success": False,
                    "error": {
                        "code": "CONFIGURATION_ERROR",
                        "message": "template_data.target_binding.extension_name_param is required",
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            ),
        )

    params = executor_for_plan.get("params") if isinstance(executor_for_plan.get("params"), dict) else None
    if not isinstance(params, dict):
        return (
            None,
            Response(
                {
                    "success": False,
                    "error": {
                        "code": "CONFIGURATION_ERROR",
                        "message": "set_flags requires params-based executor",
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            ),
        )

    params = dict(params)
    missing = [k for k in _SET_FLAGS_KEYS if bool(apply_mask.get(k)) and str(k) not in params]
    if missing:
        return (
            None,
            Response(
                {
                    "success": False,
                    "error": {
                        "code": "CONFIGURATION_ERROR",
                        "message": f"missing set_flags runtime params: {missing}",
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            ),
        )

    invalid_tokens = []
    for k in _SET_FLAGS_KEYS:
        if not bool(apply_mask.get(k)):
            continue
        expected = f"$flags.{k}"
        actual = str(params.get(k) or "").strip()
        if actual != expected:
            invalid_tokens.append(k)
    if invalid_tokens:
        return (
            None,
            Response(
                {
                    "success": False,
                    "error": {
                        "code": "CONFIGURATION_ERROR",
                        "message": f"selected flags must use $flags.* tokens: {invalid_tokens}",
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            ),
        )

    for k in _SET_FLAGS_KEYS:
        if not bool(apply_mask.get(k)):
            params.pop(k, None)

    params[bound_param] = extension_name

    def _sub(value):
        return _resolve_set_flags_runtime_value(value, flags_values=flags_values)

    resolved_params: dict[str, Any] = {}
    for k, v in params.items():
        if isinstance(v, list):
            resolved_values: list[Any] = []
            for item in v:
                resolved, err = _sub(item)
                if err:
                    return None, Response(
                        {"success": False, "error": {"code": "CONFIGURATION_ERROR", "message": err}},
                        status=http_status.HTTP_400_BAD_REQUEST,
                    )
                resolved_values.append(resolved)
            resolved_params[str(k)] = resolved_values
        else:
            resolved, err = _sub(v)
            if err:
                return None, Response(
                    {"success": False, "error": {"code": "CONFIGURATION_ERROR", "message": err}},
                    status=http_status.HTTP_400_BAD_REQUEST,
                )
            resolved_params[str(k)] = resolved

    bad_types: list[str] = []
    for k in _SET_FLAGS_KEYS:
        if not bool(apply_mask.get(k)):
            continue
        if not isinstance(resolved_params.get(k), bool):
            bad_types.append(k)
    if bad_types:
        return (
            None,
            Response(
                {
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": f"selected flags must resolve to booleans: {bad_types}",
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            ),
        )

    resolved_args: list[str] = []
    for token in executor_for_plan.get("additional_args") or []:
        rendered, err = _sub(str(token))
        if err:
            return None, Response(
                {"success": False, "error": {"code": "CONFIGURATION_ERROR", "message": err}},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        if rendered is None:
            continue
        resolved_args.append(str(rendered))

    out = dict(executor_for_plan)
    out["params"] = resolved_params
    out["additional_args"] = resolved_args
    return out, None


@extend_schema(
    tags=["v2"],
    summary="Extensions manual-operation plan",
    description="Build plan for extensions manual operation (captures base snapshot hashes per database).",
    request=ExtensionsPlanRequestSerializer,
    responses={
        200: ExtensionsPlanResponseSerializer,
        400: OpenApiResponse(description="Validation/configuration error"),
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
    manual_operation = str(serializer.validated_data.get("manual_operation") or "").strip()
    template_id_override = str(serializer.validated_data.get("template_id") or "").strip() or None
    extension_name = str(serializer.validated_data.get("extension_name") or "").strip()
    flags_values_raw = serializer.validated_data.get("flags_values")
    apply_mask_raw = serializer.validated_data.get("apply_mask")

    if not is_supported_manual_operation(manual_operation):
        return Response(
            {
                "success": False,
                "error": {"code": "INVALID_PARAMETER", "message": f"Unsupported manual_operation: {manual_operation}"},
            },
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    if manual_operation == MANUAL_OPERATION_EXTENSIONS_SET_FLAGS:
        denied = _require_manage_permission(request)
        if denied:
            return denied
        denied = _require_tenant_header_for_staff_mutating(request)
        if denied:
            return denied

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

    exposure, resolved_template_id, resolve_error = _resolve_template_for_manual_operation(
        tenant_id=tenant_id,
        manual_operation=manual_operation,
        template_id_override=template_id_override,
    )
    if resolve_error:
        return resolve_error
    assert exposure is not None  # guarded above
    assert resolved_template_id is not None  # guarded above

    definition_payload = exposure.definition.executor_payload if isinstance(exposure.definition.executor_payload, dict) else {}
    executor_for_plan, executor_error = _extract_ibcmd_executor(definition_payload)
    if executor_error:
        return executor_error
    assert executor_for_plan is not None  # guarded above

    flags_values: dict[str, bool] | None = None
    apply_mask: dict[str, bool] | None = None

    if manual_operation == MANUAL_OPERATION_EXTENSIONS_SET_FLAGS:
        if not extension_name:
            return Response(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "extension_name is required"}},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        apply_mask, mask_err = _normalize_set_flags_apply_mask(apply_mask_raw)
        if mask_err:
            return Response(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "message": mask_err}},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        if apply_mask is None:
            return Response(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "apply_mask is required"}},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        flags_values, flags_err = _normalize_set_flags_values(flags_values_raw)
        if flags_err:
            return Response(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "message": flags_err}},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        if flags_values is None:
            return Response(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "flags_values is required"}},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        transformed, transform_error = _apply_set_flags_runtime_contract(
            executor_for_plan=executor_for_plan,
            extension_name=extension_name,
            flags_values=flags_values,
            apply_mask=apply_mask,
        )
        if transform_error:
            return transform_error
        assert transformed is not None
        executor_for_plan = transformed

    preview, err, err_code = _preview_ibcmd_cli(
        user=request.user,
        command_id=str(executor_for_plan.get("command_id") or ""),
        mode=str(executor_for_plan.get("mode") or "guided"),
        connection=None,
        params=executor_for_plan.get("params") if isinstance(executor_for_plan.get("params"), dict) else {},
        additional_args=executor_for_plan.get("additional_args") if isinstance(executor_for_plan.get("additional_args"), list) else [],
        stdin=executor_for_plan.get("stdin") if isinstance(executor_for_plan.get("stdin"), str) else None,
        database_ids=database_ids,
    )
    if err:
        return Response(err, status=err_code or 400)

    mapping_spec_ref = _get_published_extensions_mapping_ref(tenant_id)
    result_contract = _RESULT_CONTRACT_BY_MANUAL_OPERATION.get(manual_operation)

    plan = ExtensionsPlan.objects.create(
        tenant_id=tenant_id,
        created_by=request.user if getattr(request.user, "id", None) else None,
        database_ids=database_ids,
        preconditions=preconditions,
        executor={
            "execution_source": "template_manual_operation",
            "manual_operation": manual_operation,
            "template_id": resolved_template_id,
            "template_exposure_id": str(exposure.id),
            "result_contract": result_contract,
            "mapping_spec_ref": mapping_spec_ref,
            "extension_name": extension_name if manual_operation == MANUAL_OPERATION_EXTENSIONS_SET_FLAGS else None,
            "flags_values": flags_values if manual_operation == MANUAL_OPERATION_EXTENSIONS_SET_FLAGS else None,
            "apply_mask": apply_mask if manual_operation == MANUAL_OPERATION_EXTENSIONS_SET_FLAGS else None,
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


def _plan_is_legacy(plan_executor: dict[str, Any]) -> bool:
    if str(plan_executor.get("execution_source") or "") != "template_manual_operation":
        return True
    if not str(plan_executor.get("manual_operation") or "").strip():
        return True
    if not str(plan_executor.get("template_id") or "").strip():
        return True
    if not str(plan_executor.get("template_exposure_id") or "").strip():
        return True
    for legacy_key in ("action_id", "action_capability", "capability"):
        if legacy_key in plan_executor:
            return True
    return False


@extend_schema(
    tags=["v2"],
    summary="Extensions manual-operation apply",
    description="Apply extensions manual operation for planned databases with drift check.",
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

    plan = ExtensionsPlan.objects.filter(tenant_id=tenant_id, id=plan_id).first()
    if plan is None:
        return Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Plan not found"}},
            status=http_status.HTTP_404_NOT_FOUND,
        )

    plan_executor = plan.executor if isinstance(plan.executor, dict) else {}
    if _plan_is_legacy(plan_executor):
        return Response(
            {
                "success": False,
                "error": {
                    "code": "PLAN_INVALID_LEGACY",
                    "message": "Plan uses legacy action-catalog contract and cannot be applied",
                },
            },
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    manual_operation = str(plan_executor.get("manual_operation") or "").strip()
    template_id = str(plan_executor.get("template_id") or "").strip()
    template_exposure_id = str(plan_executor.get("template_exposure_id") or "").strip()
    if not is_supported_manual_operation(manual_operation):
        return Response(
            {
                "success": False,
                "error": {
                    "code": "PLAN_INVALID_LEGACY",
                    "message": "Plan manual_operation is not supported",
                },
            },
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    if manual_operation == MANUAL_OPERATION_EXTENSIONS_SET_FLAGS:
        denied = _require_manage_permission(request)
        if denied:
            return denied
        denied = _require_tenant_header_for_staff_mutating(request)
        if denied:
            return denied

    database_ids = [str(x) for x in (plan.database_ids or [])]
    accessible = _accessible_databases_qs(request).filter(id__in=database_ids)
    db_by_id = {str(db.id): db for db in accessible}
    missing = [db_id for db_id in database_ids if db_id not in db_by_id]
    if missing:
        return Response(
            {"success": False, "error": {"code": "DATABASE_NOT_FOUND", "message": f"Databases not found: {missing}"}},
            status=http_status.HTTP_404_NOT_FOUND,
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

    executor = plan_executor.get("executor") if isinstance(plan_executor.get("executor"), dict) else None
    if not isinstance(executor, dict):
        return Response(
            {"success": False, "error": {"code": "PLAN_INVALID", "message": "Invalid plan executor"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    if str(executor.get("kind") or "") != "ibcmd_cli":
        return Response(
            {
                "success": False,
                "error": {"code": "PLAN_INVALID", "message": "Only ibcmd_cli executor is supported"},
            },
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
        "execution_source": "template_manual_operation",
        "manual_operation": manual_operation,
        "template_id": template_id,
        "template_exposure_id": template_exposure_id,
        "result_contract": plan_executor.get("result_contract"),
        "mapping_spec_ref": plan_executor.get("mapping_spec_ref"),
        "strict_requested": strict,
        "snapshot_source": "extensions_plan_apply",
    }

    if manual_operation == MANUAL_OPERATION_EXTENSIONS_SYNC:
        metadata_overrides["snapshot_kinds"] = ["extensions"]

    if manual_operation == MANUAL_OPERATION_EXTENSIONS_SET_FLAGS:
        extension_name = str(plan_executor.get("extension_name") or "").strip()
        apply_mask_raw = plan_executor.get("apply_mask")
        flags_values_raw = plan_executor.get("flags_values")
        apply_mask, mask_err = _normalize_set_flags_apply_mask(apply_mask_raw)
        flags_values, flags_err = _normalize_set_flags_values(flags_values_raw)
        if not extension_name or mask_err or flags_err or apply_mask is None or flags_values is None:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "PLAN_INVALID",
                        "message": "set_flags plan is invalid",
                        "details": {
                            "extension_name": extension_name,
                            "apply_mask_error": mask_err,
                            "flags_values_error": flags_err,
                        },
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        metadata_overrides["extension_name"] = extension_name
        metadata_overrides["apply_mask"] = apply_mask
        metadata_overrides["flags_values"] = flags_values

    return _execute_ibcmd_cli_validated(
        request,
        validated_data,
        metadata_overrides=metadata_overrides,
    )
