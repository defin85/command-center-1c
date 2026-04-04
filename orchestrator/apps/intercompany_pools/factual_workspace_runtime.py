from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.db.models import Q
from django.utils import timezone

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
from .models import PoolFactualLane, PoolFactualSyncCheckpoint, PoolNodeVersion


FACTUAL_WORKSPACE_ORIGIN_SYSTEM = "pools_factual_workspace"


@dataclass(frozen=True)
class PoolFactualScope:
    organization_ids: tuple[str, ...]
    databases: tuple
    quarter_end: date
    freeze_quarter: bool


def ensure_pool_factual_workspace_default_sync(
    *,
    pool,
    quarter_start: date,
    now: datetime | None = None,
) -> tuple[PoolFactualSyncCheckpoint, ...]:
    timestamp = now or timezone.now()
    scope = resolve_pool_factual_scope(
        pool=pool,
        quarter_start=quarter_start,
        now=timestamp,
    )
    if not scope.organization_ids or not scope.databases:
        return tuple()
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
                extra_metadata={"scope_resolution_blockers": list(exc.blockers)},
            )
            mark_factual_sync_checkpoint_error(
                checkpoint=checkpoint,
                scope=exc.scope,
                source_state=resolve_factual_sync_source_state(database=database, now=timestamp),
                error=FactualSyncTransportError(code=exc.code, detail=exc.detail),
                failed_at=timestamp,
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
        )
        checkpoints.append(checkpoint)
        if not _checkpoint_requires_sync(checkpoint=checkpoint, now=timestamp):
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
            activity="active",
            freeze_quarter=scope.freeze_quarter,
            scope=factual_scope,
        )
        checkpoints[-1] = result.checkpoint

    return tuple(checkpoints)


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
    "PoolFactualScope",
    "_get_or_create_checkpoint_for_scope",
    "ensure_pool_factual_workspace_default_sync",
    "resolve_pool_factual_scope",
]
