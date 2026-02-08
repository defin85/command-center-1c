from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from django.db import transaction

from apps.templates.models import (
    OperationDefinition,
    OperationExposure,
    OperationTemplate,
)


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


@transaction.atomic
def run_unified_operation_catalog_backfill() -> BackfillStats:
    """Backfill unified operation catalog from OperationTemplate projection only."""
    stats = BackfillStats()
    backfill_from_operation_templates(stats=stats)
    return stats
