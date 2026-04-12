from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.databases.models import Cluster, Database
from apps.tenancy.models import Tenant

from .master_data_registry import (
    POOL_MASTER_DATA_CAPABILITY_SYNC_INBOUND,
    POOL_MASTER_DATA_CAPABILITY_SYNC_OUTBOUND,
    POOL_MASTER_DATA_CAPABILITY_SYNC_RECONCILE,
    supports_pool_master_data_capability,
)
from .master_data_sync_cluster_all_eligibility import (
    summarize_pool_master_data_sync_cluster_all_eligibility,
)
from .master_data_sync_outbound_snapshot import enqueue_manual_outbound_snapshot_for_scope
from .master_data_sync_conflicts import MasterDataSyncConflictError
from .master_data_sync_execution import (
    PoolMasterDataSyncTriggerResult,
    trigger_pool_master_data_inbound_sync_job,
    trigger_pool_master_data_outbound_sync_job,
    trigger_pool_master_data_reconcile_sync_job,
)
from .master_data_sync_redaction import sanitize_master_data_sync_text, sanitize_master_data_sync_value
from .models import (
    PoolMasterDataSyncJobStatus,
    PoolMasterDataSyncLaunchItem,
    PoolMasterDataSyncLaunchItemStatus,
    PoolMasterDataSyncLaunchMode,
    PoolMasterDataSyncLaunchRequest,
    PoolMasterDataSyncLaunchStatus,
    PoolMasterDataSyncLaunchTargetMode,
)
from .master_data_registry import normalize_pool_master_data_entity_type


User = get_user_model()

SYNC_LAUNCH_REQUEST_NOT_FOUND = "SYNC_LAUNCH_REQUEST_NOT_FOUND"
SYNC_LAUNCH_TARGET_MODE_INVALID = "SYNC_LAUNCH_TARGET_MODE_INVALID"
SYNC_LAUNCH_MODE_INVALID = "SYNC_LAUNCH_MODE_INVALID"
SYNC_LAUNCH_CLUSTER_REQUIRED = "SYNC_LAUNCH_CLUSTER_REQUIRED"
SYNC_LAUNCH_CLUSTER_NOT_FOUND = "SYNC_LAUNCH_CLUSTER_NOT_FOUND"
SYNC_LAUNCH_DATABASE_IDS_REQUIRED = "SYNC_LAUNCH_DATABASE_IDS_REQUIRED"
SYNC_LAUNCH_DATABASE_NOT_FOUND = "SYNC_LAUNCH_DATABASE_NOT_FOUND"
SYNC_LAUNCH_EMPTY_TARGETS = "SYNC_LAUNCH_EMPTY_TARGETS"
SYNC_LAUNCH_CLUSTER_ALL_UNCONFIGURED = "SYNC_LAUNCH_CLUSTER_ALL_UNCONFIGURED"
SYNC_LAUNCH_SCOPE_EMPTY = "SYNC_LAUNCH_SCOPE_EMPTY"
SYNC_LAUNCH_SCOPE_UNSUPPORTED = "SYNC_LAUNCH_SCOPE_UNSUPPORTED"
SYNC_LAUNCH_TRIGGER_FAILED = "SYNC_LAUNCH_TRIGGER_FAILED"

_MODE_TO_CAPABILITY = {
    PoolMasterDataSyncLaunchMode.INBOUND: POOL_MASTER_DATA_CAPABILITY_SYNC_INBOUND,
    PoolMasterDataSyncLaunchMode.OUTBOUND: POOL_MASTER_DATA_CAPABILITY_SYNC_OUTBOUND,
    PoolMasterDataSyncLaunchMode.RECONCILE: POOL_MASTER_DATA_CAPABILITY_SYNC_RECONCILE,
}
_REQUEST_TERMINAL_STATUSES = {
    PoolMasterDataSyncLaunchStatus.COMPLETED,
    PoolMasterDataSyncLaunchStatus.FAILED,
}
_CHILD_TERMINAL_JOB_STATUSES = {
    PoolMasterDataSyncJobStatus.SUCCEEDED,
    PoolMasterDataSyncJobStatus.FAILED,
    PoolMasterDataSyncJobStatus.CANCELED,
}
_REQUEST_CACHE_ATTR = "_sync_launch_items_cache"
SYNC_LAUNCH_FANOUT_CHUNK_SIZE = 50


class SyncLaunchValidationError(ValueError):
    def __init__(
        self,
        *,
        code: str,
        detail: str,
        errors: object | None = None,
        status_code: int | None = None,
    ) -> None:
        self.code = str(code or "VALIDATION_ERROR")
        self.detail = str(detail or "").strip() or "Sync launch request failed."
        self.errors = errors
        self.status_code = status_code
        super().__init__(f"{self.code}: {self.detail}")


def create_pool_master_data_sync_launch_request(
    *,
    tenant: Tenant,
    mode: str,
    target_mode: str,
    cluster_id: str | None,
    database_ids: Iterable[str] | None,
    entity_scope: Iterable[str],
    actor_id: str,
    actor_username: str = "",
) -> PoolMasterDataSyncLaunchRequest:
    resolved_mode = _normalize_mode(mode)
    resolved_target_mode = _normalize_target_mode(target_mode)
    normalized_scope = _normalize_entity_scope(entity_scope=entity_scope, mode=resolved_mode)
    resolved_cluster_id, databases, target_resolution = _resolve_launch_targets(
        tenant_id=str(tenant.id),
        target_mode=resolved_target_mode,
        cluster_id=cluster_id,
        database_ids=database_ids,
    )
    with transaction.atomic():
        launch_request = PoolMasterDataSyncLaunchRequest.objects.create(
            tenant=tenant,
            mode=resolved_mode,
            target_mode=resolved_target_mode,
            cluster_id=resolved_cluster_id,
            database_ids=[str(database.id) for database in databases],
            entity_scope=normalized_scope,
            status=PoolMasterDataSyncLaunchStatus.PENDING,
            requested_by_id=_resolve_requested_by_id(actor_id),
            metadata={
                "audit_trail": [],
                "target_resolution": target_resolution,
            },
        )
        _append_launch_audit(
            launch_request=launch_request,
            action="launch_created",
            actor_id=actor_id,
            actor_username=actor_username,
            metadata={
                "mode": resolved_mode,
                "target_mode": resolved_target_mode,
                "cluster_id": str(resolved_cluster_id) if resolved_cluster_id else None,
                "database_ids": [str(database.id) for database in databases],
                "entity_scope": normalized_scope,
                "target_resolution": target_resolution,
            },
        )
        items: list[PoolMasterDataSyncLaunchItem] = []
        for database in databases:
            for entity_type in normalized_scope:
                items.append(
                    PoolMasterDataSyncLaunchItem.objects.create(
                        launch_request=launch_request,
                        database=database,
                        entity_type=entity_type,
                        status=PoolMasterDataSyncLaunchItemStatus.PENDING,
                    )
                )
        _recompute_request_read_model(launch_request=launch_request, items=items)

    from .master_data_sync_launch_workflow_runtime import start_pool_master_data_sync_launch_request_workflow

    start_pool_master_data_sync_launch_request_workflow(
        launch_request=launch_request,
        correlation_id=f"corr-sync-launch-{launch_request.id}",
        origin_system="manual_sync_launch",
        origin_event_id=f"manual-sync-launch:{launch_request.id}",
        actor_username=actor_username,
    )
    return _refresh_launch_request(
        tenant_id=str(tenant.id),
        launch_request_id=str(launch_request.id),
        include_items=False,
        refresh=True,
    )


def list_pool_master_data_sync_launch_requests(
    *,
    tenant_id: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[PoolMasterDataSyncLaunchRequest], int]:
    queryset = PoolMasterDataSyncLaunchRequest.objects.filter(tenant_id=str(tenant_id or "").strip())
    total = queryset.count()
    rows = list(
        queryset.select_related("requested_by")
        .order_by("-created_at")[max(0, offset) : max(0, offset) + max(1, limit)]
    )
    refreshed: list[PoolMasterDataSyncLaunchRequest] = []
    for row in rows:
        refreshed.append(
            _refresh_launch_request(
                tenant_id=str(tenant_id),
                launch_request_id=str(row.id),
                include_items=False,
                refresh=True,
            )
        )
    return refreshed, total


def get_pool_master_data_sync_launch_request(
    *,
    tenant_id: str,
    launch_request_id: str,
) -> PoolMasterDataSyncLaunchRequest:
    return _refresh_launch_request(
        tenant_id=tenant_id,
        launch_request_id=launch_request_id,
        include_items=True,
        refresh=True,
    )


def serialize_pool_master_data_sync_launch_request(
    *,
    launch_request: PoolMasterDataSyncLaunchRequest,
    include_items: bool = False,
) -> dict[str, Any]:
    metadata = launch_request.metadata if isinstance(launch_request.metadata, dict) else {}
    payload: dict[str, Any] = {
        "id": str(launch_request.id),
        "tenant_id": str(launch_request.tenant_id),
        "mode": str(launch_request.mode),
        "target_mode": str(launch_request.target_mode),
        "cluster_id": str(launch_request.cluster_id) if launch_request.cluster_id else None,
        "database_ids": list(launch_request.database_ids or []),
        "entity_scope": list(launch_request.entity_scope or []),
        "status": str(launch_request.status),
        "workflow_execution_id": (
            str(launch_request.workflow_execution_id) if launch_request.workflow_execution_id else None
        ),
        "operation_id": str(launch_request.operation_id) if launch_request.operation_id else None,
        "requested_by_id": launch_request.requested_by_id,
        "requested_by_username": _read_requested_by_username(launch_request),
        "last_error_code": str(launch_request.last_error_code or ""),
        "last_error": sanitize_master_data_sync_text(str(launch_request.last_error or "")),
        "aggregate_counters": _as_dict(metadata.get("aggregate_counters")),
        "progress": _as_dict(metadata.get("progress")),
        "child_job_status_counts": _as_dict(metadata.get("child_job_status_counts")),
        "audit_trail": _as_list(metadata.get("audit_trail")),
        "target_resolution": sanitize_master_data_sync_value(_as_dict(metadata.get("target_resolution"))),
        "created_at": launch_request.created_at,
        "updated_at": launch_request.updated_at,
    }
    if include_items:
        payload["items"] = [
            _serialize_launch_item(item)
            for item in _get_request_items(launch_request)
        ]
    return payload


def run_pool_master_data_sync_launch_request_fanout(
    *,
    launch_request_id: str,
) -> PoolMasterDataSyncLaunchRequest:
    with transaction.atomic():
        launch_request = (
            PoolMasterDataSyncLaunchRequest.objects.select_for_update()
            .filter(id=str(launch_request_id or "").strip())
            .first()
        )
        if launch_request is None:
            raise LookupError(
                f"{SYNC_LAUNCH_REQUEST_NOT_FOUND}: launch request '{launch_request_id}' was not found"
            )
        if launch_request.status == PoolMasterDataSyncLaunchStatus.PENDING:
            launch_request.status = PoolMasterDataSyncLaunchStatus.RUNNING
            launch_request.last_error_code = ""
            launch_request.last_error = ""
            launch_request.save(
                update_fields=["status", "last_error_code", "last_error", "updated_at"]
            )

    launch_request = _refresh_launch_request(
        tenant_id=str(launch_request.tenant_id),
        launch_request_id=str(launch_request.id),
        include_items=False,
        refresh=False,
    )
    pending_item_ids = list(
        PoolMasterDataSyncLaunchItem.objects.filter(
            launch_request_id=launch_request.id,
            status=PoolMasterDataSyncLaunchItemStatus.PENDING,
        )
        .order_by("database__name", "entity_type", "id")
        .values_list("id", flat=True)
    )
    chunk_size = max(1, int(SYNC_LAUNCH_FANOUT_CHUNK_SIZE))
    processed_items = 0
    total_pending_items = len(pending_item_ids)

    for chunk_index, start_index in enumerate(range(0, total_pending_items, chunk_size), start=1):
        chunk_ids = pending_item_ids[start_index : start_index + chunk_size]
        chunk_items = list(
            PoolMasterDataSyncLaunchItem.objects.filter(id__in=chunk_ids)
            .select_related("database", "child_job")
            .order_by("database__name", "entity_type", "id")
        )
        for item in chunk_items:
            _process_launch_item(launch_request=launch_request, item=item)
        processed_items += len(chunk_items)

        refreshed_chunk = _refresh_launch_request(
            tenant_id=str(launch_request.tenant_id),
            launch_request_id=str(launch_request.id),
            include_items=False,
            refresh=True,
        )
        _append_launch_audit(
            launch_request=refreshed_chunk,
            action="fanout_chunk_completed",
            actor_id=str(refreshed_chunk.requested_by_id or ""),
            actor_username=_read_requested_by_username(refreshed_chunk),
            metadata={
                "chunk_index": chunk_index,
                "chunk_size": len(chunk_items),
                "configured_chunk_size": chunk_size,
                "processed_items": processed_items,
                "pending_items_remaining": max(total_pending_items - processed_items, 0),
                "aggregate_counters": dict(
                    (refreshed_chunk.metadata or {}).get("aggregate_counters") or {}
                ),
            },
        )
        refreshed_chunk.save(update_fields=["metadata", "updated_at"])

    refreshed = _refresh_launch_request(
        tenant_id=str(launch_request.tenant_id),
        launch_request_id=str(launch_request.id),
        include_items=True,
        refresh=True,
    )
    if refreshed.status not in _REQUEST_TERMINAL_STATUSES:
        refreshed.status = PoolMasterDataSyncLaunchStatus.COMPLETED
        refreshed.last_error_code = ""
        refreshed.last_error = ""
        _append_launch_audit(
            launch_request=refreshed,
            action="fanout_completed",
            actor_id=str(refreshed.requested_by_id or ""),
            actor_username=_read_requested_by_username(refreshed),
            metadata={
                "aggregate_counters": dict(
                    (refreshed.metadata or {}).get("aggregate_counters") or {}
                ),
            },
        )
        refreshed.save(update_fields=["status", "last_error_code", "last_error", "metadata", "updated_at"])
    return _refresh_launch_request(
        tenant_id=str(refreshed.tenant_id),
        launch_request_id=str(refreshed.id),
        include_items=True,
        refresh=True,
    )


def mark_pool_master_data_sync_launch_request_failed(
    *,
    launch_request_id: str,
    error_code: str,
    error_detail: str,
) -> PoolMasterDataSyncLaunchRequest | None:
    launch_request = (
        PoolMasterDataSyncLaunchRequest.objects.select_related("requested_by")
        .filter(id=str(launch_request_id or "").strip())
        .first()
    )
    if launch_request is None:
        return None
    launch_request.status = PoolMasterDataSyncLaunchStatus.FAILED
    launch_request.last_error_code = str(error_code or "").strip() or SYNC_LAUNCH_TRIGGER_FAILED
    launch_request.last_error = sanitize_master_data_sync_text(error_detail) or launch_request.last_error_code
    _append_launch_audit(
        launch_request=launch_request,
        action="fanout_failed",
        actor_id=str(launch_request.requested_by_id or ""),
        actor_username=_read_requested_by_username(launch_request),
        metadata={
            "error_code": launch_request.last_error_code,
            "detail": launch_request.last_error,
        },
    )
    launch_request.save(update_fields=["status", "last_error_code", "last_error", "metadata", "updated_at"])
    return _refresh_launch_request(
        tenant_id=str(launch_request.tenant_id),
        launch_request_id=str(launch_request.id),
        include_items=True,
        refresh=True,
    )


def _process_launch_item(
    *,
    launch_request: PoolMasterDataSyncLaunchRequest,
    item: PoolMasterDataSyncLaunchItem,
) -> None:
    correlation_id = f"corr-sync-launch:{launch_request.id}:{item.id}"
    origin_event_id = f"manual-sync-launch:{launch_request.id}:{item.id}"

    try:
        result, trigger_metadata = _trigger_item(
            launch_request=launch_request,
            item=item,
            correlation_id=correlation_id,
            origin_event_id=origin_event_id,
        )
    except MasterDataSyncConflictError as exc:
        _save_launch_item(
            item=item,
            status=PoolMasterDataSyncLaunchItemStatus.FAILED,
            reason_code=str(exc.code or SYNC_LAUNCH_TRIGGER_FAILED),
            reason_detail=str(exc.detail or ""),
            metadata={"diagnostics": exc.to_diagnostic()},
        )
        return
    except Exception as exc:  # noqa: BLE001
        error_code = str(getattr(exc, "code", SYNC_LAUNCH_TRIGGER_FAILED) or SYNC_LAUNCH_TRIGGER_FAILED)
        error_detail = str(getattr(exc, "detail", exc) or error_code)
        _save_launch_item(
            item=item,
            status=PoolMasterDataSyncLaunchItemStatus.FAILED,
            reason_code=error_code,
            reason_detail=error_detail,
            metadata={
                "detail": sanitize_master_data_sync_text(error_detail),
            },
        )
        return

    if result.skipped:
        _save_launch_item(
            item=item,
            status=PoolMasterDataSyncLaunchItemStatus.SKIPPED,
            reason_code=str(result.skip_reason or ""),
            reason_detail=str(result.skip_reason or ""),
            child_job=result.sync_job,
            metadata=_merge_launch_item_metadata(
                _build_result_metadata(result=result, outcome="skipped"),
                trigger_metadata,
            ),
        )
        return

    if result.started_workflow:
        outcome = (
            PoolMasterDataSyncLaunchItemStatus.SCHEDULED
            if result.created_job
            else PoolMasterDataSyncLaunchItemStatus.COALESCED
        )
        _save_launch_item(
            item=item,
            status=outcome,
            reason_code="",
            reason_detail="",
            child_job=result.sync_job,
            metadata=_merge_launch_item_metadata(
                _build_result_metadata(
                    result=result,
                    outcome="scheduled" if result.created_job else "coalesced",
                ),
                trigger_metadata,
            ),
        )
        return

    reason_code, reason_detail = _extract_result_failure(result=result)
    _save_launch_item(
        item=item,
        status=PoolMasterDataSyncLaunchItemStatus.FAILED,
        reason_code=reason_code,
        reason_detail=reason_detail,
        child_job=result.sync_job,
        metadata=_merge_launch_item_metadata(
            _build_result_metadata(result=result, outcome="failed"),
            trigger_metadata,
        ),
    )


def _trigger_item(
    *,
    launch_request: PoolMasterDataSyncLaunchRequest,
    item: PoolMasterDataSyncLaunchItem,
    correlation_id: str,
    origin_event_id: str,
) -> tuple[PoolMasterDataSyncTriggerResult, dict[str, Any]]:
    common_kwargs = {
        "tenant_id": str(launch_request.tenant_id),
        "database_id": str(item.database_id),
        "entity_type": str(item.entity_type),
        "origin_system": "manual_sync_launch",
        "origin_event_id": origin_event_id,
        "correlation_id": correlation_id,
    }
    if launch_request.mode == PoolMasterDataSyncLaunchMode.INBOUND:
        return trigger_pool_master_data_inbound_sync_job(**common_kwargs), {}
    if launch_request.mode == PoolMasterDataSyncLaunchMode.OUTBOUND:
        snapshot_result = enqueue_manual_outbound_snapshot_for_scope(
            tenant_id=str(launch_request.tenant_id),
            database_id=str(item.database_id),
            entity_type=str(item.entity_type),
            origin_system="manual_sync_launch",
            origin_event_id=origin_event_id,
        )
        return (
            trigger_pool_master_data_outbound_sync_job(
                **common_kwargs,
                canonical_id="",
            ),
            {
                "manual_outbound_snapshot": {
                    "candidates": int(snapshot_result.candidates),
                    "prepared": int(snapshot_result.prepared),
                    "blocked": int(snapshot_result.blocked),
                }
            },
        )
    if launch_request.mode == PoolMasterDataSyncLaunchMode.RECONCILE:
        return (
            trigger_pool_master_data_reconcile_sync_job(
                **common_kwargs,
                reconcile_window_id=f"manual-launch:{launch_request.id}",
                reconcile_window_deadline_at="",
            ),
            {},
        )
    raise ValueError(f"{SYNC_LAUNCH_MODE_INVALID}: unsupported launch mode '{launch_request.mode}'")


def _save_launch_item(
    *,
    item: PoolMasterDataSyncLaunchItem,
    status: str,
    reason_code: str,
    reason_detail: str,
    child_job=None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    refreshed = PoolMasterDataSyncLaunchItem.objects.get(id=item.id)
    refreshed.status = status
    refreshed.child_job = child_job
    refreshed.reason_code = str(reason_code or "").strip()
    refreshed.reason_detail = sanitize_master_data_sync_text(reason_detail)
    refreshed.metadata = sanitize_master_data_sync_value(dict(metadata or {}))
    refreshed.save(
        update_fields=[
            "status",
            "child_job",
            "reason_code",
            "reason_detail",
            "metadata",
            "updated_at",
        ]
    )


def _build_result_metadata(
    *,
    result: PoolMasterDataSyncTriggerResult,
    outcome: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "launch_outcome": outcome,
        "created_job": bool(result.created_job),
        "started_workflow": bool(result.started_workflow),
        "skipped": bool(result.skipped),
        "skip_reason": str(result.skip_reason or ""),
        "policy": str(result.policy or ""),
        "policy_source": str(result.policy_source or ""),
    }
    if result.sync_job is not None:
        payload["sync_job_id"] = str(result.sync_job.id)
        payload["child_status"] = str(result.sync_job.status or "")
        payload["child_workflow_execution_id"] = (
            str(result.sync_job.workflow_execution_id) if result.sync_job.workflow_execution_id else ""
        )
        payload["child_operation_id"] = (
            str(result.sync_job.operation_id) if result.sync_job.operation_id else ""
        )
    if result.start_result is not None:
        payload["enqueue_status"] = str(result.start_result.enqueue_status or "")
        payload["enqueue_error"] = sanitize_master_data_sync_text(
            str(result.start_result.enqueue_error or "")
        )
    return sanitize_master_data_sync_value(payload)


def _merge_launch_item_metadata(*payloads: Mapping[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for payload in payloads:
        if isinstance(payload, Mapping):
            merged.update(dict(payload))
    return sanitize_master_data_sync_value(merged)


def _extract_result_failure(*, result: PoolMasterDataSyncTriggerResult) -> tuple[str, str]:
    if result.start_result is not None and str(result.start_result.enqueue_error or "").strip():
        error_code = (
            str(getattr(result.start_result.sync_job, "last_error_code", "") or "").strip()
            or str(result.start_result.enqueue_status or "").strip()
            or SYNC_LAUNCH_TRIGGER_FAILED
        )
        return error_code, str(result.start_result.enqueue_error or "")
    if result.sync_job is not None:
        error_code = str(result.sync_job.last_error_code or "").strip() or SYNC_LAUNCH_TRIGGER_FAILED
        error_detail = str(result.sync_job.last_error or "").strip() or error_code
        return error_code, error_detail
    if str(result.skip_reason or "").strip():
        return str(result.skip_reason or "").strip(), str(result.skip_reason or "").strip()
    return SYNC_LAUNCH_TRIGGER_FAILED, SYNC_LAUNCH_TRIGGER_FAILED


def _refresh_launch_request(
    *,
    tenant_id: str,
    launch_request_id: str,
    include_items: bool,
    refresh: bool,
) -> PoolMasterDataSyncLaunchRequest:
    launch_request = (
        PoolMasterDataSyncLaunchRequest.objects.filter(
            id=str(launch_request_id or "").strip(),
            tenant_id=str(tenant_id or "").strip(),
        )
        .select_related("requested_by")
        .first()
    )
    if launch_request is None:
        raise LookupError(
            f"{SYNC_LAUNCH_REQUEST_NOT_FOUND}: launch request '{launch_request_id}' was not found"
        )
    items = list(
        launch_request.items.select_related("database", "child_job")
        .order_by("database__name", "entity_type", "id")
        .all()
    )
    if refresh:
        _recompute_request_read_model(launch_request=launch_request, items=items)
    if include_items:
        setattr(launch_request, _REQUEST_CACHE_ATTR, items)
    return launch_request


def _recompute_request_read_model(
    *,
    launch_request: PoolMasterDataSyncLaunchRequest,
    items: list[PoolMasterDataSyncLaunchItem],
) -> None:
    status_counts = Counter(str(item.status or "") for item in items)
    child_status_counts = Counter(
        str(item.child_job.status or "")
        for item in items
        if item.child_job is not None and str(item.child_job.status or "").strip()
    )
    total_items = len(items)
    completed_items = int(child_status_counts.get(PoolMasterDataSyncJobStatus.SUCCEEDED, 0))
    fanout_processed_items = total_items - int(status_counts.get(PoolMasterDataSyncLaunchItemStatus.PENDING, 0))
    terminal_items = 0
    for item in items:
        child_status = str(getattr(item.child_job, "status", "") or "").strip()
        if item.status in {
            PoolMasterDataSyncLaunchItemStatus.SKIPPED,
            PoolMasterDataSyncLaunchItemStatus.FAILED,
        }:
            terminal_items += 1
            continue
        if child_status in _CHILD_TERMINAL_JOB_STATUSES:
            terminal_items += 1

    progress = {
        "total_items": total_items,
        "pending_items": int(status_counts.get(PoolMasterDataSyncLaunchItemStatus.PENDING, 0)),
        "fanout_processed_items": fanout_processed_items,
        "completed_items": completed_items,
        "terminal_items": terminal_items,
        "completion_ratio": round((terminal_items / total_items) if total_items else 0.0, 4),
    }
    aggregate_counters = {
        "total_items": total_items,
        "scheduled": int(status_counts.get(PoolMasterDataSyncLaunchItemStatus.SCHEDULED, 0)),
        "coalesced": int(status_counts.get(PoolMasterDataSyncLaunchItemStatus.COALESCED, 0)),
        "skipped": int(status_counts.get(PoolMasterDataSyncLaunchItemStatus.SKIPPED, 0)),
        "failed": int(status_counts.get(PoolMasterDataSyncLaunchItemStatus.FAILED, 0)),
        "completed": completed_items,
    }
    metadata = dict(launch_request.metadata or {})
    metadata["aggregate_counters"] = aggregate_counters
    metadata["progress"] = progress
    metadata["child_job_status_counts"] = {
        key: int(value)
        for key, value in sorted(child_status_counts.items())
    }
    launch_request.metadata = sanitize_master_data_sync_value(metadata)
    launch_request.save(update_fields=["metadata", "updated_at"])


def _append_launch_audit(
    *,
    launch_request: PoolMasterDataSyncLaunchRequest,
    action: str,
    actor_id: str,
    actor_username: str,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    payload = dict(launch_request.metadata or {})
    audit_trail = list(payload.get("audit_trail") or [])
    audit_trail.append(
        sanitize_master_data_sync_value(
            {
                "action": str(action or "").strip(),
                "at": timezone.now().isoformat(),
                "actor_id": str(actor_id or "").strip(),
                "actor_username": str(actor_username or "").strip(),
                "metadata": dict(metadata or {}),
            }
        )
    )
    payload["audit_trail"] = audit_trail[-50:]
    launch_request.metadata = payload


def _normalize_mode(mode: str) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized not in set(PoolMasterDataSyncLaunchMode.values):
        raise ValueError(f"{SYNC_LAUNCH_MODE_INVALID}: unsupported launch mode '{mode}'")
    return normalized


def _normalize_target_mode(target_mode: str) -> str:
    normalized = str(target_mode or "").strip().lower()
    if normalized not in set(PoolMasterDataSyncLaunchTargetMode.values):
        raise ValueError(
            f"{SYNC_LAUNCH_TARGET_MODE_INVALID}: unsupported launch target mode '{target_mode}'"
        )
    return normalized


def _normalize_entity_scope(*, entity_scope: Iterable[str], mode: str) -> list[str]:
    required_capability = _MODE_TO_CAPABILITY[mode]
    normalized_scope = [
        normalize_pool_master_data_entity_type(str(value or ""))
        for value in list(entity_scope or [])
    ]
    normalized_scope = list(dict.fromkeys(normalized_scope))
    if not normalized_scope:
        raise ValueError(f"{SYNC_LAUNCH_SCOPE_EMPTY}: entity_scope must not be empty")
    for entity_type in normalized_scope:
        if not supports_pool_master_data_capability(
            entity_type=entity_type,
            capability=required_capability,
        ):
            raise ValueError(
                f"{SYNC_LAUNCH_SCOPE_UNSUPPORTED}: entity_type '{entity_type}' "
                f"does not support launch mode '{mode}'"
            )
    return normalized_scope


def _resolve_launch_targets(
    *,
    tenant_id: str,
    target_mode: str,
    cluster_id: str | None,
    database_ids: Iterable[str] | None,
) -> tuple[str | None, list[Database], dict[str, Any]]:
    normalized_tenant_id = str(tenant_id or "").strip()
    if target_mode == PoolMasterDataSyncLaunchTargetMode.CLUSTER_ALL:
        normalized_cluster_id = str(cluster_id or "").strip()
        if not normalized_cluster_id:
            raise ValueError(f"{SYNC_LAUNCH_CLUSTER_REQUIRED}: cluster_id is required for cluster_all")
        cluster = Cluster.objects.filter(id=normalized_cluster_id, tenant_id=normalized_tenant_id).first()
        if cluster is None:
            raise ValueError(
                f"{SYNC_LAUNCH_CLUSTER_NOT_FOUND}: cluster '{normalized_cluster_id}' was not found"
            )
        databases = list(
            Database.objects.filter(tenant_id=normalized_tenant_id, cluster_id=cluster.id)
            .order_by("name", "id")
        )
        if not databases:
            raise ValueError(
                f"{SYNC_LAUNCH_EMPTY_TARGETS}: cluster '{normalized_cluster_id}' has no target databases"
            )
        target_resolution = summarize_pool_master_data_sync_cluster_all_eligibility(databases=databases)
        if target_resolution["unconfigured_count"] > 0:
            raise SyncLaunchValidationError(
                code=SYNC_LAUNCH_CLUSTER_ALL_UNCONFIGURED,
                detail=(
                    f"cluster '{normalized_cluster_id}' contains databases without explicit "
                    "cluster_all eligibility decision"
                ),
                errors={
                    "cluster_id": [
                        "Resolve cluster_all eligibility for all databases in /databases before launch."
                    ],
                    "unconfigured_databases": target_resolution["unconfigured_databases"],
                },
                status_code=409,
            )
        eligible_database_ids = set(target_resolution.get("eligible_database_ids") or [])
        eligible_databases = [
            database for database in databases if str(database.id) in eligible_database_ids
        ]
        if not eligible_databases:
            raise ValueError(
                f"{SYNC_LAUNCH_EMPTY_TARGETS}: cluster '{normalized_cluster_id}' has no eligible target databases"
            )
        return str(cluster.id), eligible_databases, target_resolution

    if target_mode == PoolMasterDataSyncLaunchTargetMode.DATABASE_SET:
        selected_database_ids = [str(value or "").strip() for value in list(database_ids or []) if str(value or "").strip()]
        deduped_database_ids = list(dict.fromkeys(selected_database_ids))
        if not deduped_database_ids:
            raise ValueError(
                f"{SYNC_LAUNCH_DATABASE_IDS_REQUIRED}: database_ids must not be empty for database_set"
            )
        databases = list(
            Database.objects.filter(
                tenant_id=normalized_tenant_id,
                id__in=deduped_database_ids,
            ).order_by("name", "id")
        )
        database_map = {str(database.id): database for database in databases}
        missing_ids = [database_id for database_id in deduped_database_ids if database_id not in database_map]
        if missing_ids:
            raise ValueError(
                f"{SYNC_LAUNCH_DATABASE_NOT_FOUND}: databases not found in tenant scope: {', '.join(missing_ids)}"
            )
        resolved_databases = [database_map[database_id] for database_id in deduped_database_ids]
        return None, resolved_databases, {
            "eligible_count": len(resolved_databases),
            "excluded_count": 0,
            "unconfigured_count": 0,
            "eligible_database_ids": [str(database.id) for database in resolved_databases],
            "excluded_databases": [],
            "unconfigured_databases": [],
        }

    raise ValueError(
        f"{SYNC_LAUNCH_TARGET_MODE_INVALID}: unsupported launch target mode '{target_mode}'"
    )


def _serialize_launch_item(item: PoolMasterDataSyncLaunchItem) -> dict[str, Any]:
    metadata = item.metadata if isinstance(item.metadata, dict) else {}
    return {
        "id": str(item.id),
        "database_id": str(item.database_id),
        "database_name": str(item.database.name),
        "cluster_id": str(item.database.cluster_id) if item.database.cluster_id else None,
        "entity_type": str(item.entity_type),
        "status": str(item.status),
        "reason_code": str(item.reason_code or ""),
        "reason_detail": sanitize_master_data_sync_text(str(item.reason_detail or "")),
        "child_job_id": str(item.child_job_id) if item.child_job_id else None,
        "child_job_status": str(item.child_job.status or "") if item.child_job_id else "",
        "child_workflow_execution_id": (
            str(item.child_job.workflow_execution_id) if item.child_job and item.child_job.workflow_execution_id else None
        ),
        "child_operation_id": (
            str(item.child_job.operation_id) if item.child_job and item.child_job.operation_id else None
        ),
        "metadata": sanitize_master_data_sync_value(metadata),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _get_request_items(launch_request: PoolMasterDataSyncLaunchRequest) -> list[PoolMasterDataSyncLaunchItem]:
    cached = getattr(launch_request, _REQUEST_CACHE_ATTR, None)
    if isinstance(cached, list):
        return cached
    return list(
        launch_request.items.select_related("database", "child_job")
        .order_by("database__name", "entity_type", "id")
        .all()
    )


def _read_requested_by_username(launch_request: PoolMasterDataSyncLaunchRequest) -> str:
    requested_by = getattr(launch_request, "requested_by", None)
    return str(getattr(requested_by, "username", "") or "")


def _resolve_requested_by_id(actor_id: str) -> str | None:
    normalized = str(actor_id or "").strip()
    if not normalized:
        return None
    if not User.objects.filter(id=normalized).exists():
        return None
    return normalized


def _as_dict(value: object | None) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object | None) -> list[Any]:
    return value if isinstance(value, list) else []


__all__ = [
    "SYNC_LAUNCH_CLUSTER_NOT_FOUND",
    "SYNC_LAUNCH_CLUSTER_ALL_UNCONFIGURED",
    "SYNC_LAUNCH_DATABASE_NOT_FOUND",
    "SYNC_LAUNCH_EMPTY_TARGETS",
    "SYNC_LAUNCH_FANOUT_CHUNK_SIZE",
    "SYNC_LAUNCH_REQUEST_NOT_FOUND",
    "SyncLaunchValidationError",
    "create_pool_master_data_sync_launch_request",
    "get_pool_master_data_sync_launch_request",
    "list_pool_master_data_sync_launch_requests",
    "mark_pool_master_data_sync_launch_request_failed",
    "run_pool_master_data_sync_launch_request_fanout",
    "serialize_pool_master_data_sync_launch_request",
]
