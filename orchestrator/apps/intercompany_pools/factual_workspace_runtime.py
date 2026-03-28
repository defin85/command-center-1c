from __future__ import annotations

from datetime import date, datetime, timedelta

from django.db.models import Q
from django.utils import timezone

from .factual_sync_runtime import FACTUAL_SYNC_FRESHNESS_TARGET_SECONDS
from .factual_workflow_runtime import start_pool_factual_sync_workflow
from .models import PoolFactualLane, PoolFactualSyncCheckpoint, PoolNodeVersion


DEFAULT_FACTUAL_ACCOUNT_CODES = ("62.01", "90.01")
DEFAULT_FACTUAL_MOVEMENT_KINDS = ("credit", "debit")
FACTUAL_WORKSPACE_ORIGIN_SYSTEM = "pools_factual_workspace"


def ensure_pool_factual_workspace_default_sync(
    *,
    pool,
    quarter_start: date,
    now: datetime | None = None,
) -> tuple[PoolFactualSyncCheckpoint, ...]:
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
    databases = [
        node.organization.database
        for node in active_nodes
        if getattr(node.organization, "database_id", None) and node.organization.database.tenant_id == pool.tenant_id
    ]
    databases = list({str(database.id): database for database in databases}.values())

    if not organization_ids or not databases:
        return tuple()

    quarter_end = _resolve_quarter_end(quarter_start)
    freeze_quarter = quarter_end < _current_quarter_start(timestamp.date())
    checkpoints: list[PoolFactualSyncCheckpoint] = []

    for database in databases:
        checkpoint, _ = PoolFactualSyncCheckpoint.objects.get_or_create(
            tenant=pool.tenant,
            pool=pool,
            database=database,
            lane=PoolFactualLane.READ,
            quarter_start=quarter_start,
            defaults={
                "quarter_end": quarter_end,
                "metadata": {
                    "default_entrypoint": "pools_factual_workspace",
                },
            },
        )
        checkpoints.append(checkpoint)
        if not _checkpoint_requires_sync(checkpoint=checkpoint, now=timestamp):
            continue
        result = start_pool_factual_sync_workflow(
            checkpoint=checkpoint,
            database=database,
            organization_ids=organization_ids,
            account_codes=DEFAULT_FACTUAL_ACCOUNT_CODES,
            movement_kinds=DEFAULT_FACTUAL_MOVEMENT_KINDS,
            correlation_id=f"workspace:{pool.id}:{quarter_start.isoformat()}",
            origin_system=FACTUAL_WORKSPACE_ORIGIN_SYSTEM,
            origin_event_id=f"pool:{pool.id}:quarter:{quarter_start.isoformat()}",
            activity="active",
            freeze_quarter=freeze_quarter,
        )
        checkpoints[-1] = result.checkpoint

    return tuple(checkpoints)


def _checkpoint_requires_sync(*, checkpoint: PoolFactualSyncCheckpoint, now: datetime) -> bool:
    workflow_status = str(checkpoint.workflow_status or "").strip().lower()
    if workflow_status in {"pending", "running"}:
        return False
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
    "ensure_pool_factual_workspace_default_sync",
]
