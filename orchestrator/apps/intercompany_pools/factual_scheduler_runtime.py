from __future__ import annotations

from datetime import datetime

from django.utils import timezone

from .factual_scope_selection import (
    DEFAULT_FACTUAL_MOVEMENT_KINDS,
    FactualScopeSelectionError,
    resolve_pool_factual_sync_scope_for_database,
)
from .factual_workspace_runtime import (
    PoolFactualScope,
    _checkpoint_requires_sync,
    _current_quarter_start,
    _get_or_create_checkpoint_for_scope,
    _update_checkpoint_scope_contract,
    ensure_pool_factual_workspace_default_sync,
    resolve_pool_factual_scope,
)
from .factual_sync_runtime import (
    FactualSyncTransportError,
    mark_factual_sync_checkpoint_error,
    resolve_factual_sync_source_state,
)
from .factual_workflow_runtime import start_pool_factual_sync_workflow
from .models import OrganizationPool, PoolFactualLane, PoolFactualSyncCheckpoint


FACTUAL_ACTIVE_SYNC_ORIGIN_SYSTEM = "pools_factual_scheduler"
FACTUAL_RECONCILE_SYNC_ORIGIN_SYSTEM = "pools_factual_reconcile_scheduler"


def trigger_pool_factual_active_sync_window(
    *,
    now: datetime | None = None,
    tenant_id: str | None = None,
) -> dict[str, int | str]:
    timestamp = now or timezone.now()
    quarter_start = _current_quarter_start(timestamp.date())
    pools = OrganizationPool.objects.filter(is_active=True)
    if tenant_id:
        pools = pools.filter(tenant_id=tenant_id)

    pools_scanned = 0
    checkpoints_touched = 0
    checkpoints_running = 0
    for pool in pools.order_by("tenant_id", "code", "id"):
        pools_scanned += 1
        checkpoints = ensure_pool_factual_workspace_default_sync(
            pool=pool,
            quarter_start=quarter_start,
            now=timestamp,
        )
        checkpoints_touched += len(checkpoints)
        checkpoints_running += sum(
            1
            for checkpoint in checkpoints
            if str(checkpoint.workflow_status or "").strip().lower() in {"pending", "running"}
        )

    return {
        "quarter_start": quarter_start.isoformat(),
        "pools_scanned": pools_scanned,
        "checkpoints_touched": checkpoints_touched,
        "checkpoints_running": checkpoints_running,
    }


def trigger_pool_factual_closed_quarter_reconcile_window(
    *,
    now: datetime | None = None,
    tenant_id: str | None = None,
) -> dict[str, int | str]:
    timestamp = now or timezone.now()
    quarter_cutoff_start = _current_quarter_start(timestamp.date())
    read_checkpoints = (
        PoolFactualSyncCheckpoint.objects.select_related("tenant", "pool", "database")
        .filter(
            lane=PoolFactualLane.READ,
            quarter_end__lt=quarter_cutoff_start,
            pool__is_active=True,
            metadata__has_key="frozen_at",
        )
        .order_by("tenant_id", "pool_id", "database_id", "quarter_start", "id")
    )
    if tenant_id:
        read_checkpoints = read_checkpoints.filter(tenant_id=tenant_id)

    seen_scopes: set[tuple[str, str, str, str]] = set()
    read_checkpoints_scanned = 0
    reconcile_checkpoints_touched = 0
    reconcile_checkpoints_created = 0
    reconcile_checkpoints_running = 0

    for read_checkpoint in read_checkpoints:
        read_checkpoints_scanned += 1
        scope_key = (
            str(read_checkpoint.tenant_id),
            str(read_checkpoint.pool_id),
            str(read_checkpoint.database_id),
            read_checkpoint.quarter_start.isoformat(),
        )
        if scope_key in seen_scopes:
            continue
        seen_scopes.add(scope_key)

        scope = resolve_pool_factual_scope(
            pool=read_checkpoint.pool,
            quarter_start=read_checkpoint.quarter_start,
            now=timestamp,
        )
        if not scope.organization_ids or not _scope_contains_database(scope=scope, database_id=str(read_checkpoint.database_id)):
            continue

        try:
            factual_scope = resolve_pool_factual_sync_scope_for_database(
                pool=read_checkpoint.pool,
                database=read_checkpoint.database,
                quarter_start=read_checkpoint.quarter_start,
                quarter_end=read_checkpoint.quarter_end,
                organization_ids=scope.organization_ids,
                movement_kinds=DEFAULT_FACTUAL_MOVEMENT_KINDS,
                verify_live_bindings=True,
            )
        except FactualScopeSelectionError as exc:
            reconcile_checkpoint, created = _get_or_create_checkpoint_for_scope(
                tenant=read_checkpoint.tenant,
                pool=read_checkpoint.pool,
                database=read_checkpoint.database,
                lane=PoolFactualLane.RECONCILE,
                quarter_start=read_checkpoint.quarter_start,
                quarter_end=read_checkpoint.quarter_end,
                scope_fingerprint=exc.scope.scope_fingerprint,
                default_entrypoint="pools_factual_reconcile_scheduler",
            )
            _update_checkpoint_scope_contract(
                checkpoint=reconcile_checkpoint,
                scope=exc.scope,
                default_entrypoint="pools_factual_reconcile_scheduler",
                extra_metadata={"scope_resolution_blockers": list(exc.blockers)},
            )
            reconcile_checkpoints_touched += 1
            if created:
                reconcile_checkpoints_created += 1
            mark_factual_sync_checkpoint_error(
                checkpoint=reconcile_checkpoint,
                scope=exc.scope,
                source_state=resolve_factual_sync_source_state(database=read_checkpoint.database, now=timestamp),
                error=FactualSyncTransportError(code=exc.code, detail=exc.detail),
                failed_at=timestamp,
            )
            continue

        reconcile_checkpoint, created = _get_or_create_checkpoint_for_scope(
            tenant=read_checkpoint.tenant,
            pool=read_checkpoint.pool,
            database=read_checkpoint.database,
            lane=PoolFactualLane.RECONCILE,
            quarter_start=read_checkpoint.quarter_start,
            quarter_end=read_checkpoint.quarter_end,
            scope_fingerprint=factual_scope.scope_fingerprint,
            default_entrypoint="pools_factual_reconcile_scheduler",
        )
        reconcile_checkpoint = _update_checkpoint_scope_contract(
            checkpoint=reconcile_checkpoint,
            scope=factual_scope,
            default_entrypoint="pools_factual_reconcile_scheduler",
        )
        reconcile_checkpoints_touched += 1
        if created:
            reconcile_checkpoints_created += 1
        if not _checkpoint_requires_sync(checkpoint=reconcile_checkpoint, now=timestamp):
            continue

        result = start_pool_factual_sync_workflow(
            checkpoint=reconcile_checkpoint,
            database=read_checkpoint.database,
            organization_ids=scope.organization_ids,
            account_codes=factual_scope.account_codes,
            movement_kinds=DEFAULT_FACTUAL_MOVEMENT_KINDS,
            correlation_id=f"reconcile-scheduler:{read_checkpoint.pool_id}:{read_checkpoint.quarter_start.isoformat()}",
            origin_system=FACTUAL_RECONCILE_SYNC_ORIGIN_SYSTEM,
            origin_event_id=(
                f"pool:{read_checkpoint.pool_id}:quarter:{read_checkpoint.quarter_start.isoformat()}:reconcile"
            ),
            activity="cold",
            freeze_quarter=True,
            scope=factual_scope,
        )
        if result.enqueue_success or str(result.enqueue_status or "").strip().lower() in {"pending", "running"}:
            reconcile_checkpoints_running += 1

    return {
        "quarter_cutoff_start": quarter_cutoff_start.isoformat(),
        "read_checkpoints_scanned": read_checkpoints_scanned,
        "reconcile_checkpoints_touched": reconcile_checkpoints_touched,
        "reconcile_checkpoints_created": reconcile_checkpoints_created,
        "reconcile_checkpoints_running": reconcile_checkpoints_running,
    }


def _scope_contains_database(*, scope: PoolFactualScope, database_id: str) -> bool:
    return any(str(database.id) == database_id for database in scope.databases)


__all__ = [
    "FACTUAL_ACTIVE_SYNC_ORIGIN_SYSTEM",
    "FACTUAL_RECONCILE_SYNC_ORIGIN_SYSTEM",
    "trigger_pool_factual_active_sync_window",
    "trigger_pool_factual_closed_quarter_reconcile_window",
]
