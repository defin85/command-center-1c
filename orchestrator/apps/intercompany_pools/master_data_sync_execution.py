from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from .master_data_sync_conflicts import (
    MASTER_DATA_SYNC_CONFLICT_APPLY,
    MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
    MasterDataSyncConflictError,
    enqueue_master_data_sync_conflict,
    raise_fail_closed_master_data_sync_conflict,
)
from .master_data_sync_dispatcher import dispatch_pending_master_data_sync_outbox
from .master_data_sync_policy import resolve_pool_master_data_sync_policy
from .master_data_sync_runtime_settings import require_pool_master_data_sync_runtime_settings
from .master_data_sync_workflow_contract import validate_master_data_sync_workflow_input_context
from .master_data_sync_workflow_runtime import (
    PoolMasterDataSyncWorkflowStartResult,
    start_pool_master_data_sync_job_workflow,
)
from .models import (
    PoolMasterDataEntityType,
    PoolMasterDataSyncDirection,
    PoolMasterDataSyncJob,
    PoolMasterDataSyncJobStatus,
    PoolMasterDataSyncPolicy,
)

MASTER_DATA_SYNC_DISABLED = "MASTER_DATA_SYNC_DISABLED"
MASTER_DATA_SYNC_OUTBOUND_DISABLED = "MASTER_DATA_SYNC_OUTBOUND_DISABLED"
MASTER_DATA_SYNC_INBOUND_DISABLED = "MASTER_DATA_SYNC_INBOUND_DISABLED"


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
    normalized_entity_type = str(entity_type or "").strip()
    normalized_origin_system = str(origin_system or "cc").strip().lower() or "cc"
    normalized_origin_event_id = str(origin_event_id or "").strip() or f"evt-{uuid4()}"
    normalized_canonical_id = str(canonical_id or "").strip()
    normalized_correlation_id = str(correlation_id or "").strip() or f"corr-{uuid4()}"

    if normalized_entity_type not in set(PoolMasterDataEntityType.values):
        raise ValueError(f"Unsupported master-data entity_type '{entity_type}'")

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
        existing_job = (
            PoolMasterDataSyncJob.objects.select_for_update()
            .filter(
                tenant_id=normalized_tenant_id,
                database_id=normalized_database_id,
                entity_type=normalized_entity_type,
                status__in=[PoolMasterDataSyncJobStatus.PENDING, PoolMasterDataSyncJobStatus.RUNNING],
            )
            .order_by("-created_at")
            .first()
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
                    "last_trigger": {
                        "canonical_id": normalized_canonical_id,
                        "origin_system": normalized_origin_system,
                        "origin_event_id": normalized_origin_event_id,
                        "at": timezone.now().isoformat(),
                    },
                },
            )
            created_job = True
        else:
            sync_job = existing_job
            metadata = dict(sync_job.metadata or {})
            metadata["trigger_count"] = int(metadata.get("trigger_count") or 0) + 1
            metadata["policy_source"] = policy_decision.source
            metadata["last_trigger"] = {
                "canonical_id": normalized_canonical_id,
                "origin_system": normalized_origin_system,
                "origin_event_id": normalized_origin_event_id,
                "at": timezone.now().isoformat(),
            }
            sync_job.policy = policy_decision.policy
            sync_job.direction = PoolMasterDataSyncDirection.OUTBOUND
            sync_job.metadata = metadata
            sync_job.save(update_fields=["policy", "direction", "metadata", "updated_at"])
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

    dispatch_result = dispatch_pending_master_data_sync_outbox(
        batch_size=runtime_settings.dispatch_batch_size,
        max_retry_backoff_seconds=runtime_settings.max_retry_backoff_seconds,
        tenant_id=str(sync_job.tenant_id),
        database_id=str(sync_job.database_id),
        entity_type=str(sync_job.entity_type),
    )
    metadata = dict(sync_job.metadata or {})
    metadata["dispatch_summary"] = {
        "claimed": int(dispatch_result.claimed),
        "sent": int(dispatch_result.sent),
        "failed": int(dispatch_result.failed),
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
            "claimed": int(dispatch_result.claimed),
            "sent": int(dispatch_result.sent),
            "failed": int(dispatch_result.failed),
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
    "PoolMasterDataSyncPolicyDecision",
    "PoolMasterDataSyncTriggerResult",
    "execute_pool_master_data_sync_dispatch_step",
    "execute_pool_master_data_sync_finalize_step",
    "resolve_effective_pool_master_data_sync_policy",
    "trigger_pool_master_data_outbound_sync_job",
]
