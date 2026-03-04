from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.templates.models import OperationDefinition, OperationExposure
from apps.templates.operation_catalog_service import resolve_definition, resolve_exposure


POOL_RUNTIME_TEMPLATE_CONTRACT_VERSION = 1
POOL_RUNTIME_TEMPLATE_CONTRACT = "pool_runtime.v1"
POOL_RUNTIME_TEMPLATE_CAPABILITY = "pools.runtime"
POOL_RUNTIME_TEMPLATE_TARGET_ENTITY = "pool_run"


@dataclass(frozen=True)
class PoolRuntimeTemplateSpec:
    alias: str
    label: str
    step_id: str
    description: str
    display_order: int


@dataclass(frozen=True)
class PoolRuntimeTemplateRegistrySyncResult:
    created: int
    updated: int
    unchanged: int


@dataclass(frozen=True)
class PoolRuntimeTemplateRegistryEntryStatus:
    alias: str
    label: str
    status: str
    issues: list[str]
    exposure_id: str | None
    exposure_revision: int | None
    operation_type: str
    target_entity: str
    is_active: bool
    exposure_status: str
    system_managed: bool
    domain: str


_POOL_RUNTIME_TEMPLATE_SPECS: tuple[PoolRuntimeTemplateSpec, ...] = (
    PoolRuntimeTemplateSpec(
        alias="pool.prepare_input",
        label="Pool Prepare Input",
        step_id="prepare_input",
        description="System-managed pool runtime step: prepare input payload.",
        display_order=10,
    ),
    PoolRuntimeTemplateSpec(
        alias="pool.distribution_calculation.top_down",
        label="Pool Distribution Calculation (Top Down)",
        step_id="distribution_calculation.top_down",
        description="System-managed pool runtime step: top-down distribution calculation.",
        display_order=20,
    ),
    PoolRuntimeTemplateSpec(
        alias="pool.distribution_calculation.bottom_up",
        label="Pool Distribution Calculation (Bottom Up)",
        step_id="distribution_calculation.bottom_up",
        description="System-managed pool runtime step: bottom-up distribution calculation.",
        display_order=30,
    ),
    PoolRuntimeTemplateSpec(
        alias="pool.reconciliation_report",
        label="Pool Reconciliation Report",
        step_id="reconciliation_report",
        description="System-managed pool runtime step: reconciliation report generation.",
        display_order=40,
    ),
    PoolRuntimeTemplateSpec(
        alias="pool.approval_gate",
        label="Pool Approval Gate",
        step_id="approval_gate",
        description="System-managed pool runtime step: approval gate checkpoint.",
        display_order=50,
    ),
    PoolRuntimeTemplateSpec(
        alias="pool.master_data_gate",
        label="Pool Master Data Gate",
        step_id="master_data_gate",
        description="System-managed pool runtime step: pre-publication master-data resolve+upsert gate.",
        display_order=55,
    ),
    PoolRuntimeTemplateSpec(
        alias="pool.publication_odata",
        label="Pool Publication OData",
        step_id="publication_odata",
        description="System-managed pool runtime step: publication to OData targets.",
        display_order=60,
    ),
    PoolRuntimeTemplateSpec(
        alias="pool.master_data_sync.inbound",
        label="Pool Master Data Sync Inbound",
        step_id="master_data_sync.inbound",
        description="System-managed pool runtime step: process inbound master-data sync batch.",
        display_order=62,
    ),
    PoolRuntimeTemplateSpec(
        alias="pool.master_data_sync.dispatch",
        label="Pool Master Data Sync Dispatch",
        step_id="master_data_sync.dispatch",
        description="System-managed pool runtime step: dispatch master-data sync scope batch.",
        display_order=65,
    ),
    PoolRuntimeTemplateSpec(
        alias="pool.master_data_sync.finalize",
        label="Pool Master Data Sync Finalize",
        step_id="master_data_sync.finalize",
        description="System-managed pool runtime step: finalize master-data sync job state.",
        display_order=70,
    ),
)


def get_pool_runtime_template_specs() -> tuple[PoolRuntimeTemplateSpec, ...]:
    return _POOL_RUNTIME_TEMPLATE_SPECS


def get_pool_runtime_template_aliases() -> tuple[str, ...]:
    return tuple(spec.alias for spec in _POOL_RUNTIME_TEMPLATE_SPECS)


def _definition_payload(spec: PoolRuntimeTemplateSpec) -> dict[str, object]:
    return {
        "operation_type": spec.alias,
        "target_entity": POOL_RUNTIME_TEMPLATE_TARGET_ENTITY,
        "template_data": {
            "pool_runtime": {
                "step_id": spec.step_id,
                "contract": POOL_RUNTIME_TEMPLATE_CONTRACT,
            },
            "options": {
                "target_scope": "global",
            },
        },
    }


def _needs_exposure_update(*, exposure: OperationExposure, definition_id: str, spec: PoolRuntimeTemplateSpec) -> bool:
    return any(
        (
            str(exposure.definition_id) != str(definition_id),
            str(exposure.label or "") != spec.label,
            str(exposure.description or "") != spec.description,
            bool(exposure.is_active) is not True,
            str(exposure.capability or "") != POOL_RUNTIME_TEMPLATE_CAPABILITY,
            list(exposure.contexts or []) != [],
            int(exposure.display_order) != int(spec.display_order),
            dict(exposure.capability_config or {}) != {},
            str(exposure.status or "") != OperationExposure.STATUS_PUBLISHED,
            bool(getattr(exposure, "system_managed", False)) is not True,
            str(getattr(exposure, "domain", "") or "") != OperationExposure.DOMAIN_POOL_RUNTIME,
        )
    )


def _resolve_exposure_revision(exposure: OperationExposure) -> int:
    try:
        parsed = int(getattr(exposure, "exposure_revision", 0) or 0)
    except (TypeError, ValueError):
        parsed = 0
    if parsed > 0:
        return parsed
    definition = getattr(exposure, "definition", None)
    try:
        fallback = int(getattr(definition, "contract_version", 1) or 1)
    except (TypeError, ValueError):
        fallback = 1
    return fallback if fallback > 0 else 1


def sync_pool_runtime_template_registry(*, dry_run: bool = False) -> PoolRuntimeTemplateRegistrySyncResult:
    created = 0
    updated = 0
    unchanged = 0

    def _apply() -> None:
        nonlocal created, updated, unchanged

        for spec in _POOL_RUNTIME_TEMPLATE_SPECS:
            definition, _ = resolve_definition(
                tenant_scope="global",
                executor_kind=OperationDefinition.EXECUTOR_WORKFLOW,
                executor_payload=_definition_payload(spec),
                contract_version=POOL_RUNTIME_TEMPLATE_CONTRACT_VERSION,
            )
            exposure = (
                OperationExposure.objects.select_related("definition")
                .filter(
                    surface=OperationExposure.SURFACE_TEMPLATE,
                    alias=spec.alias,
                    tenant__isnull=True,
                )
                .first()
            )
            if exposure is None:
                created += 1
                if dry_run:
                    continue
                resolve_exposure(
                    definition=definition,
                    surface=OperationExposure.SURFACE_TEMPLATE,
                    alias=spec.alias,
                    tenant_id=None,
                    label=spec.label,
                    description=spec.description,
                    is_active=True,
                    capability=POOL_RUNTIME_TEMPLATE_CAPABILITY,
                    contexts=[],
                    display_order=spec.display_order,
                    capability_config={},
                    status=OperationExposure.STATUS_PUBLISHED,
                    system_managed=True,
                    domain=OperationExposure.DOMAIN_POOL_RUNTIME,
                )
                continue

            if not _needs_exposure_update(exposure=exposure, definition_id=str(definition.id), spec=spec):
                unchanged += 1
                continue

            updated += 1
            if dry_run:
                continue
            resolve_exposure(
                definition=definition,
                surface=OperationExposure.SURFACE_TEMPLATE,
                alias=spec.alias,
                tenant_id=None,
                label=spec.label,
                description=spec.description,
                is_active=True,
                capability=POOL_RUNTIME_TEMPLATE_CAPABILITY,
                contexts=[],
                display_order=spec.display_order,
                capability_config={},
                status=OperationExposure.STATUS_PUBLISHED,
                system_managed=True,
                domain=OperationExposure.DOMAIN_POOL_RUNTIME,
            )

    if dry_run:
        _apply()
    else:
        with transaction.atomic():
            _apply()

    return PoolRuntimeTemplateRegistrySyncResult(created=created, updated=updated, unchanged=unchanged)


def inspect_pool_runtime_template_registry() -> list[PoolRuntimeTemplateRegistryEntryStatus]:
    result: list[PoolRuntimeTemplateRegistryEntryStatus] = []
    for spec in _POOL_RUNTIME_TEMPLATE_SPECS:
        exposure = (
            OperationExposure.objects.select_related("definition")
            .filter(
                surface=OperationExposure.SURFACE_TEMPLATE,
                alias=spec.alias,
                tenant__isnull=True,
            )
            .first()
        )
        if exposure is None:
            result.append(
                PoolRuntimeTemplateRegistryEntryStatus(
                    alias=spec.alias,
                    label=spec.label,
                    status="missing",
                    issues=["missing_exposure"],
                    exposure_id=None,
                    exposure_revision=None,
                    operation_type="",
                    target_entity="",
                    is_active=False,
                    exposure_status="",
                    system_managed=False,
                    domain="",
                )
            )
            continue

        payload = exposure.definition.executor_payload if isinstance(exposure.definition.executor_payload, dict) else {}
        operation_type = str(payload.get("operation_type") or "").strip()
        target_entity = str(payload.get("target_entity") or "").strip()
        template_data = payload.get("template_data")
        pool_runtime_data = template_data.get("pool_runtime") if isinstance(template_data, dict) else {}
        step_id = str(pool_runtime_data.get("step_id") or "").strip() if isinstance(pool_runtime_data, dict) else ""
        contract = str(pool_runtime_data.get("contract") or "").strip() if isinstance(pool_runtime_data, dict) else ""

        issues: list[str] = []
        if operation_type != spec.alias:
            issues.append("operation_type_mismatch")
        if target_entity != POOL_RUNTIME_TEMPLATE_TARGET_ENTITY:
            issues.append("target_entity_mismatch")
        if step_id != spec.step_id:
            issues.append("step_id_mismatch")
        if contract != POOL_RUNTIME_TEMPLATE_CONTRACT:
            issues.append("contract_mismatch")
        if not bool(exposure.is_active):
            issues.append("inactive")
        if str(exposure.status or "") != OperationExposure.STATUS_PUBLISHED:
            issues.append("unpublished")
        if not bool(getattr(exposure, "system_managed", False)):
            issues.append("not_system_managed")
        if str(getattr(exposure, "domain", "") or "") != OperationExposure.DOMAIN_POOL_RUNTIME:
            issues.append("domain_mismatch")

        status = "configured" if not issues else "drift"
        result.append(
            PoolRuntimeTemplateRegistryEntryStatus(
                alias=spec.alias,
                label=spec.label,
                status=status,
                issues=issues,
                exposure_id=str(exposure.id),
                exposure_revision=_resolve_exposure_revision(exposure),
                operation_type=operation_type,
                target_entity=target_entity,
                is_active=bool(exposure.is_active),
                exposure_status=str(exposure.status or ""),
                system_managed=bool(getattr(exposure, "system_managed", False)),
                domain=str(getattr(exposure, "domain", "") or ""),
            )
        )
    return result
