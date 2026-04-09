from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.db.models import Q
from django.utils import timezone

from apps.templates.workflow.models import WorkflowExecution

from .factual_result_projection import sync_pool_factual_checkpoint_state_from_execution
from .factual_scheduling import resolve_factual_polling_tier
from .factual_scope_selection import (
    DEFAULT_FACTUAL_ACCOUNT_CODES,
    DEFAULT_FACTUAL_MOVEMENT_KINDS,
    FactualScopeSelectionError,
    resolve_pool_factual_sync_scope_for_database,
)
from .factual_sync_runtime import (
    FACTUAL_SYNC_FRESHNESS_TARGET_SECONDS,
    FactualSyncTransportError,
    mark_factual_sync_checkpoint_error,
    resolve_factual_sync_source_state,
)
from .factual_workflow_runtime import start_pool_factual_sync_workflow
from .models import (
    PoolBatchSettlement,
    PoolBatchSettlementStatus,
    PoolFactualBalanceSnapshot,
    PoolFactualLane,
    PoolFactualReviewItem,
    PoolFactualReviewStatus,
    PoolFactualSyncCheckpoint,
    PoolNodeVersion,
)


FACTUAL_WORKSPACE_ORIGIN_SYSTEM = "pools_factual_workspace"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PoolFactualScope:
    organization_ids: tuple[str, ...]
    databases: tuple
    quarter_end: date
    freeze_quarter: bool


@dataclass(frozen=True)
class PoolFactualActivityDecision:
    activity: str
    polling_tier: str
    poll_interval_seconds: int
    freshness_target_seconds: int
    reason: str


def ensure_pool_factual_workspace_default_sync(
    *,
    pool,
    quarter_start: date,
    now: datetime | None = None,
    requested_activity: str | None = None,
    force_sync: bool = False,
) -> tuple[PoolFactualSyncCheckpoint, ...]:
    timestamp = now or timezone.now()
    scope = resolve_pool_factual_scope(
        pool=pool,
        quarter_start=quarter_start,
        now=timestamp,
    )
    if not scope.organization_ids or not scope.databases:
        return tuple()
    activity_decision = resolve_pool_factual_sync_activity(
        pool=pool,
        quarter_start=quarter_start,
        quarter_end=scope.quarter_end,
        now=timestamp,
        requested_activity=requested_activity,
    )
    checkpoints: list[PoolFactualSyncCheckpoint] = []

    for database in scope.databases:
        try:
            factual_scope = resolve_pool_factual_sync_scope_for_database(
                pool=pool,
                database=database,
                quarter_start=quarter_start,
                quarter_end=scope.quarter_end,
                organization_ids=scope.organization_ids,
                movement_kinds=DEFAULT_FACTUAL_MOVEMENT_KINDS,
                verify_live_bindings=True,
            )
        except FactualScopeSelectionError as exc:
            checkpoint, _ = _get_or_create_checkpoint_for_scope(
                tenant=pool.tenant,
                pool=pool,
                database=database,
                lane=PoolFactualLane.READ,
                quarter_start=quarter_start,
                quarter_end=scope.quarter_end,
                scope_fingerprint=exc.scope.scope_fingerprint,
                default_entrypoint="pools_factual_workspace",
            )
            _update_checkpoint_scope_contract(
                checkpoint=checkpoint,
                scope=exc.scope,
                default_entrypoint="pools_factual_workspace",
                extra_metadata={
                    **_build_activity_metadata(activity_decision=activity_decision),
                    "scope_resolution_blockers": list(exc.blockers),
                },
            )
            mark_factual_sync_checkpoint_error(
                checkpoint=checkpoint,
                scope=exc.scope,
                source_state=resolve_factual_sync_source_state(database=database, now=timestamp),
                error=FactualSyncTransportError(code=exc.code, detail=exc.detail),
                failed_at=timestamp,
                activity=activity_decision.activity,
                polling_tier=activity_decision.polling_tier,
                poll_interval_seconds=activity_decision.poll_interval_seconds,
                freshness_target_seconds=activity_decision.freshness_target_seconds,
            )
            checkpoints.append(PoolFactualSyncCheckpoint.objects.get(id=checkpoint.id))
            continue

        checkpoint, _ = _get_or_create_checkpoint_for_scope(
            tenant=pool.tenant,
            pool=pool,
            database=database,
            lane=PoolFactualLane.READ,
            quarter_start=quarter_start,
            quarter_end=scope.quarter_end,
            scope_fingerprint=factual_scope.scope_fingerprint,
            default_entrypoint="pools_factual_workspace",
        )
        checkpoint = _update_checkpoint_scope_contract(
            checkpoint=checkpoint,
            scope=factual_scope,
            default_entrypoint="pools_factual_workspace",
            extra_metadata=_build_activity_metadata(activity_decision=activity_decision),
        )
        checkpoint = _reconcile_checkpoint_workflow_state(checkpoint=checkpoint)
        checkpoints.append(checkpoint)
        if not _checkpoint_requires_sync(checkpoint=checkpoint, now=timestamp, force_sync=force_sync):
            continue
        result = start_pool_factual_sync_workflow(
            checkpoint=checkpoint,
            database=database,
            organization_ids=scope.organization_ids,
            account_codes=factual_scope.account_codes,
            movement_kinds=DEFAULT_FACTUAL_MOVEMENT_KINDS,
            correlation_id=f"workspace:{pool.id}:{quarter_start.isoformat()}",
            origin_system=FACTUAL_WORKSPACE_ORIGIN_SYSTEM,
            origin_event_id=f"pool:{pool.id}:quarter:{quarter_start.isoformat()}",
            activity=activity_decision.activity,
            freeze_quarter=scope.freeze_quarter,
            scope=factual_scope,
        )
        checkpoints[-1] = result.checkpoint

    return tuple(checkpoints)


def _reconcile_checkpoint_workflow_state(
    *,
    checkpoint: PoolFactualSyncCheckpoint,
) -> PoolFactualSyncCheckpoint:
    current_status = str(checkpoint.workflow_status or "").strip().lower()
    if current_status not in {"pending", "running"} or not checkpoint.workflow_execution_id:
        return checkpoint

    execution = WorkflowExecution.objects.filter(id=checkpoint.workflow_execution_id).first()
    if execution is None:
        return checkpoint

    execution_status = str(getattr(execution, "status", "") or "").strip().lower()
    if execution_status in {"pending", "running"}:
        return checkpoint

    try:
        sync_pool_factual_checkpoint_state_from_execution(execution=execution)
    except Exception:  # pragma: no cover - defensive guard for malformed legacy executions
        logger.warning(
            "Failed to reconcile factual checkpoint %s from workflow execution %s",
            checkpoint.id,
            checkpoint.workflow_execution_id,
            exc_info=True,
        )
        return checkpoint

    return PoolFactualSyncCheckpoint.objects.get(id=checkpoint.id)


def resolve_pool_factual_scope(
    *,
    pool,
    quarter_start: date,
    now: datetime | None = None,
) -> PoolFactualScope:
    timestamp = now or timezone.now()
    active_nodes = list(
        PoolNodeVersion.objects.filter(
            pool=pool,
            effective_from__lte=quarter_start,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=quarter_start))
        .select_related("organization", "organization__database")
    )
    organization_ids = tuple(
        sorted(
            {
                str(node.organization_id)
                for node in active_nodes
            }
        )
    )
    databases = tuple(
        {str(database.id): database for database in [
            node.organization.database
            for node in active_nodes
            if getattr(node.organization, "database_id", None) and node.organization.database.tenant_id == pool.tenant_id
        ]}.values()
    )
    quarter_end = _resolve_quarter_end(quarter_start)
    freeze_quarter = quarter_end < _current_quarter_start(timestamp.date())
    return PoolFactualScope(
        organization_ids=organization_ids,
        databases=databases,
        quarter_end=quarter_end,
        freeze_quarter=freeze_quarter,
    )


def resolve_pool_factual_sync_activity(
    *,
    pool,
    quarter_start: date,
    quarter_end: date | None = None,
    now: datetime | None = None,
    requested_activity: str | None = None,
) -> PoolFactualActivityDecision:
    if requested_activity:
        tier = resolve_factual_polling_tier(activity=requested_activity)
        return PoolFactualActivityDecision(
            activity=tier.name,
            polling_tier=tier.name,
            poll_interval_seconds=tier.interval_seconds,
            freshness_target_seconds=tier.interval_seconds,
            reason="requested_override",
        )

    timestamp = now or timezone.now()
    current_quarter_start = _current_quarter_start(timestamp.date())
    if quarter_start >= current_quarter_start:
        tier = resolve_factual_polling_tier(activity="active")
        return PoolFactualActivityDecision(
            activity=tier.name,
            polling_tier=tier.name,
            poll_interval_seconds=tier.interval_seconds,
            freshness_target_seconds=tier.interval_seconds,
            reason="current_quarter",
        )

    resolved_quarter_end = quarter_end or _resolve_quarter_end(quarter_start)
    activity = (
        "warm"
        if _is_operationally_relevant_factual_context(
            pool=pool,
            quarter_start=quarter_start,
            quarter_end=resolved_quarter_end,
        )
        else "cold"
    )
    tier = resolve_factual_polling_tier(activity=activity)
    return PoolFactualActivityDecision(
        activity=tier.name,
        polling_tier=tier.name,
        poll_interval_seconds=tier.interval_seconds,
        freshness_target_seconds=tier.interval_seconds,
        reason="open_context" if activity == "warm" else "low_activity",
    )


def _checkpoint_requires_sync(
    *,
    checkpoint: PoolFactualSyncCheckpoint,
    now: datetime,
    force_sync: bool = False,
) -> bool:
    workflow_status = str(checkpoint.workflow_status or "").strip().lower()
    if workflow_status in {"pending", "running"}:
        return False
    if force_sync:
        return True
    if workflow_status == "failed":
        return True
    if checkpoint.last_synced_at is None:
        return True

    metadata = checkpoint.metadata if isinstance(checkpoint.metadata, dict) else {}
    freshness_target = metadata.get("freshness_target_seconds")
    try:
        freshness_target_seconds = int(freshness_target)
    except (TypeError, ValueError):
        freshness_target_seconds = FACTUAL_SYNC_FRESHNESS_TARGET_SECONDS

    return checkpoint.last_synced_at <= now - timedelta(seconds=max(freshness_target_seconds, 1))


def _build_activity_metadata(*, activity_decision: PoolFactualActivityDecision) -> dict[str, object]:
    return {
        "activity": activity_decision.activity,
        "polling_tier": activity_decision.polling_tier,
        "poll_interval_seconds": int(activity_decision.poll_interval_seconds),
        "freshness_target_seconds": int(activity_decision.freshness_target_seconds),
        "activity_reason": activity_decision.reason,
    }


def _is_operationally_relevant_factual_context(
    *,
    pool,
    quarter_start: date,
    quarter_end: date,
) -> bool:
    if PoolFactualReviewItem.objects.filter(
        tenant=pool.tenant,
        pool=pool,
        quarter_start=quarter_start,
        quarter_end=quarter_end,
        status=PoolFactualReviewStatus.PENDING,
    ).exists():
        return True

    if PoolBatchSettlement.objects.filter(
        tenant=pool.tenant,
        batch__pool=pool,
        batch__period_start__gte=quarter_start,
        batch__period_start__lte=quarter_end,
    ).exclude(status=PoolBatchSettlementStatus.CLOSED).exists():
        return True

    return PoolFactualBalanceSnapshot.objects.filter(
        tenant=pool.tenant,
        pool=pool,
        quarter_start=quarter_start,
        quarter_end=quarter_end,
    ).exclude(open_balance=0).exists()


def _get_or_create_checkpoint_for_scope(
    *,
    tenant,
    pool,
    database,
    lane: str,
    quarter_start: date,
    quarter_end: date,
    scope_fingerprint: str,
    default_entrypoint: str,
) -> tuple[PoolFactualSyncCheckpoint, bool]:
    exact_checkpoint = (
        PoolFactualSyncCheckpoint.objects.filter(
            tenant=tenant,
            pool=pool,
            database=database,
            lane=lane,
            quarter_start=quarter_start,
            scope_fingerprint=scope_fingerprint,
        )
        .order_by("-updated_at", "-created_at")
        .first()
    )
    if exact_checkpoint is not None:
        return exact_checkpoint, False

    legacy_checkpoint = (
        PoolFactualSyncCheckpoint.objects.filter(
            tenant=tenant,
            pool=pool,
            database=database,
            lane=lane,
            quarter_start=quarter_start,
            scope_fingerprint="",
        )
        .order_by("-last_synced_at", "-updated_at", "-created_at")
        .first()
    )
    if legacy_checkpoint is not None:
        update_fields: list[str] = []
        if legacy_checkpoint.quarter_end != quarter_end:
            legacy_checkpoint.quarter_end = quarter_end
            update_fields.append("quarter_end")
        if legacy_checkpoint.scope_fingerprint != scope_fingerprint:
            legacy_checkpoint.scope_fingerprint = scope_fingerprint
            update_fields.append("scope_fingerprint")
        metadata = dict(legacy_checkpoint.metadata or {})
        if not str(metadata.get("default_entrypoint") or "").strip():
            legacy_checkpoint.metadata = {
                **metadata,
                "default_entrypoint": default_entrypoint,
            }
            update_fields.append("metadata")
        if update_fields:
            legacy_checkpoint.save(update_fields=[*update_fields, "updated_at"])
        return legacy_checkpoint, False

    return (
        PoolFactualSyncCheckpoint.objects.create(
            tenant=tenant,
            pool=pool,
            database=database,
            lane=lane,
            quarter_start=quarter_start,
            quarter_end=quarter_end,
            scope_fingerprint=scope_fingerprint,
            metadata={
                "default_entrypoint": default_entrypoint,
            },
        ),
        True,
    )


def _update_checkpoint_scope_contract(
    *,
    checkpoint: PoolFactualSyncCheckpoint,
    scope,
    default_entrypoint: str,
    extra_metadata: dict[str, object] | None = None,
) -> PoolFactualSyncCheckpoint:
    metadata = dict(checkpoint.metadata or {})
    factual_scope_contract = scope.as_factual_scope_contract()
    next_metadata = {
        **metadata,
        "default_entrypoint": default_entrypoint,
        "scope_fingerprint": scope.scope_fingerprint,
        "source_profile": scope.source_profile,
        "source_scope": scope.as_metadata(),
    }
    if factual_scope_contract:
        next_metadata["factual_scope_contract"] = factual_scope_contract
    if extra_metadata:
        next_metadata.update(extra_metadata)
    update_fields: list[str] = []
    if checkpoint.quarter_end != scope.quarter_end:
        checkpoint.quarter_end = scope.quarter_end
        update_fields.append("quarter_end")
    if checkpoint.scope_fingerprint != scope.scope_fingerprint:
        checkpoint.scope_fingerprint = scope.scope_fingerprint
        update_fields.append("scope_fingerprint")
    if checkpoint.metadata != next_metadata:
        checkpoint.metadata = next_metadata
        update_fields.append("metadata")
    if update_fields:
        checkpoint.save(update_fields=[*update_fields, "updated_at"])
    return checkpoint


def _current_quarter_start(current_date: date) -> date:
    month = ((current_date.month - 1) // 3) * 3 + 1
    return date(current_date.year, month, 1)


def _resolve_quarter_end(quarter_start: date) -> date:
    if quarter_start.month == 10:
        next_quarter_start = date(quarter_start.year + 1, 1, 1)
    else:
        next_quarter_start = date(quarter_start.year, quarter_start.month + 3, 1)
    return next_quarter_start - timedelta(days=1)


__all__ = [
    "DEFAULT_FACTUAL_ACCOUNT_CODES",
    "DEFAULT_FACTUAL_MOVEMENT_KINDS",
    "FACTUAL_WORKSPACE_ORIGIN_SYSTEM",
    "PoolFactualActivityDecision",
    "PoolFactualScope",
    "_get_or_create_checkpoint_for_scope",
    "_checkpoint_requires_sync",
    "_current_quarter_start",
    "ensure_pool_factual_workspace_default_sync",
    "resolve_pool_factual_sync_activity",
    "resolve_pool_factual_scope",
]
