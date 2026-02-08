from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

from django.db import transaction

from apps.operations.driver_catalog_effective import (
    get_effective_driver_catalog,
    resolve_driver_catalog_versions,
)
from apps.runtime_settings.action_catalog import (
    UI_ACTION_CATALOG_KEY,
    ensure_valid_action_catalog,
)
from apps.runtime_settings.models import RuntimeSetting, TenantRuntimeSettingOverride
from apps.templates.models import (
    OperationDefinition,
    OperationExposure,
    OperationMigrationIssue,
    OperationTemplate,
)

logger = logging.getLogger(__name__)


_SET_FLAGS_CAPABILITY = "extensions.set_flags"
_KNOWN_CAPABILITIES = {"extensions.list", "extensions.sync", "extensions.set_flags"}
_EXECUTOR_KINDS = {
    OperationDefinition.EXECUTOR_IBCMD_CLI,
    OperationDefinition.EXECUTOR_DESIGNER_CLI,
    OperationDefinition.EXECUTOR_WORKFLOW,
}


@dataclass
class BackfillStats:
    templates_processed: int = 0
    actions_processed: int = 0
    definitions_created: int = 0
    definitions_reused: int = 0
    exposures_created: int = 0
    exposures_updated: int = 0
    issues_created: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "templates_processed": self.templates_processed,
            "actions_processed": self.actions_processed,
            "definitions_created": self.definitions_created,
            "definitions_reused": self.definitions_reused,
            "exposures_created": self.exposures_created,
            "exposures_updated": self.exposures_updated,
            "issues_created": self.issues_created,
        }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k in sorted(value.keys()):
            v = _clean_json(value[k])
            if v is None:
                continue
            out[str(k)] = v
        return out
    if isinstance(value, list):
        return [_clean_json(v) for v in value]
    return value


def _normalize_executor_kind(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    if value in _EXECUTOR_KINDS:
        return value
    return OperationDefinition.EXECUTOR_WORKFLOW


def _resolve_capability(raw_action: dict[str, Any]) -> str:
    capability = str(raw_action.get("capability") or "").strip()
    if capability:
        return capability
    action_id = str(raw_action.get("id") or "").strip()
    if action_id in _KNOWN_CAPABILITIES:
        return action_id
    return ""


def _resolve_definition(
    *,
    tenant_scope: str,
    executor_kind: str,
    executor_payload: dict[str, Any],
    contract_version: int = 1,
) -> tuple[OperationDefinition, bool]:
    cleaned_payload = _clean_json(executor_payload)
    fp = _fingerprint(cleaned_payload)
    definition, created = OperationDefinition.objects.get_or_create(
        tenant_scope=tenant_scope,
        fingerprint=fp,
        defaults={
            "executor_kind": _normalize_executor_kind(executor_kind),
            "executor_payload": cleaned_payload,
            "contract_version": max(1, int(contract_version or 1)),
            "status": OperationDefinition.STATUS_ACTIVE,
        },
    )
    if not created:
        changed = False
        if definition.executor_payload != cleaned_payload:
            definition.executor_payload = cleaned_payload
            changed = True
        if definition.executor_kind != _normalize_executor_kind(executor_kind):
            definition.executor_kind = _normalize_executor_kind(executor_kind)
            changed = True
        if changed:
            definition.save(update_fields=["executor_kind", "executor_payload", "updated_at"])
    return definition, created


def _resolve_exposure(
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
    qs = OperationExposure.objects.filter(surface=surface, alias=alias)
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
            capability=capability,
            contexts=contexts,
            display_order=int(display_order),
            capability_config=_clean_json(capability_config),
            status=status,
        )
        return exposure, True

    exposure.definition = definition
    exposure.label = label
    exposure.description = description
    exposure.is_active = bool(is_active)
    exposure.capability = capability
    exposure.contexts = contexts
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


def _record_issue(
    *,
    stats: BackfillStats,
    source_type: str,
    source_id: str,
    tenant_id: str | None,
    exposure: OperationExposure | None,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    _, created = OperationMigrationIssue.objects.get_or_create(
        source_type=source_type,
        source_id=source_id,
        tenant_id=tenant_id,
        exposure=exposure,
        code=code,
        defaults={
            "severity": OperationMigrationIssue.SEVERITY_ERROR,
            "message": message,
            "details": _clean_json(details or {}),
        },
    )
    if created:
        stats.issues_created += 1


def _get_commands_for_driver(driver: str, cache: dict[str, dict[str, Any] | None]) -> dict[str, Any] | None:
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
        commands_by_id = catalog.get("commands_by_id")
        cache[key] = commands_by_id if isinstance(commands_by_id, dict) else None
    except Exception:
        logger.exception("operation_catalog_backfill: failed to resolve command catalog", extra={"driver": key})
        cache[key] = None
    return cache[key]


def _validate_set_flags_binding(
    *,
    capability: str,
    executor_payload: dict[str, Any],
    capability_config: dict[str, Any],
    commands_cache: dict[str, dict[str, Any] | None],
) -> str | None:
    if capability != _SET_FLAGS_CAPABILITY:
        return None

    target_binding = capability_config.get("target_binding")
    if not isinstance(target_binding, dict):
        return "target_binding is required for extensions.set_flags"

    bound_param = str(target_binding.get("extension_name_param") or "").strip()
    if not bound_param:
        return "target_binding.extension_name_param is required for extensions.set_flags"

    driver = str(executor_payload.get("driver") or "").strip().lower()
    command_id = str(executor_payload.get("command_id") or "").strip()
    if not driver or not command_id:
        return "extensions.set_flags requires executor.driver and executor.command_id"

    commands_by_id = _get_commands_for_driver(driver, commands_cache)
    if not isinstance(commands_by_id, dict):
        return f"driver catalog not available: {driver}"

    command = commands_by_id.get(command_id)
    if not isinstance(command, dict):
        return f"unknown command_id: {command_id}"

    params_by_name = command.get("params_by_name")
    if not isinstance(params_by_name, dict):
        return f"command params schema not found: {driver}/{command_id}"

    if bound_param not in params_by_name:
        return f"bound param not found in command schema: {bound_param}"
    return None


def _template_executor_payload(template: OperationTemplate) -> tuple[str, dict[str, Any]]:
    operation_type = str(template.operation_type or "").strip()
    executor_kind = _normalize_executor_kind(operation_type)
    payload = {
        "operation_type": operation_type,
        "target_entity": str(template.target_entity or "").strip(),
        "template_data": template.template_data if isinstance(template.template_data, dict) else {},
    }
    return executor_kind, payload


def backfill_from_operation_templates(*, stats: BackfillStats) -> None:
    for order, template in enumerate(OperationTemplate.objects.all().order_by("name", "id"), start=1):
        stats.templates_processed += 1
        executor_kind, executor_payload = _template_executor_payload(template)
        definition, created = _resolve_definition(
            tenant_scope="global",
            executor_kind=executor_kind,
            executor_payload=executor_payload,
            contract_version=1,
        )
        if created:
            stats.definitions_created += 1
        else:
            stats.definitions_reused += 1

        contexts_raw = template.template_data.get("contexts") if isinstance(template.template_data, dict) else []
        contexts = [str(v) for v in contexts_raw if isinstance(v, str)] if isinstance(contexts_raw, list) else []
        _exposure, exp_created = _resolve_exposure(
            definition=definition,
            surface=OperationExposure.SURFACE_TEMPLATE,
            alias=str(template.id),
            tenant_id=None,
            label=str(template.name or template.id),
            description=str(template.description or ""),
            is_active=bool(template.is_active),
            capability=f"templates.{str(template.operation_type or '').strip() or 'legacy'}",
            contexts=contexts,
            display_order=order,
            capability_config={},
            status=OperationExposure.STATUS_PUBLISHED if template.is_active else OperationExposure.STATUS_DRAFT,
        )
        if exp_created:
            stats.exposures_created += 1
        else:
            stats.exposures_updated += 1


def _iter_action_catalog_sources() -> list[tuple[str, str | None, str, dict[str, Any]]]:
    sources: list[tuple[str, str | None, str, dict[str, Any]]] = []

    global_value = RuntimeSetting.objects.filter(key=UI_ACTION_CATALOG_KEY).values_list("value", flat=True).first()
    if isinstance(global_value, dict):
        sources.append(("runtime_setting_global", None, OperationExposure.STATUS_PUBLISHED, global_value))

    overrides = TenantRuntimeSettingOverride.objects.filter(key=UI_ACTION_CATALOG_KEY).values(
        "tenant_id", "status", "value"
    )
    for row in overrides:
        tenant_id = str(row.get("tenant_id") or "").strip() or None
        status = (
            OperationExposure.STATUS_PUBLISHED
            if row.get("status") == TenantRuntimeSettingOverride.STATUS_PUBLISHED
            else OperationExposure.STATUS_DRAFT
        )
        value = row.get("value")
        if isinstance(value, dict):
            sources.append(("runtime_setting_tenant_override", tenant_id, status, value))
    return sources


def _extract_action_capability_config(action: dict[str, Any], capability: str, executor: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    fixed = executor.get("fixed")
    if isinstance(fixed, dict):
        out["fixed"] = dict(fixed)

    target_binding = executor.get("target_binding")
    if isinstance(target_binding, dict):
        out["target_binding"] = dict(target_binding)

    if capability == _SET_FLAGS_CAPABILITY:
        fixed_obj = out.get("fixed")
        if isinstance(fixed_obj, dict) and "apply_mask" in fixed_obj:
            out["apply_mask"] = fixed_obj.pop("apply_mask")
            if not fixed_obj:
                out.pop("fixed", None)
    return out


def _extract_action_executor_payload(executor: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    payload = dict(executor)
    payload.pop("target_binding", None)
    executor_kind = _normalize_executor_kind(payload.get("kind"))
    return executor_kind, payload


def backfill_from_action_catalog(*, stats: BackfillStats) -> None:
    commands_cache: dict[str, dict[str, Any] | None] = {}

    for source_type, tenant_id, source_status, raw_payload in _iter_action_catalog_sources():
        catalog, schema_errors = ensure_valid_action_catalog(raw_payload)
        if schema_errors:
            _record_issue(
                stats=stats,
                source_type=source_type,
                source_id=tenant_id or "global",
                tenant_id=tenant_id,
                exposure=None,
                code="INVALID_ACTION_CATALOG_PAYLOAD",
                message="Action catalog schema validation failed during backfill",
                details={"errors": [err.to_text() for err in schema_errors]},
            )
            continue

        extensions = catalog.get("extensions")
        actions = extensions.get("actions") if isinstance(extensions, dict) else None
        if not isinstance(actions, list):
            continue

        tenant_scope = f"tenant:{tenant_id}" if tenant_id else "global"
        for index, raw_action in enumerate(actions):
            if not isinstance(raw_action, dict):
                continue
            stats.actions_processed += 1

            action_alias = str(raw_action.get("id") or "").strip()
            if not action_alias:
                _record_issue(
                    stats=stats,
                    source_type=source_type,
                    source_id=f"{tenant_id or 'global'}:index:{index}",
                    tenant_id=tenant_id,
                    exposure=None,
                    code="ACTION_ALIAS_REQUIRED",
                    message="Action id is required for unified exposure alias",
                )
                continue

            executor = raw_action.get("executor")
            if not isinstance(executor, dict):
                _record_issue(
                    stats=stats,
                    source_type=source_type,
                    source_id=action_alias,
                    tenant_id=tenant_id,
                    exposure=None,
                    code="ACTION_EXECUTOR_REQUIRED",
                    message="Action executor is required",
                )
                continue

            capability = _resolve_capability(raw_action)
            capability_config = _extract_action_capability_config(raw_action, capability, executor)
            executor_kind, executor_payload = _extract_action_executor_payload(executor)

            definition, created = _resolve_definition(
                tenant_scope=tenant_scope,
                executor_kind=executor_kind,
                executor_payload=executor_payload,
                contract_version=1,
            )
            if created:
                stats.definitions_created += 1
            else:
                stats.definitions_reused += 1

            contexts = raw_action.get("contexts")
            contexts_list = [str(v) for v in contexts if isinstance(v, str)] if isinstance(contexts, list) else []
            desired_status = source_status
            is_active = bool(raw_action.get("is_active", True))
            if not is_active:
                desired_status = OperationExposure.STATUS_DRAFT

            exposure, exp_created = _resolve_exposure(
                definition=definition,
                surface=OperationExposure.SURFACE_ACTION_CATALOG,
                alias=action_alias,
                tenant_id=tenant_id,
                label=str(raw_action.get("label") or action_alias),
                description=str(raw_action.get("description") or ""),
                is_active=is_active,
                capability=capability,
                contexts=contexts_list,
                display_order=index,
                capability_config=capability_config,
                status=desired_status,
            )
            if exp_created:
                stats.exposures_created += 1
            else:
                stats.exposures_updated += 1

            binding_error = _validate_set_flags_binding(
                capability=capability,
                executor_payload=executor_payload,
                capability_config=capability_config,
                commands_cache=commands_cache,
            )
            if binding_error:
                exposure.status = OperationExposure.STATUS_INVALID
                exposure.save(update_fields=["status", "updated_at"])
                _record_issue(
                    stats=stats,
                    source_type=source_type,
                    source_id=action_alias,
                    tenant_id=tenant_id,
                    exposure=exposure,
                    code="INVALID_SET_FLAGS_TARGET_BINDING",
                    message=binding_error,
                    details={
                        "capability": capability,
                        "alias": action_alias,
                    },
                )


@transaction.atomic
def run_unified_operation_catalog_backfill() -> BackfillStats:
    """Backfill unified operation catalog from legacy templates + runtime settings."""
    stats = BackfillStats()
    backfill_from_operation_templates(stats=stats)
    backfill_from_action_catalog(stats=stats)
    return stats

