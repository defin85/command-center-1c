from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from django.db import transaction
from django.db.models import Q, QuerySet

from apps.operations.driver_catalog_effective import (
    get_effective_driver_catalog,
    resolve_driver_catalog_versions,
)
from apps.templates.models import (
    OperationDefinition,
    OperationExposure,
    OperationMigrationIssue,
)

logger = logging.getLogger(__name__)

_SET_FLAGS_CAPABILITY = "extensions.set_flags"
_SUPPORTED_EXECUTOR_KINDS = {
    OperationDefinition.EXECUTOR_IBCMD_CLI,
    OperationDefinition.EXECUTOR_DESIGNER_CLI,
    OperationDefinition.EXECUTOR_WORKFLOW,
}
_CANONICAL_DRIVER_BY_KIND = {
    OperationDefinition.EXECUTOR_IBCMD_CLI: "ibcmd",
    OperationDefinition.EXECUTOR_DESIGNER_CLI: "cli",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key in sorted(value.keys()):
            normalized = _clean_json(value[key])
            if normalized is None:
                continue
            out[str(key)] = normalized
        return out
    if isinstance(value, list):
        return [_clean_json(v) for v in value]
    return value


def _fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(_clean_json(payload)).encode("utf-8")).hexdigest()


def normalize_executor_kind(raw_kind: Any) -> str:
    kind = str(raw_kind or "").strip().lower()
    if kind in _SUPPORTED_EXECUTOR_KINDS:
        return kind
    return OperationDefinition.EXECUTOR_WORKFLOW


def canonical_driver_for_executor_kind(raw_kind: Any) -> str | None:
    return _CANONICAL_DRIVER_BY_KIND.get(normalize_executor_kind(raw_kind))


def _validate_template_runtime_contract(
    *,
    definition_payload: dict[str, Any],
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []

    operation_type = str(definition_payload.get("operation_type") or "").strip()
    if not operation_type:
        errors.append(
            {
                "path": "definition.executor_payload.operation_type",
                "code": "REQUIRED",
                "message": "operation_type is required",
            }
        )

    template_data = definition_payload.get("template_data")
    if template_data is None:
        errors.append(
            {
                "path": "definition.executor_payload.template_data",
                "code": "REQUIRED",
                "message": "template_data is required",
            }
        )
    elif not isinstance(template_data, dict):
        errors.append(
            {
                "path": "definition.executor_payload.template_data",
                "code": "INVALID_TYPE",
                "message": "template_data must be an object",
            }
        )

    if operation_type:
        try:
            from apps.templates.registry import get_registry
            from apps.templates.registry.bootstrap import ensure_registry_populated

            registry = get_registry()
            if not registry.get_all():
                ensure_registry_populated()

            if not registry.get_all():
                errors.append(
                    {
                        "path": "definition.executor_payload.operation_type",
                        "code": "REGISTRY_UNAVAILABLE",
                        "message": "operation registry is empty",
                    }
                )
            elif not registry.is_valid(operation_type):
                errors.append(
                    {
                        "path": "definition.executor_payload.operation_type",
                        "code": "UNSUPPORTED_OPERATION_TYPE",
                        "message": f"unsupported operation_type: {operation_type}",
                    }
                )
        except Exception:
            logger.exception(
                "operation_catalog_service: failed to validate operation_type against registry",
                extra={"operation_type": operation_type},
            )
            errors.append(
                {
                    "path": "definition.executor_payload.operation_type",
                    "code": "REGISTRY_UNAVAILABLE",
                    "message": "operation registry is unavailable",
                }
            )

    return errors


def normalize_executor_payload(
    *,
    executor_kind: Any,
    executor_payload: dict[str, Any],
) -> tuple[str, dict[str, Any], list[dict[str, str]]]:
    normalized_kind = normalize_executor_kind(executor_kind)
    normalized_payload = _clean_json(executor_payload if isinstance(executor_payload, dict) else {})
    errors: list[dict[str, str]] = []

    payload_kind = str(normalized_payload.get("kind") or "").strip().lower()
    if payload_kind and payload_kind != normalized_kind:
        errors.append(
            {
                "path": "definition.executor_payload.kind",
                "code": "KIND_MISMATCH",
                "message": f"executor_payload.kind={payload_kind} conflicts with executor_kind={normalized_kind}",
            }
        )

    normalized_payload["kind"] = normalized_kind
    expected_driver = canonical_driver_for_executor_kind(normalized_kind)
    payload_driver = str(normalized_payload.get("driver") or "").strip().lower()

    if expected_driver is None:
        if payload_driver:
            errors.append(
                {
                    "path": "definition.executor_payload.driver",
                    "code": "DRIVER_NOT_ALLOWED",
                    "message": f"driver is not allowed for executor kind: {normalized_kind}",
                }
            )
        normalized_payload.pop("driver", None)
    else:
        if payload_driver and payload_driver != expected_driver:
            errors.append(
                {
                    "path": "definition.executor_payload.driver",
                    "code": "DRIVER_KIND_MISMATCH",
                    "message": f"driver={payload_driver} conflicts with executor kind {normalized_kind} (expected {expected_driver})",
                }
            )
        normalized_payload["driver"] = expected_driver

    return normalized_kind, normalized_payload, errors


def build_template_definition_payload(*, operation_type: str, target_entity: str, template_data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    payload = {
        "operation_type": str(operation_type or "").strip(),
        "target_entity": str(target_entity or "").strip(),
        "template_data": template_data if isinstance(template_data, dict) else {},
    }
    return normalize_executor_kind(operation_type), payload


def resolve_definition(
    *,
    tenant_scope: str,
    executor_kind: str,
    executor_payload: dict[str, Any],
    contract_version: int = 1,
) -> tuple[OperationDefinition, bool]:
    normalized_kind, normalized_payload, _errors = normalize_executor_payload(
        executor_kind=executor_kind,
        executor_payload=executor_payload,
    )
    fp = _fingerprint(normalized_payload)
    definition, created = OperationDefinition.objects.get_or_create(
        tenant_scope=tenant_scope,
        fingerprint=fp,
        defaults={
            "executor_kind": normalized_kind,
            "executor_payload": normalized_payload,
            "contract_version": max(1, int(contract_version or 1)),
            "status": OperationDefinition.STATUS_ACTIVE,
        },
    )
    if not created:
        changed = False
        desired_kind = normalized_kind
        if definition.executor_kind != desired_kind:
            definition.executor_kind = desired_kind
            changed = True
        if definition.executor_payload != normalized_payload:
            definition.executor_payload = normalized_payload
            changed = True
        if changed:
            definition.save(update_fields=["executor_kind", "executor_payload", "updated_at"])
    return definition, created


def resolve_exposure(
    *,
    definition: OperationDefinition,
    surface: str,
    alias: str,
    tenant_id: str | None,
    label: str,
    description: str,
    is_active: bool,
    capability: str,
    contexts: list[str],
    display_order: int,
    capability_config: dict[str, Any],
    status: str,
) -> tuple[OperationExposure, bool]:
    qs = OperationExposure.objects.select_related("definition").filter(surface=surface, alias=alias)
    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)
    else:
        qs = qs.filter(tenant__isnull=True)
    exposure = qs.first()
    if exposure is None:
        exposure = OperationExposure.objects.create(
            definition=definition,
            surface=surface,
            alias=alias,
            tenant_id=tenant_id,
            label=label,
            description=description,
            is_active=bool(is_active),
            capability=str(capability or "").strip(),
            contexts=[str(v) for v in contexts if isinstance(v, str)],
            display_order=int(display_order),
            capability_config=_clean_json(capability_config),
            status=status,
        )
        return exposure, True

    exposure.definition = definition
    exposure.label = label
    exposure.description = description
    exposure.is_active = bool(is_active)
    exposure.capability = str(capability or "").strip()
    exposure.contexts = [str(v) for v in contexts if isinstance(v, str)]
    exposure.display_order = int(display_order)
    exposure.capability_config = _clean_json(capability_config)
    exposure.status = status
    exposure.save(
        update_fields=[
            "definition",
            "label",
            "description",
            "is_active",
            "capability",
            "contexts",
            "display_order",
            "capability_config",
            "status",
            "updated_at",
        ]
    )
    return exposure, False


def _commands_by_driver(driver: str, cache: dict[str, dict[str, Any] | None]) -> dict[str, Any] | None:
    key = str(driver or "").strip().lower()
    if not key:
        return None
    if key in cache:
        return cache[key]
    try:
        resolved = resolve_driver_catalog_versions(key)
        if resolved.base_version is None:
            cache[key] = None
            return None
        effective = get_effective_driver_catalog(
            driver=key,
            base_version=resolved.base_version,
            overrides_version=resolved.overrides_version,
        )
        catalog = effective.catalog if isinstance(effective.catalog, dict) else {}
        commands = catalog.get("commands_by_id")
        cache[key] = commands if isinstance(commands, dict) else None
    except Exception:
        logger.exception("operation_catalog_service: failed to resolve commands", extra={"driver": key})
        cache[key] = None
    return cache[key]


def validate_set_flags_binding(
    *,
    executor_kind: str | None,
    definition_payload: dict[str, Any],
    capability_config: dict[str, Any],
    commands_cache: dict[str, dict[str, Any] | None] | None = None,
) -> list[dict[str, str]]:
    cache = commands_cache if commands_cache is not None else {}
    errors: list[dict[str, str]] = []

    definition_fixed = definition_payload.get("fixed")
    if isinstance(definition_fixed, dict) and "apply_mask" in definition_fixed:
        errors.append(
            {
                "path": "definition.executor_payload.fixed.apply_mask",
                "code": "FORBIDDEN",
                "message": "apply_mask preset is not allowed for extensions.set_flags; use runtime request/workflow input",
            }
        )
    if "apply_mask" in capability_config:
        errors.append(
            {
                "path": "capability_config.apply_mask",
                "code": "FORBIDDEN",
                "message": "apply_mask preset is not allowed for extensions.set_flags; use runtime request/workflow input",
            }
        )
    cfg_fixed = capability_config.get("fixed")
    if isinstance(cfg_fixed, dict) and "apply_mask" in cfg_fixed:
        errors.append(
            {
                "path": "capability_config.fixed.apply_mask",
                "code": "FORBIDDEN",
                "message": "apply_mask preset is not allowed for extensions.set_flags; use runtime request/workflow input",
            }
        )
    if errors:
        return errors

    target_binding = capability_config.get("target_binding")
    if not isinstance(target_binding, dict):
        errors.append({"path": "capability_config.target_binding", "code": "REQUIRED", "message": "target_binding is required"})
        return errors

    bound_param = str(target_binding.get("extension_name_param") or "").strip()
    if not bound_param:
        errors.append(
            {
                "path": "capability_config.target_binding.extension_name_param",
                "code": "REQUIRED",
                "message": "extension_name_param is required",
            }
        )
        return errors

    resolved_kind = normalize_executor_kind(definition_payload.get("kind") or executor_kind)
    driver = str(definition_payload.get("driver") or "").strip().lower()
    if not driver:
        driver = canonical_driver_for_executor_kind(resolved_kind) or ""
    command_id = str(definition_payload.get("command_id") or "").strip()
    if not driver or not command_id:
        errors.append(
            {
                "path": "definition.executor_payload",
                "code": "INVALID_EXECUTOR",
                "message": "driver and command_id are required for set_flags",
            }
        )
        return errors

    commands = _commands_by_driver(driver, cache)
    if not isinstance(commands, dict):
        errors.append(
            {
                "path": "definition.executor_payload.driver",
                "code": "DRIVER_CATALOG_UNAVAILABLE",
                "message": f"driver catalog not available: {driver}",
            }
        )
        return errors

    command = commands.get(command_id)
    if not isinstance(command, dict):
        errors.append(
            {
                "path": "definition.executor_payload.command_id",
                "code": "UNKNOWN_COMMAND",
                "message": f"unknown command_id: {command_id}",
            }
        )
        return errors

    params_by_name = command.get("params_by_name")
    if not isinstance(params_by_name, dict) or bound_param not in params_by_name:
        errors.append(
            {
                "path": "capability_config.target_binding.extension_name_param",
                "code": "UNKNOWN_PARAM",
                "message": f"bound param not found in command schema: {bound_param}",
            }
        )
    return errors


def validate_exposure_payload(
    *,
    executor_kind: str | None,
    definition_payload: dict[str, Any],
    capability: str,
    capability_config: dict[str, Any],
    commands_cache: dict[str, dict[str, Any] | None] | None = None,
) -> list[dict[str, str]]:
    _normalized_kind, _normalized_payload, contract_errors = normalize_executor_payload(
        executor_kind=executor_kind,
        executor_payload=definition_payload,
    )
    errors: list[dict[str, str]] = []
    if contract_errors:
        errors.extend(contract_errors)

    errors.extend(_validate_template_runtime_contract(definition_payload=_normalized_payload))

    if str(capability or "").strip() == _SET_FLAGS_CAPABILITY:
        errors.extend(
            validate_set_flags_binding(
                executor_kind=executor_kind,
                definition_payload=definition_payload,
                capability_config=capability_config,
                commands_cache=commands_cache,
            )
        )

    return errors


def serialize_template_exposure(exposure: OperationExposure) -> dict[str, Any]:
    payload = exposure.definition.executor_payload if isinstance(exposure.definition.executor_payload, dict) else {}
    return {
        "id": exposure.alias,
        "name": exposure.label,
        "description": exposure.description,
        "operation_type": str(payload.get("operation_type") or ""),
        "target_entity": str(payload.get("target_entity") or ""),
        "template_data": payload.get("template_data") if isinstance(payload.get("template_data"), dict) else {},
        "is_active": exposure.is_active,
        "created_at": exposure.created_at,
        "updated_at": exposure.updated_at,
    }


def list_template_exposures_queryset() -> QuerySet[OperationExposure]:
    return (
        OperationExposure.objects.select_related("definition")
        .filter(surface=OperationExposure.SURFACE_TEMPLATE)
        .order_by("label")
    )


@transaction.atomic
def upsert_template_exposure(
    *,
    template_id: str,
    name: str,
    description: str,
    operation_type: str,
    target_entity: str,
    template_data: dict[str, Any],
    is_active: bool,
) -> tuple[OperationExposure, bool]:
    executor_kind, definition_payload = build_template_definition_payload(
        operation_type=operation_type,
        target_entity=target_entity,
        template_data=template_data,
    )
    definition, _ = resolve_definition(
        tenant_scope="global",
        executor_kind=executor_kind,
        executor_payload=definition_payload,
        contract_version=1,
    )

    status = OperationExposure.STATUS_PUBLISHED if is_active else OperationExposure.STATUS_DRAFT
    exposure, created = resolve_exposure(
        definition=definition,
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias=template_id,
        tenant_id=None,
        label=name,
        description=description,
        is_active=is_active,
        capability=f"templates.{str(operation_type or '').strip() or 'legacy'}",
        contexts=[],
        display_order=0,
        capability_config={},
        status=status,
    )

    return exposure, created


@transaction.atomic
def delete_template_exposure(*, template_id: str) -> OperationExposure | None:
    exposure = (
        OperationExposure.objects.select_related("definition")
        .filter(surface=OperationExposure.SURFACE_TEMPLATE, alias=template_id, tenant__isnull=True)
        .first()
    )
    if exposure is None:
        return None

    definition = exposure.definition
    exposure.delete()
    if not OperationExposure.objects.filter(definition=definition).exists():
        definition.delete()
    return exposure


def list_migration_issues_queryset() -> QuerySet[OperationMigrationIssue]:
    return OperationMigrationIssue.objects.select_related("tenant", "exposure").all().order_by("-created_at")


def list_set_flags_apply_mask_preset_findings(*, statuses: list[str] | None = None) -> list[dict[str, Any]]:
    qs = OperationExposure.objects.select_related("definition", "tenant").filter(
        surface="action_catalog",
        capability=_SET_FLAGS_CAPABILITY,
    )
    if statuses:
        qs = qs.filter(status__in=statuses)

    preset_paths = {
        "definition.executor_payload.fixed.apply_mask",
        "capability_config.apply_mask",
        "capability_config.fixed.apply_mask",
    }
    findings: list[dict[str, Any]] = []
    for exposure in qs:
        definition_payload = exposure.definition.executor_payload if isinstance(exposure.definition.executor_payload, dict) else {}
        capability_config = exposure.capability_config if isinstance(exposure.capability_config, dict) else {}
        errors = validate_set_flags_binding(
            executor_kind=exposure.definition.executor_kind,
            definition_payload=definition_payload,
            capability_config=capability_config,
            commands_cache=None,
        )
        preset_errors = [err for err in errors if str(err.get("path") or "") in preset_paths]
        if not preset_errors:
            continue
        findings.append(
            {
                "exposure_id": str(exposure.id),
                "definition_id": str(exposure.definition_id),
                "alias": exposure.alias,
                "label": exposure.label,
                "tenant_id": str(exposure.tenant_id) if exposure.tenant_id else None,
                "status": exposure.status,
                "is_active": bool(exposure.is_active),
                "paths": [str(err.get("path") or "") for err in preset_errors],
                "messages": [str(err.get("message") or "") for err in preset_errors],
            }
        )
    findings.sort(
        key=lambda item: (
            str(item.get("tenant_id") or ""),
            str(item.get("status") or ""),
            str(item.get("alias") or ""),
        )
    )
    return findings


def filter_exposures_queryset(
    *,
    surface: str | None,
    tenant_id: str | None,
    capability: str | None,
    status: str | None,
    alias: str | None,
) -> QuerySet[OperationExposure]:
    qs = OperationExposure.objects.select_related("definition").all()
    if surface:
        qs = qs.filter(surface=surface)
    if tenant_id:
        qs = qs.filter(Q(tenant_id=tenant_id) | Q(tenant__isnull=True))
    if capability:
        qs = qs.filter(capability=capability)
    if status:
        qs = qs.filter(status=status)
    if alias:
        qs = qs.filter(alias=alias)
    return qs.order_by("surface", "display_order", "label")
