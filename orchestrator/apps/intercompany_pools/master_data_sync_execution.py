from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.databases.models import Database

from .master_data_dedupe import (
    MasterDataDedupeReviewRequiredError,
    ingest_pool_master_data_source_record,
    require_pool_master_data_dedupe_resolved,
)
from .master_data_registry import (
    POOL_MASTER_DATA_CAPABILITY_SYNC_INBOUND,
    POOL_MASTER_DATA_CAPABILITY_SYNC_OUTBOUND,
    POOL_MASTER_DATA_CAPABILITY_SYNC_RECONCILE,
    normalize_pool_master_data_entity_type,
    supports_pool_master_data_capability,
)
from .master_data_sync_conflicts import (
    MASTER_DATA_SYNC_CONFLICT_DEDUPE_REVIEW_REQUIRED,
    MASTER_DATA_SYNC_CONFLICT_APPLY,
    MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
    MasterDataSyncConflictError,
    enqueue_master_data_sync_conflict,
    raise_fail_closed_master_data_sync_conflict,
)
from .master_data_sync_dispatcher import dispatch_pending_master_data_sync_outbox
from .master_data_sync_inbound_poller import (
    InboundPollerTransportError,
    MasterDataSyncSelectChangesResult,
    process_master_data_sync_inbound_batch,
)
from .master_data_sync_live_odata_transport import (
    MasterDataSyncLiveODataError,
    notify_changes_received_from_live_odata,
    select_changes_from_live_odata,
)
from .master_data_sync_policy import resolve_pool_master_data_sync_policy
from .master_data_sync_runtime_settings import require_pool_master_data_sync_runtime_settings
from .master_data_sync_workflow_contract import validate_master_data_sync_workflow_input_context
from .master_data_sync_workflow_runtime import (
    PoolMasterDataSyncWorkflowStartResult,
    start_pool_master_data_sync_job_workflow,
)
from .models import (
    PoolMasterDataSyncDirection,
    PoolMasterDataSyncJob,
    PoolMasterDataSyncJobStatus,
    PoolMasterDataSyncPolicy,
)

MASTER_DATA_SYNC_DISABLED = "MASTER_DATA_SYNC_DISABLED"
MASTER_DATA_SYNC_OUTBOUND_DISABLED = "MASTER_DATA_SYNC_OUTBOUND_DISABLED"
MASTER_DATA_SYNC_INBOUND_DISABLED = "MASTER_DATA_SYNC_INBOUND_DISABLED"
MASTER_DATA_SYNC_OUTBOUND_CAPABILITY_DISABLED = "MASTER_DATA_SYNC_OUTBOUND_CAPABILITY_DISABLED"
MASTER_DATA_SYNC_INBOUND_CAPABILITY_DISABLED = "MASTER_DATA_SYNC_INBOUND_CAPABILITY_DISABLED"
MASTER_DATA_SYNC_RECONCILE_CAPABILITY_DISABLED = "MASTER_DATA_SYNC_RECONCILE_CAPABILITY_DISABLED"
MASTER_DATA_SYNC_INBOUND_CALLBACKS_NOT_CONFIGURED = "MASTER_DATA_SYNC_INBOUND_CALLBACKS_NOT_CONFIGURED"
SYNC_LEGACY_INBOUND_ROUTE_DISABLED = "SYNC_LEGACY_INBOUND_ROUTE_DISABLED"
MASTER_DATA_SYNC_DEDUPE_REVIEW_REQUIRED = "MASTER_DATA_DEDUPE_REVIEW_REQUIRED"


class LegacyInboundRouteDisabledError(RuntimeError):
    def __init__(self, *, detail: str) -> None:
        self.code = SYNC_LEGACY_INBOUND_ROUTE_DISABLED
        self.detail = str(detail or "").strip() or "legacy inbound route is disabled"
        super().__init__(f"{self.code}: {self.detail}")


_InboundSelectChangesCallback = Callable[..., MasterDataSyncSelectChangesResult]
_InboundApplyChangeCallback = Callable[..., Any]
_InboundNotifyChangesReceivedCallback = Callable[..., Any]

_INBOUND_SELECT_CHANGES_CALLBACK: _InboundSelectChangesCallback | None = None
_INBOUND_APPLY_CHANGE_CALLBACK: _InboundApplyChangeCallback | None = None
_INBOUND_NOTIFY_CHANGES_RECEIVED_CALLBACK: _InboundNotifyChangesReceivedCallback | None = None
_INBOUND_SELECT_CHANGES_KWARGS: dict[str, Any] = {}
_INBOUND_NOTIFY_CHANGES_RECEIVED_KWARGS: dict[str, Any] = {}


@dataclass(frozen=True)
class PoolMasterDataSyncPolicyDecision:
    policy: str
    source: str  # database_scope | tenant_default | runtime_default


@dataclass(frozen=True)
class PoolMasterDataSyncTriggerResult:
    sync_job: PoolMasterDataSyncJob | None
    created_job: bool
    started_workflow: bool
    skipped: bool
    skip_reason: str | None
    policy: str | None
    policy_source: str | None
    start_result: PoolMasterDataSyncWorkflowStartResult | None


def resolve_effective_pool_master_data_sync_policy(
    *,
    tenant_id: str,
    entity_type: str,
    database_id: str | None,
    default_policy: str,
) -> PoolMasterDataSyncPolicyDecision:
    resolution = resolve_pool_master_data_sync_policy(
        tenant_id=tenant_id,
        entity_type=entity_type,
        database_id=database_id,
    )
    if resolution.policy is not None:
        return PoolMasterDataSyncPolicyDecision(
            policy=str(resolution.policy),
            source=str(resolution.source),
        )

    normalized_default = str(default_policy or "").strip().lower()
    if normalized_default in set(PoolMasterDataSyncPolicy.values):
        return PoolMasterDataSyncPolicyDecision(
            policy=normalized_default,
            source="runtime_default",
        )
    raise ValueError(f"Unsupported runtime default sync policy '{default_policy}'")


def configure_pool_master_data_sync_inbound_callbacks(
    *,
    select_changes: _InboundSelectChangesCallback,
    apply_change: _InboundApplyChangeCallback | None = None,
    notify_changes_received: _InboundNotifyChangesReceivedCallback | None = None,
    select_changes_kwargs: Mapping[str, Any] | None = None,
    notify_changes_received_kwargs: Mapping[str, Any] | None = None,
) -> None:
    global _INBOUND_SELECT_CHANGES_CALLBACK
    global _INBOUND_APPLY_CHANGE_CALLBACK
    global _INBOUND_NOTIFY_CHANGES_RECEIVED_CALLBACK
    _INBOUND_SELECT_CHANGES_CALLBACK = select_changes
    _INBOUND_APPLY_CHANGE_CALLBACK = apply_change
    _INBOUND_NOTIFY_CHANGES_RECEIVED_CALLBACK = notify_changes_received
    _INBOUND_SELECT_CHANGES_KWARGS.clear()
    _INBOUND_SELECT_CHANGES_KWARGS.update(dict(select_changes_kwargs or {}))
    _INBOUND_NOTIFY_CHANGES_RECEIVED_KWARGS.clear()
    _INBOUND_NOTIFY_CHANGES_RECEIVED_KWARGS.update(dict(notify_changes_received_kwargs or {}))


def reset_pool_master_data_sync_inbound_callbacks() -> None:
    global _INBOUND_SELECT_CHANGES_CALLBACK
    global _INBOUND_APPLY_CHANGE_CALLBACK
    global _INBOUND_NOTIFY_CHANGES_RECEIVED_CALLBACK
    _INBOUND_SELECT_CHANGES_CALLBACK = None
    _INBOUND_APPLY_CHANGE_CALLBACK = None
    _INBOUND_NOTIFY_CHANGES_RECEIVED_CALLBACK = None
    _INBOUND_SELECT_CHANGES_KWARGS.clear()
    _INBOUND_NOTIFY_CHANGES_RECEIVED_KWARGS.clear()


def _find_active_sync_job(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    direction: str,
) -> PoolMasterDataSyncJob | None:
    return (
        PoolMasterDataSyncJob.objects.select_for_update()
        .filter(
            tenant_id=tenant_id,
            database_id=database_id,
            entity_type=entity_type,
            direction=direction,
            status__in=[PoolMasterDataSyncJobStatus.PENDING, PoolMasterDataSyncJobStatus.RUNNING],
        )
        .order_by("-created_at")
        .first()
    )


def _update_coalesced_sync_job_metadata(
    *,
    sync_job: PoolMasterDataSyncJob,
    last_trigger: Mapping[str, Any],
    requested_policy: str,
    requested_policy_source: str,
) -> PoolMasterDataSyncJob:
    metadata = dict(sync_job.metadata or {})
    metadata["trigger_count"] = int(metadata.get("trigger_count") or 0) + 1
    metadata["last_trigger"] = dict(last_trigger)
    metadata["last_requested_policy"] = requested_policy
    metadata["last_requested_policy_source"] = requested_policy_source
    sync_job.metadata = metadata
    sync_job.save(update_fields=["metadata", "updated_at"])
    return sync_job


def trigger_pool_master_data_outbound_sync_job(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    canonical_id: str,
    origin_system: str,
    origin_event_id: str,
    correlation_id: str | None = None,
) -> PoolMasterDataSyncTriggerResult:
    normalized_tenant_id = str(tenant_id or "").strip()
    normalized_database_id = str(database_id or "").strip()
    normalized_entity_type = normalize_pool_master_data_entity_type(entity_type)
    normalized_origin_system = str(origin_system or "cc").strip().lower() or "cc"
    normalized_origin_event_id = str(origin_event_id or "").strip() or f"evt-{uuid4()}"
    normalized_canonical_id = str(canonical_id or "").strip()
    normalized_correlation_id = str(correlation_id or "").strip() or f"corr-{uuid4()}"

    if not supports_pool_master_data_capability(
        entity_type=normalized_entity_type,
        capability=POOL_MASTER_DATA_CAPABILITY_SYNC_OUTBOUND,
    ):
        return PoolMasterDataSyncTriggerResult(
            sync_job=None,
            created_job=False,
            started_workflow=False,
            skipped=True,
            skip_reason=MASTER_DATA_SYNC_OUTBOUND_CAPABILITY_DISABLED,
            policy=None,
            policy_source=None,
            start_result=None,
        )

    try:
        require_pool_master_data_dedupe_resolved(
            tenant_id=normalized_tenant_id,
            entity_type=normalized_entity_type,
            canonical_id=normalized_canonical_id,
        )
    except MasterDataDedupeReviewRequiredError as exc:
        enqueue_master_data_sync_conflict(
            tenant_id=normalized_tenant_id,
            database_id=normalized_database_id,
            entity_type=normalized_entity_type,
            conflict_code=MASTER_DATA_SYNC_CONFLICT_DEDUPE_REVIEW_REQUIRED,
            canonical_id=normalized_canonical_id,
            origin_system=normalized_origin_system,
            origin_event_id=normalized_origin_event_id,
            diagnostics=exc.to_diagnostic(),
            metadata={"runtime_gate": "dedupe_review_required"},
        )
        return PoolMasterDataSyncTriggerResult(
            sync_job=None,
            created_job=False,
            started_workflow=False,
            skipped=True,
            skip_reason=MASTER_DATA_SYNC_DEDUPE_REVIEW_REQUIRED,
            policy=None,
            policy_source=None,
            start_result=None,
        )

    runtime_settings = require_pool_master_data_sync_runtime_settings(tenant_id=normalized_tenant_id)
    if not runtime_settings.enabled:
        return PoolMasterDataSyncTriggerResult(
            sync_job=None,
            created_job=False,
            started_workflow=False,
            skipped=True,
            skip_reason=MASTER_DATA_SYNC_DISABLED,
            policy=None,
            policy_source=None,
            start_result=None,
        )
    if not runtime_settings.outbound_enabled:
        return PoolMasterDataSyncTriggerResult(
            sync_job=None,
            created_job=False,
            started_workflow=False,
            skipped=True,
            skip_reason=MASTER_DATA_SYNC_OUTBOUND_DISABLED,
            policy=None,
            policy_source=None,
            start_result=None,
        )

    policy_decision = resolve_effective_pool_master_data_sync_policy(
        tenant_id=normalized_tenant_id,
        entity_type=normalized_entity_type,
        database_id=normalized_database_id,
        default_policy=runtime_settings.default_policy,
    )
    if policy_decision.policy not in {
        PoolMasterDataSyncPolicy.CC_MASTER,
        PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    }:
        raise_fail_closed_master_data_sync_conflict(
            tenant_id=normalized_tenant_id,
            database_id=normalized_database_id,
            entity_type=normalized_entity_type,
            conflict_code=MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
            detail=(
                "Outbound sync is forbidden by effective policy "
                f"'{policy_decision.policy}' for scope tenant='{normalized_tenant_id}', "
                f"database='{normalized_database_id}', entity='{normalized_entity_type}'."
            ),
            canonical_id=normalized_canonical_id,
            origin_system=normalized_origin_system,
            origin_event_id=normalized_origin_event_id,
            diagnostics={
                "policy": policy_decision.policy,
                "policy_source": policy_decision.source,
            },
        )

    with transaction.atomic():
        last_trigger = {
            "canonical_id": normalized_canonical_id,
            "origin_system": normalized_origin_system,
            "origin_event_id": normalized_origin_event_id,
            "at": timezone.now().isoformat(),
        }
        existing_job = _find_active_sync_job(
            tenant_id=normalized_tenant_id,
            database_id=normalized_database_id,
            entity_type=normalized_entity_type,
            direction=PoolMasterDataSyncDirection.OUTBOUND,
        )
        if existing_job is None:
            sync_job = PoolMasterDataSyncJob.objects.create(
                tenant_id=normalized_tenant_id,
                database_id=normalized_database_id,
                entity_type=normalized_entity_type,
                policy=policy_decision.policy,
                direction=PoolMasterDataSyncDirection.OUTBOUND,
                status=PoolMasterDataSyncJobStatus.PENDING,
                metadata={
                    "trigger_count": 1,
                    "policy_source": policy_decision.source,
                    "last_trigger": last_trigger,
                },
            )
            created_job = True
        else:
            sync_job = _update_coalesced_sync_job_metadata(
                sync_job=existing_job,
                last_trigger=last_trigger,
                requested_policy=policy_decision.policy,
                requested_policy_source=policy_decision.source,
            )
            created_job = False

    start_result = start_pool_master_data_sync_job_workflow(
        sync_job=sync_job,
        correlation_id=normalized_correlation_id,
        origin_system=normalized_origin_system,
        origin_event_id=normalized_origin_event_id,
    )
    if not start_result.enqueue_success:
        enqueue_master_data_sync_conflict(
            tenant_id=normalized_tenant_id,
            database_id=normalized_database_id,
            entity_type=normalized_entity_type,
            conflict_code=MASTER_DATA_SYNC_CONFLICT_APPLY,
            canonical_id=normalized_canonical_id,
            origin_system=normalized_origin_system,
            origin_event_id=normalized_origin_event_id,
            diagnostics={
                "detail": str(start_result.enqueue_error or ""),
                "enqueue_status": str(start_result.enqueue_status or ""),
                "sync_job_id": str(sync_job.id),
            },
            metadata={
                "phase": "enqueue_workflow_execution",
                "policy": policy_decision.policy,
                "policy_source": policy_decision.source,
            },
        )

    return PoolMasterDataSyncTriggerResult(
        sync_job=start_result.sync_job,
        created_job=created_job,
        started_workflow=bool(start_result.enqueue_success),
        skipped=False,
        skip_reason=None,
        policy=policy_decision.policy,
        policy_source=policy_decision.source,
        start_result=start_result,
    )


def trigger_pool_master_data_inbound_sync_job(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    origin_system: str = "ib",
    origin_event_id: str | None = None,
    correlation_id: str | None = None,
) -> PoolMasterDataSyncTriggerResult:
    normalized_tenant_id = str(tenant_id or "").strip()
    normalized_database_id = str(database_id or "").strip()
    normalized_entity_type = normalize_pool_master_data_entity_type(entity_type)
    normalized_origin_system = str(origin_system or "ib").strip().lower() or "ib"
    normalized_origin_event_id = str(origin_event_id or "").strip() or f"evt-{uuid4()}"
    normalized_correlation_id = str(correlation_id or "").strip() or f"corr-{uuid4()}"

    if not supports_pool_master_data_capability(
        entity_type=normalized_entity_type,
        capability=POOL_MASTER_DATA_CAPABILITY_SYNC_INBOUND,
    ):
        return PoolMasterDataSyncTriggerResult(
            sync_job=None,
            created_job=False,
            started_workflow=False,
            skipped=True,
            skip_reason=MASTER_DATA_SYNC_INBOUND_CAPABILITY_DISABLED,
            policy=None,
            policy_source=None,
            start_result=None,
        )

    runtime_settings = require_pool_master_data_sync_runtime_settings(tenant_id=normalized_tenant_id)
    if not runtime_settings.enabled:
        return PoolMasterDataSyncTriggerResult(
            sync_job=None,
            created_job=False,
            started_workflow=False,
            skipped=True,
            skip_reason=MASTER_DATA_SYNC_DISABLED,
            policy=None,
            policy_source=None,
            start_result=None,
        )
    if not runtime_settings.inbound_enabled:
        return PoolMasterDataSyncTriggerResult(
            sync_job=None,
            created_job=False,
            started_workflow=False,
            skipped=True,
            skip_reason=MASTER_DATA_SYNC_INBOUND_DISABLED,
            policy=None,
            policy_source=None,
            start_result=None,
        )

    policy_decision = resolve_effective_pool_master_data_sync_policy(
        tenant_id=normalized_tenant_id,
        entity_type=normalized_entity_type,
        database_id=normalized_database_id,
        default_policy=runtime_settings.default_policy,
    )
    if policy_decision.policy not in {
        PoolMasterDataSyncPolicy.IB_MASTER,
        PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    }:
        raise_fail_closed_master_data_sync_conflict(
            tenant_id=normalized_tenant_id,
            database_id=normalized_database_id,
            entity_type=normalized_entity_type,
            conflict_code=MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
            detail=(
                "Inbound sync is forbidden by effective policy "
                f"'{policy_decision.policy}' for scope tenant='{normalized_tenant_id}', "
                f"database='{normalized_database_id}', entity='{normalized_entity_type}'."
            ),
            origin_system=normalized_origin_system,
            origin_event_id=normalized_origin_event_id,
            diagnostics={
                "policy": policy_decision.policy,
                "policy_source": policy_decision.source,
            },
        )

    with transaction.atomic():
        last_trigger = {
            "origin_system": normalized_origin_system,
            "origin_event_id": normalized_origin_event_id,
            "at": timezone.now().isoformat(),
        }
        existing_job = _find_active_sync_job(
            tenant_id=normalized_tenant_id,
            database_id=normalized_database_id,
            entity_type=normalized_entity_type,
            direction=PoolMasterDataSyncDirection.INBOUND,
        )
        if existing_job is None:
            sync_job = PoolMasterDataSyncJob.objects.create(
                tenant_id=normalized_tenant_id,
                database_id=normalized_database_id,
                entity_type=normalized_entity_type,
                policy=policy_decision.policy,
                direction=PoolMasterDataSyncDirection.INBOUND,
                status=PoolMasterDataSyncJobStatus.PENDING,
                metadata={
                    "trigger_count": 1,
                    "policy_source": policy_decision.source,
                    "last_trigger": last_trigger,
                },
            )
            created_job = True
        else:
            sync_job = _update_coalesced_sync_job_metadata(
                sync_job=existing_job,
                last_trigger=last_trigger,
                requested_policy=policy_decision.policy,
                requested_policy_source=policy_decision.source,
            )
            created_job = False

    start_result = start_pool_master_data_sync_job_workflow(
        sync_job=sync_job,
        correlation_id=normalized_correlation_id,
        origin_system=normalized_origin_system,
        origin_event_id=normalized_origin_event_id,
    )
    if not start_result.enqueue_success:
        enqueue_master_data_sync_conflict(
            tenant_id=normalized_tenant_id,
            database_id=normalized_database_id,
            entity_type=normalized_entity_type,
            conflict_code=MASTER_DATA_SYNC_CONFLICT_APPLY,
            origin_system=normalized_origin_system,
            origin_event_id=normalized_origin_event_id,
            diagnostics={
                "detail": str(start_result.enqueue_error or ""),
                "enqueue_status": str(start_result.enqueue_status or ""),
                "sync_job_id": str(sync_job.id),
            },
            metadata={
                "phase": "enqueue_workflow_execution",
                "policy": policy_decision.policy,
                "policy_source": policy_decision.source,
            },
        )

    return PoolMasterDataSyncTriggerResult(
        sync_job=start_result.sync_job,
        created_job=created_job,
        started_workflow=bool(start_result.enqueue_success),
        skipped=False,
        skip_reason=None,
        policy=policy_decision.policy,
        policy_source=policy_decision.source,
        start_result=start_result,
    )


def trigger_pool_master_data_reconcile_sync_job(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    origin_system: str = "reconcile_scheduler",
    origin_event_id: str | None = None,
    correlation_id: str | None = None,
    reconcile_window_id: str | None = None,
    reconcile_window_deadline_at: str | None = None,
) -> PoolMasterDataSyncTriggerResult:
    normalized_tenant_id = str(tenant_id or "").strip()
    normalized_database_id = str(database_id or "").strip()
    normalized_entity_type = normalize_pool_master_data_entity_type(entity_type)
    normalized_origin_system = str(origin_system or "reconcile_scheduler").strip().lower() or "reconcile_scheduler"
    normalized_origin_event_id = str(origin_event_id or "").strip() or f"evt-{uuid4()}"
    normalized_correlation_id = str(correlation_id or "").strip() or f"corr-{uuid4()}"
    normalized_window_id = str(reconcile_window_id or "").strip()
    normalized_window_deadline_at = str(reconcile_window_deadline_at or "").strip()

    if not supports_pool_master_data_capability(
        entity_type=normalized_entity_type,
        capability=POOL_MASTER_DATA_CAPABILITY_SYNC_RECONCILE,
    ):
        return PoolMasterDataSyncTriggerResult(
            sync_job=None,
            created_job=False,
            started_workflow=False,
            skipped=True,
            skip_reason=MASTER_DATA_SYNC_RECONCILE_CAPABILITY_DISABLED,
            policy=None,
            policy_source=None,
            start_result=None,
        )

    runtime_settings = require_pool_master_data_sync_runtime_settings(tenant_id=normalized_tenant_id)
    if not runtime_settings.enabled:
        return PoolMasterDataSyncTriggerResult(
            sync_job=None,
            created_job=False,
            started_workflow=False,
            skipped=True,
            skip_reason=MASTER_DATA_SYNC_DISABLED,
            policy=None,
            policy_source=None,
            start_result=None,
        )
    if not runtime_settings.inbound_enabled:
        return PoolMasterDataSyncTriggerResult(
            sync_job=None,
            created_job=False,
            started_workflow=False,
            skipped=True,
            skip_reason=MASTER_DATA_SYNC_INBOUND_DISABLED,
            policy=None,
            policy_source=None,
            start_result=None,
        )
    if not runtime_settings.outbound_enabled:
        return PoolMasterDataSyncTriggerResult(
            sync_job=None,
            created_job=False,
            started_workflow=False,
            skipped=True,
            skip_reason=MASTER_DATA_SYNC_OUTBOUND_DISABLED,
            policy=None,
            policy_source=None,
            start_result=None,
        )

    policy_decision = resolve_effective_pool_master_data_sync_policy(
        tenant_id=normalized_tenant_id,
        entity_type=normalized_entity_type,
        database_id=normalized_database_id,
        default_policy=runtime_settings.default_policy,
    )

    with transaction.atomic():
        last_trigger = {
            "origin_system": normalized_origin_system,
            "origin_event_id": normalized_origin_event_id,
            "mode": "reconcile_probe",
            "reconcile_window_id": normalized_window_id,
            "reconcile_window_deadline_at": normalized_window_deadline_at,
            "at": timezone.now().isoformat(),
        }
        existing_job = _find_active_sync_job(
            tenant_id=normalized_tenant_id,
            database_id=normalized_database_id,
            entity_type=normalized_entity_type,
            direction=PoolMasterDataSyncDirection.BIDIRECTIONAL,
        )
        if existing_job is None:
            sync_job = PoolMasterDataSyncJob.objects.create(
                tenant_id=normalized_tenant_id,
                database_id=normalized_database_id,
                entity_type=normalized_entity_type,
                policy=policy_decision.policy,
                direction=PoolMasterDataSyncDirection.BIDIRECTIONAL,
                status=PoolMasterDataSyncJobStatus.PENDING,
                metadata={
                    "trigger_count": 1,
                    "policy_source": policy_decision.source,
                    "last_trigger": last_trigger,
                },
            )
            created_job = True
        else:
            sync_job = _update_coalesced_sync_job_metadata(
                sync_job=existing_job,
                last_trigger=last_trigger,
                requested_policy=policy_decision.policy,
                requested_policy_source=policy_decision.source,
            )
            created_job = False

    start_result = start_pool_master_data_sync_job_workflow(
        sync_job=sync_job,
        correlation_id=normalized_correlation_id,
        origin_system=normalized_origin_system,
        origin_event_id=normalized_origin_event_id,
    )
    if not start_result.enqueue_success:
        enqueue_master_data_sync_conflict(
            tenant_id=normalized_tenant_id,
            database_id=normalized_database_id,
            entity_type=normalized_entity_type,
            conflict_code=MASTER_DATA_SYNC_CONFLICT_APPLY,
            origin_system=normalized_origin_system,
            origin_event_id=normalized_origin_event_id,
            diagnostics={
                "detail": str(start_result.enqueue_error or ""),
                "enqueue_status": str(start_result.enqueue_status or ""),
                "sync_job_id": str(sync_job.id),
                "reconcile_window_id": normalized_window_id,
            },
            metadata={
                "phase": "enqueue_workflow_execution",
                "policy": policy_decision.policy,
                "policy_source": policy_decision.source,
                "reconcile_window_id": normalized_window_id,
            },
        )

    return PoolMasterDataSyncTriggerResult(
        sync_job=start_result.sync_job,
        created_job=created_job,
        started_workflow=bool(start_result.enqueue_success),
        skipped=False,
        skip_reason=None,
        policy=policy_decision.policy,
        policy_source=policy_decision.source,
        start_result=start_result,
    )


def run_pool_master_data_sync_legacy_inbound_route(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
) -> None:
    raise LegacyInboundRouteDisabledError(
        detail=(
            "Legacy inbound route is disabled. "
            f"Use workflow runtime trigger for scope tenant='{tenant_id}', "
            f"database='{database_id}', entity='{entity_type}'."
        ),
    )


def execute_pool_master_data_sync_inbound_step(
    *,
    input_context: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_context = validate_master_data_sync_workflow_input_context(input_context=input_context)
    sync_job = _get_sync_job_for_context(normalized_context=normalized_context)
    runtime_settings = require_pool_master_data_sync_runtime_settings(tenant_id=str(sync_job.tenant_id))
    if not runtime_settings.enabled:
        raise_fail_closed_master_data_sync_conflict(
            tenant_id=str(sync_job.tenant_id),
            database_id=str(sync_job.database_id),
            entity_type=str(sync_job.entity_type),
            conflict_code=MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
            detail="Master-data sync runtime is disabled for tenant.",
            origin_system=str(normalized_context["origin_system"]),
            origin_event_id=str(normalized_context["origin_event_id"]),
            diagnostics={"runtime_gate": MASTER_DATA_SYNC_DISABLED},
        )

    if sync_job.direction not in {
        PoolMasterDataSyncDirection.INBOUND,
        PoolMasterDataSyncDirection.BIDIRECTIONAL,
    }:
        return {
            "step": "master_data_sync.inbound",
            "sync_job_id": str(sync_job.id),
            "skipped": True,
            "reason": "direction_without_inbound",
        }
    if not supports_pool_master_data_capability(
        entity_type=str(sync_job.entity_type),
        capability=POOL_MASTER_DATA_CAPABILITY_SYNC_INBOUND,
    ):
        raise_fail_closed_master_data_sync_conflict(
            tenant_id=str(sync_job.tenant_id),
            database_id=str(sync_job.database_id),
            entity_type=str(sync_job.entity_type),
            conflict_code=MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
            detail="Inbound capability is disabled for master-data entity type.",
            origin_system=str(normalized_context["origin_system"]),
            origin_event_id=str(normalized_context["origin_event_id"]),
            diagnostics={"runtime_gate": MASTER_DATA_SYNC_INBOUND_CAPABILITY_DISABLED},
        )

    if not runtime_settings.inbound_enabled:
        raise_fail_closed_master_data_sync_conflict(
            tenant_id=str(sync_job.tenant_id),
            database_id=str(sync_job.database_id),
            entity_type=str(sync_job.entity_type),
            conflict_code=MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
            detail="Inbound master-data sync runtime is disabled.",
            origin_system=str(normalized_context["origin_system"]),
            origin_event_id=str(normalized_context["origin_event_id"]),
            diagnostics={"runtime_gate": MASTER_DATA_SYNC_INBOUND_DISABLED},
        )

    policy_decision = resolve_effective_pool_master_data_sync_policy(
        tenant_id=str(sync_job.tenant_id),
        entity_type=str(sync_job.entity_type),
        database_id=str(sync_job.database_id),
        default_policy=runtime_settings.default_policy,
    )
    if policy_decision.policy not in {
        PoolMasterDataSyncPolicy.IB_MASTER,
        PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    }:
        raise_fail_closed_master_data_sync_conflict(
            tenant_id=str(sync_job.tenant_id),
            database_id=str(sync_job.database_id),
            entity_type=str(sync_job.entity_type),
            conflict_code=MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
            detail=f"Inbound sync is forbidden by effective policy '{policy_decision.policy}'.",
            origin_system=str(normalized_context["origin_system"]),
            origin_event_id=str(normalized_context["origin_event_id"]),
            diagnostics={"policy": policy_decision.policy, "policy_source": policy_decision.source},
        )

    try:
        inbound_result = _process_pool_master_data_sync_inbound_batch(
            sync_job=sync_job,
        )
    except InboundPollerTransportError as exc:
        raise_fail_closed_master_data_sync_conflict(
            tenant_id=str(sync_job.tenant_id),
            database_id=str(sync_job.database_id),
            entity_type=str(sync_job.entity_type),
            conflict_code=MASTER_DATA_SYNC_CONFLICT_APPLY,
            detail=exc.detail,
            origin_system=str(normalized_context["origin_system"]),
            origin_event_id=str(normalized_context["origin_event_id"]),
            diagnostics={
                "runtime_gate": MASTER_DATA_SYNC_INBOUND_CALLBACKS_NOT_CONFIGURED
                if exc.code == MASTER_DATA_SYNC_INBOUND_CALLBACKS_NOT_CONFIGURED
                else "inbound_transport_error",
                "error_code": exc.code,
                "error_detail": exc.detail,
            },
        )
    except MasterDataDedupeReviewRequiredError as exc:
        raise_fail_closed_master_data_sync_conflict(
            tenant_id=str(sync_job.tenant_id),
            database_id=str(sync_job.database_id),
            entity_type=str(sync_job.entity_type),
            conflict_code=MASTER_DATA_SYNC_CONFLICT_DEDUPE_REVIEW_REQUIRED,
            detail=exc.detail,
            canonical_id=str(exc.canonical_id or ""),
            origin_system=str(normalized_context["origin_system"]),
            origin_event_id=str(normalized_context["origin_event_id"]),
            diagnostics=exc.to_diagnostic(),
            metadata={"runtime_gate": "dedupe_review_required"},
        )
    except MasterDataSyncConflictError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise_fail_closed_master_data_sync_conflict(
            tenant_id=str(sync_job.tenant_id),
            database_id=str(sync_job.database_id),
            entity_type=str(sync_job.entity_type),
            conflict_code=MASTER_DATA_SYNC_CONFLICT_APPLY,
            detail=str(exc) or "inbound apply failed",
            origin_system=str(normalized_context["origin_system"]),
            origin_event_id=str(normalized_context["origin_event_id"]),
            diagnostics={
                "runtime_gate": "inbound_apply_error",
                "error_code": "INBOUND_APPLY_FAILED",
                "error_detail": str(exc) or "inbound apply failed",
            },
        )

    metadata = dict(sync_job.metadata or {})
    metadata["inbound_summary"] = {
        "polled": int(inbound_result.polled),
        "applied": int(inbound_result.applied),
        "duplicates": int(inbound_result.duplicates),
        "ack_scheduled": bool(inbound_result.ack_scheduled),
        "next_checkpoint_token": str(inbound_result.next_checkpoint_token or ""),
        "policy": policy_decision.policy,
        "policy_source": policy_decision.source,
        "at": timezone.now().isoformat(),
    }
    sync_job.policy = policy_decision.policy
    sync_job.metadata = metadata
    update_fields = ["policy", "metadata", "updated_at"]
    if sync_job.started_at is None:
        sync_job.started_at = timezone.now()
        update_fields.append("started_at")
    sync_job.save(update_fields=update_fields)

    return {
        "step": "master_data_sync.inbound",
        "sync_job_id": str(sync_job.id),
        "policy": policy_decision.policy,
        "policy_source": policy_decision.source,
        "inbound": {
            "polled": int(inbound_result.polled),
            "applied": int(inbound_result.applied),
            "duplicates": int(inbound_result.duplicates),
            "ack_scheduled": bool(inbound_result.ack_scheduled),
            "next_checkpoint_token": str(inbound_result.next_checkpoint_token or ""),
        },
    }


def execute_pool_master_data_sync_dispatch_step(
    *,
    input_context: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_context = validate_master_data_sync_workflow_input_context(input_context=input_context)
    sync_job = _get_sync_job_for_context(normalized_context=normalized_context)
    runtime_settings = require_pool_master_data_sync_runtime_settings(tenant_id=str(sync_job.tenant_id))
    if not runtime_settings.enabled:
        raise_fail_closed_master_data_sync_conflict(
            tenant_id=str(sync_job.tenant_id),
            database_id=str(sync_job.database_id),
            entity_type=str(sync_job.entity_type),
            conflict_code=MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
            detail="Master-data sync runtime is disabled for tenant.",
            origin_system=str(normalized_context["origin_system"]),
            origin_event_id=str(normalized_context["origin_event_id"]),
            diagnostics={"runtime_gate": MASTER_DATA_SYNC_DISABLED},
        )

    policy_decision = resolve_effective_pool_master_data_sync_policy(
        tenant_id=str(sync_job.tenant_id),
        entity_type=str(sync_job.entity_type),
        database_id=str(sync_job.database_id),
        default_policy=runtime_settings.default_policy,
    )

    if sync_job.direction in {
        PoolMasterDataSyncDirection.OUTBOUND,
        PoolMasterDataSyncDirection.BIDIRECTIONAL,
    }:
        if not supports_pool_master_data_capability(
            entity_type=str(sync_job.entity_type),
            capability=POOL_MASTER_DATA_CAPABILITY_SYNC_OUTBOUND,
        ):
            raise_fail_closed_master_data_sync_conflict(
                tenant_id=str(sync_job.tenant_id),
                database_id=str(sync_job.database_id),
                entity_type=str(sync_job.entity_type),
                conflict_code=MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
                detail="Outbound capability is disabled for master-data entity type.",
                origin_system=str(normalized_context["origin_system"]),
                origin_event_id=str(normalized_context["origin_event_id"]),
                diagnostics={"runtime_gate": MASTER_DATA_SYNC_OUTBOUND_CAPABILITY_DISABLED},
            )
        if not runtime_settings.outbound_enabled:
            raise_fail_closed_master_data_sync_conflict(
                tenant_id=str(sync_job.tenant_id),
                database_id=str(sync_job.database_id),
                entity_type=str(sync_job.entity_type),
                conflict_code=MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
                detail="Outbound master-data sync runtime is disabled.",
                origin_system=str(normalized_context["origin_system"]),
                origin_event_id=str(normalized_context["origin_event_id"]),
                diagnostics={"runtime_gate": MASTER_DATA_SYNC_OUTBOUND_DISABLED},
            )
        if policy_decision.policy not in {
            PoolMasterDataSyncPolicy.CC_MASTER,
            PoolMasterDataSyncPolicy.BIDIRECTIONAL,
        }:
            raise_fail_closed_master_data_sync_conflict(
                tenant_id=str(sync_job.tenant_id),
                database_id=str(sync_job.database_id),
                entity_type=str(sync_job.entity_type),
                conflict_code=MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
                detail=f"Outbound sync is forbidden by effective policy '{policy_decision.policy}'.",
                origin_system=str(normalized_context["origin_system"]),
                origin_event_id=str(normalized_context["origin_event_id"]),
                diagnostics={"policy": policy_decision.policy, "policy_source": policy_decision.source},
            )
    if sync_job.direction in {
        PoolMasterDataSyncDirection.INBOUND,
        PoolMasterDataSyncDirection.BIDIRECTIONAL,
    }:
        if not supports_pool_master_data_capability(
            entity_type=str(sync_job.entity_type),
            capability=POOL_MASTER_DATA_CAPABILITY_SYNC_INBOUND,
        ):
            raise_fail_closed_master_data_sync_conflict(
                tenant_id=str(sync_job.tenant_id),
                database_id=str(sync_job.database_id),
                entity_type=str(sync_job.entity_type),
                conflict_code=MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
                detail="Inbound capability is disabled for master-data entity type.",
                origin_system=str(normalized_context["origin_system"]),
                origin_event_id=str(normalized_context["origin_event_id"]),
                diagnostics={"runtime_gate": MASTER_DATA_SYNC_INBOUND_CAPABILITY_DISABLED},
            )
        if not runtime_settings.inbound_enabled:
            raise_fail_closed_master_data_sync_conflict(
                tenant_id=str(sync_job.tenant_id),
                database_id=str(sync_job.database_id),
                entity_type=str(sync_job.entity_type),
                conflict_code=MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
                detail="Inbound master-data sync runtime is disabled.",
                origin_system=str(normalized_context["origin_system"]),
                origin_event_id=str(normalized_context["origin_event_id"]),
                diagnostics={"runtime_gate": MASTER_DATA_SYNC_INBOUND_DISABLED},
            )
        if policy_decision.policy not in {
            PoolMasterDataSyncPolicy.IB_MASTER,
            PoolMasterDataSyncPolicy.BIDIRECTIONAL,
        }:
            raise_fail_closed_master_data_sync_conflict(
                tenant_id=str(sync_job.tenant_id),
                database_id=str(sync_job.database_id),
                entity_type=str(sync_job.entity_type),
                conflict_code=MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
                detail=f"Inbound sync is forbidden by effective policy '{policy_decision.policy}'.",
                origin_system=str(normalized_context["origin_system"]),
                origin_event_id=str(normalized_context["origin_event_id"]),
                diagnostics={"policy": policy_decision.policy, "policy_source": policy_decision.source},
            )

    dispatch_claimed = 0
    dispatch_sent = 0
    dispatch_failed = 0
    dispatch_skipped = False
    if sync_job.direction in {
        PoolMasterDataSyncDirection.OUTBOUND,
        PoolMasterDataSyncDirection.BIDIRECTIONAL,
    }:
        dispatch_result = dispatch_pending_master_data_sync_outbox(
            batch_size=runtime_settings.dispatch_batch_size,
            max_retry_backoff_seconds=runtime_settings.max_retry_backoff_seconds,
            tenant_id=str(sync_job.tenant_id),
            database_id=str(sync_job.database_id),
            entity_type=str(sync_job.entity_type),
        )
        dispatch_claimed = int(dispatch_result.claimed)
        dispatch_sent = int(dispatch_result.sent)
        dispatch_failed = int(dispatch_result.failed)
    else:
        dispatch_skipped = True
    metadata = dict(sync_job.metadata or {})
    metadata["dispatch_summary"] = {
        "claimed": dispatch_claimed,
        "sent": dispatch_sent,
        "failed": dispatch_failed,
        "skipped": dispatch_skipped,
        "policy": policy_decision.policy,
        "policy_source": policy_decision.source,
        "at": timezone.now().isoformat(),
    }
    update_fields = ["policy", "metadata", "updated_at"]
    sync_job.policy = policy_decision.policy
    sync_job.metadata = metadata
    if sync_job.started_at is None:
        sync_job.started_at = timezone.now()
        update_fields.append("started_at")
    sync_job.attempt_count = int(sync_job.attempt_count or 0) + 1
    update_fields.append("attempt_count")
    sync_job.save(update_fields=update_fields)

    return {
        "step": "master_data_sync.dispatch",
        "sync_job_id": str(sync_job.id),
        "policy": policy_decision.policy,
        "policy_source": policy_decision.source,
        "dispatch": {
            "claimed": dispatch_claimed,
            "sent": dispatch_sent,
            "failed": dispatch_failed,
            "skipped": dispatch_skipped,
        },
    }


def execute_pool_master_data_sync_finalize_step(
    *,
    input_context: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_context = validate_master_data_sync_workflow_input_context(input_context=input_context)
    sync_job = _get_sync_job_for_context(normalized_context=normalized_context)
    now = timezone.now()
    update_fields = ["updated_at"]
    if sync_job.status not in {
        PoolMasterDataSyncJobStatus.FAILED,
        PoolMasterDataSyncJobStatus.CANCELED,
    }:
        sync_job.status = PoolMasterDataSyncJobStatus.SUCCEEDED
        update_fields.append("status")
    if sync_job.finished_at is None:
        sync_job.finished_at = now
        update_fields.append("finished_at")
    sync_job.save(update_fields=update_fields)
    return {
        "step": "master_data_sync.finalize",
        "sync_job_id": str(sync_job.id),
        "status": str(sync_job.status),
        "finished_at": sync_job.finished_at.isoformat() if sync_job.finished_at else None,
    }


def _process_pool_master_data_sync_inbound_batch(
    *,
    sync_job: PoolMasterDataSyncJob,
):
    select_changes = _INBOUND_SELECT_CHANGES_CALLBACK
    notify_changes_received = _INBOUND_NOTIFY_CHANGES_RECEIVED_CALLBACK
    if select_changes is None:
        def select_changes(*, checkpoint_token, tenant_id, database_id, entity_type, **kwargs):
            _ = kwargs
            try:
                return select_changes_from_live_odata(
                    checkpoint_token=checkpoint_token,
                    tenant_id=tenant_id,
                    database_id=database_id,
                    entity_type=entity_type,
                )
            except MasterDataSyncLiveODataError as exc:
                raise InboundPollerTransportError(code=exc.code, detail=exc.detail) from exc

    if notify_changes_received is None:
        def notify_changes_received(*, checkpoint_token, next_checkpoint_token, tenant_id, database_id, entity_type, **kwargs):
            _ = kwargs
            try:
                return notify_changes_received_from_live_odata(
                    checkpoint_token=checkpoint_token,
                    next_checkpoint_token=next_checkpoint_token,
                    tenant_id=tenant_id,
                    database_id=database_id,
                    entity_type=entity_type,
                )
            except MasterDataSyncLiveODataError as exc:
                raise InboundPollerTransportError(code=exc.code, detail=exc.detail) from exc

    apply_change = _INBOUND_APPLY_CHANGE_CALLBACK
    if apply_change is None:
        def apply_change(*, change, tenant_id, database_id, entity_type, dedupe_fingerprint, **kwargs):
            return _apply_pool_master_data_sync_inbound_change(
                sync_job=sync_job,
                change=change,
                tenant_id=tenant_id,
                database_id=database_id,
                entity_type=entity_type,
                dedupe_fingerprint=dedupe_fingerprint,
            )

    return process_master_data_sync_inbound_batch(
        tenant_id=str(sync_job.tenant_id),
        database_id=str(sync_job.database_id),
        entity_type=str(sync_job.entity_type),
        select_changes=select_changes,
        apply_change=apply_change,
        notify_changes_received=notify_changes_received,
        select_changes_kwargs=dict(_INBOUND_SELECT_CHANGES_KWARGS),
        notify_changes_received_kwargs=dict(_INBOUND_NOTIFY_CHANGES_RECEIVED_KWARGS),
    )


def _apply_pool_master_data_sync_inbound_change(
    *,
    sync_job: PoolMasterDataSyncJob,
    change,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    dedupe_fingerprint: str,
) -> None:
    database = Database.objects.filter(id=str(database_id), tenant_id=str(tenant_id)).first()
    if database is None:
        raise ValueError(
            f"INBOUND_SOURCE_DATABASE_NOT_FOUND: database '{database_id}' is not available in tenant '{tenant_id}'"
        )
    normalized_entity_type = normalize_pool_master_data_entity_type(entity_type)
    change_entity_type = normalize_pool_master_data_entity_type(str(change.entity_type))
    if change_entity_type != normalized_entity_type:
        raise ValueError(
            "INBOUND_ENTITY_TYPE_MISMATCH: "
            f"change entity '{change_entity_type}' != scope '{normalized_entity_type}'"
        )

    payload = dict(change.payload or {})
    source_ref = (
        str(payload.get("source_ref") or "").strip()
        or str(payload.get("ib_ref_key") or "").strip()
        or str(change.canonical_id or "").strip()
    )
    try:
        result = ingest_pool_master_data_source_record(
            tenant_id=str(tenant_id),
            entity_type=normalized_entity_type,
            source_database=database,
            source_ref=source_ref,
            source_canonical_id=str(change.canonical_id or ""),
            canonical_payload=payload,
            origin_kind="sync_inbound",
            origin_ref=str(sync_job.id),
            origin_event_id=str(change.origin_event_id or ""),
            metadata={
                "sync_job_id": str(sync_job.id),
                "source_database_id": str(database.id),
                "origin_system": str(change.origin_system or ""),
                "payload_fingerprint": str(change.payload_fingerprint or ""),
                "dedupe_fingerprint": str(dedupe_fingerprint or ""),
            },
        )
    except MasterDataDedupeReviewRequiredError as exc:
        raise_fail_closed_master_data_sync_conflict(
            tenant_id=str(tenant_id),
            database_id=str(database_id),
            entity_type=normalized_entity_type,
            conflict_code=MASTER_DATA_SYNC_CONFLICT_DEDUPE_REVIEW_REQUIRED,
            detail=exc.detail,
            canonical_id=str(exc.canonical_id or change.canonical_id or ""),
            origin_system=str(change.origin_system or ""),
            origin_event_id=str(change.origin_event_id or ""),
            diagnostics={
                **exc.to_diagnostic(),
                "runtime_gate": "dedupe_review_required",
                "dedupe_fingerprint": str(dedupe_fingerprint or ""),
                "sync_job_id": str(sync_job.id),
            },
            metadata={"sync_job_id": str(sync_job.id)},
        )
    if result.blocked:
        raise MasterDataDedupeReviewRequiredError(
            detail=str(result.detail or "Cross-infobase dedupe review is required."),
            entity_type=normalized_entity_type,
            canonical_id=str(result.canonical_id or change.canonical_id or ""),
            cluster_id=str(result.cluster.id) if result.cluster is not None else "",
            review_item_id=str(result.review_item.id) if result.review_item is not None else "",
            reason_code=str(result.reason_code or MASTER_DATA_SYNC_DEDUPE_REVIEW_REQUIRED),
        )


def _get_sync_job_for_context(*, normalized_context: Mapping[str, Any]) -> PoolMasterDataSyncJob:
    sync_job = PoolMasterDataSyncJob.objects.filter(id=str(normalized_context["sync_job_id"])).first()
    if sync_job is None:
        raise ValueError(
            f"POOL_MASTER_DATA_SYNC_JOB_NOT_FOUND: sync_job '{normalized_context['sync_job_id']}' was not found"
        )
    if str(sync_job.tenant_id) != str(normalized_context["tenant_id"]):
        raise ValueError(
            "POOL_MASTER_DATA_SYNC_JOB_TENANT_MISMATCH: "
            f"job tenant '{sync_job.tenant_id}' != context tenant '{normalized_context['tenant_id']}'"
        )
    if str(sync_job.database_id) != str(normalized_context["database_id"]):
        raise ValueError(
            "POOL_MASTER_DATA_SYNC_JOB_DATABASE_MISMATCH: "
            f"job database '{sync_job.database_id}' != context database '{normalized_context['database_id']}'"
        )
    if str(sync_job.entity_type) != str(normalized_context["entity_type"]):
        raise ValueError(
            "POOL_MASTER_DATA_SYNC_JOB_ENTITY_MISMATCH: "
            f"job entity '{sync_job.entity_type}' != context entity '{normalized_context['entity_type']}'"
        )
    return sync_job


__all__ = [
    "LegacyInboundRouteDisabledError",
    "MASTER_DATA_SYNC_INBOUND_CALLBACKS_NOT_CONFIGURED",
    "SYNC_LEGACY_INBOUND_ROUTE_DISABLED",
    "PoolMasterDataSyncPolicyDecision",
    "PoolMasterDataSyncTriggerResult",
    "configure_pool_master_data_sync_inbound_callbacks",
    "execute_pool_master_data_sync_dispatch_step",
    "execute_pool_master_data_sync_finalize_step",
    "execute_pool_master_data_sync_inbound_step",
    "reset_pool_master_data_sync_inbound_callbacks",
    "run_pool_master_data_sync_legacy_inbound_route",
    "resolve_effective_pool_master_data_sync_policy",
    "trigger_pool_master_data_inbound_sync_job",
    "trigger_pool_master_data_outbound_sync_job",
    "trigger_pool_master_data_reconcile_sync_job",
]
