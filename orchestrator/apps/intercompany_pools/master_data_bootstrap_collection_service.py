from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.databases.models import Cluster, Database
from apps.tenancy.models import Tenant

from .master_data_bootstrap_import_dependency_order import resolve_bootstrap_import_dependency_order
from .master_data_bootstrap_import_service import (
    BOOTSTRAP_IMPORT_MODE_EXECUTE,
    BootstrapImportPreflightBlockedError,
    create_pool_master_data_bootstrap_import_job,
    run_pool_master_data_bootstrap_dry_run_preview,
    run_pool_master_data_bootstrap_preflight_preview,
)
from .master_data_sync_redaction import sanitize_master_data_sync_text, sanitize_master_data_sync_value
from .models import (
    PoolMasterDataBootstrapCollectionItem,
    PoolMasterDataBootstrapCollectionItemStatus,
    PoolMasterDataBootstrapCollectionMode,
    PoolMasterDataBootstrapCollectionRequest,
    PoolMasterDataBootstrapCollectionStatus,
    PoolMasterDataBootstrapCollectionTargetMode,
    PoolMasterDataBootstrapImportJob,
    PoolMasterDataBootstrapImportJobStatus,
)


BOOTSTRAP_COLLECTION_REQUEST_NOT_FOUND = "BOOTSTRAP_COLLECTION_REQUEST_NOT_FOUND"
BOOTSTRAP_COLLECTION_TARGET_MODE_INVALID = "BOOTSTRAP_COLLECTION_TARGET_MODE_INVALID"
BOOTSTRAP_COLLECTION_MODE_INVALID = "BOOTSTRAP_COLLECTION_MODE_INVALID"
BOOTSTRAP_COLLECTION_CLUSTER_REQUIRED = "BOOTSTRAP_COLLECTION_CLUSTER_REQUIRED"
BOOTSTRAP_COLLECTION_CLUSTER_NOT_FOUND = "BOOTSTRAP_COLLECTION_CLUSTER_NOT_FOUND"
BOOTSTRAP_COLLECTION_DATABASE_IDS_REQUIRED = "BOOTSTRAP_COLLECTION_DATABASE_IDS_REQUIRED"
BOOTSTRAP_COLLECTION_DATABASE_NOT_FOUND = "BOOTSTRAP_COLLECTION_DATABASE_NOT_FOUND"
BOOTSTRAP_COLLECTION_EMPTY_TARGETS = "BOOTSTRAP_COLLECTION_EMPTY_TARGETS"
BOOTSTRAP_COLLECTION_SCOPE_EMPTY = "BOOTSTRAP_COLLECTION_SCOPE_EMPTY"
BOOTSTRAP_COLLECTION_DRY_RUN_COLLECTION_REQUIRED = "BOOTSTRAP_COLLECTION_DRY_RUN_COLLECTION_REQUIRED"
BOOTSTRAP_COLLECTION_EXECUTE_COLLECTION_REQUIRED = "BOOTSTRAP_COLLECTION_EXECUTE_COLLECTION_REQUIRED"
BOOTSTRAP_COLLECTION_DRY_RUN_BLOCKED = "BOOTSTRAP_COLLECTION_DRY_RUN_BLOCKED"
BOOTSTRAP_COLLECTION_EXECUTE_BLOCKED = "BOOTSTRAP_COLLECTION_EXECUTE_BLOCKED"
BOOTSTRAP_COLLECTION_STAGE_SCOPE_MISMATCH = "BOOTSTRAP_COLLECTION_STAGE_SCOPE_MISMATCH"
BOOTSTRAP_COLLECTION_STAGE_RUNNER_STALE = "BOOTSTRAP_COLLECTION_STAGE_RUNNER_STALE"

_COLLECTION_WORKFLOW_EXECUTION_ID = "workflow_execution_id"
_COLLECTION_OPERATION_ID = "operation_id"
_COLLECTION_FORCED_STATUS = "forced_status"
_COLLECTION_STAGE_RUNNER = "stage_runner"
_COLLECTION_FANOUT_BATCH_SIZE = "fanout_batch_size"

_DEFAULT_COLLECTION_FANOUT_BATCH_SIZE = 25
_CHILD_TERMINAL_JOB_STATUSES = {
    PoolMasterDataBootstrapImportJobStatus.FINALIZED,
    PoolMasterDataBootstrapImportJobStatus.FAILED,
    PoolMasterDataBootstrapImportJobStatus.CANCELED,
}
_CHILD_ACTIVE_EXECUTE_JOB_STATUSES = {
    PoolMasterDataBootstrapImportJobStatus.EXECUTE_PENDING,
    PoolMasterDataBootstrapImportJobStatus.RUNNING,
}


@dataclass(frozen=True)
class PoolMasterDataBootstrapCollectionStageChunkResult:
    collection: PoolMasterDataBootstrapCollectionRequest
    stage: str
    processed_items: int
    pending_items: int
    should_continue: bool
    stale_runner: bool = False


def run_pool_master_data_bootstrap_collection_preflight_preview(
    *,
    tenant_id: str,
    target_mode: str,
    cluster_id: str | None,
    database_ids: Iterable[str] | None,
    entity_scope: Iterable[str],
    actor_id: str,
) -> dict[str, Any]:
    resolved_target_mode = _normalize_target_mode(target_mode)
    normalized_scope = _normalize_entity_scope(entity_scope)
    resolved_cluster_id, databases = _resolve_collection_targets(
        tenant_id=tenant_id,
        target_mode=resolved_target_mode,
        cluster_id=cluster_id,
        database_ids=database_ids,
    )
    database_entries: list[dict[str, Any]] = []
    aggregate_errors: list[dict[str, Any]] = []
    all_ok = True
    for database in databases:
        preflight = run_pool_master_data_bootstrap_preflight_preview(
            tenant_id=tenant_id,
            database=database,
            entity_scope=normalized_scope,
            actor_id=actor_id,
        )
        item_ok = bool(preflight.get("ok"))
        if not item_ok:
            all_ok = False
            first_error = _first_preflight_error(preflight)
            aggregate_errors.append(
                {
                    "database_id": str(database.id),
                    "database_name": str(database.name),
                    "cluster_id": str(database.cluster_id) if database.cluster_id else None,
                    "code": str(first_error.get("code") or ""),
                    "detail": str(first_error.get("detail") or ""),
                }
            )
        database_entries.append(
            {
                "database_id": str(database.id),
                "database_name": str(database.name),
                "cluster_id": str(database.cluster_id) if database.cluster_id else None,
                "ok": item_ok,
                "preflight_result": preflight,
            }
        )
    return sanitize_master_data_sync_value(
        {
            "ok": all_ok,
            "target_mode": resolved_target_mode,
            "cluster_id": str(resolved_cluster_id) if resolved_cluster_id else None,
            "database_ids": [str(database.id) for database in databases],
            "database_count": len(databases),
            "entity_scope": normalized_scope,
            "databases": database_entries,
            "errors": aggregate_errors,
            "generated_at": timezone.now().isoformat(),
        }
    )


def create_pool_master_data_bootstrap_collection_preflight_request(
    *,
    tenant: Tenant,
    target_mode: str,
    cluster_id: str | None,
    database_ids: Iterable[str] | None,
    entity_scope: Iterable[str],
    actor_id: str,
    actor_username: str = "",
) -> PoolMasterDataBootstrapCollectionRequest:
    resolved_target_mode = _normalize_target_mode(target_mode)
    normalized_scope = _normalize_entity_scope(entity_scope)
    resolved_cluster_id, databases = _resolve_collection_targets(
        tenant_id=str(tenant.id),
        target_mode=resolved_target_mode,
        cluster_id=cluster_id,
        database_ids=database_ids,
    )

    with transaction.atomic():
        collection = PoolMasterDataBootstrapCollectionRequest.objects.create(
            tenant=tenant,
            target_mode=resolved_target_mode,
            mode=PoolMasterDataBootstrapCollectionMode.PREFLIGHT,
            cluster_id=resolved_cluster_id,
            database_ids=[str(database.id) for database in databases],
            entity_scope=normalized_scope,
            status=PoolMasterDataBootstrapCollectionStatus.PREFLIGHT_COMPLETED,
            requested_by_id=str(actor_id or "").strip() or None,
            metadata={
                "audit_trail": [],
                _COLLECTION_FANOUT_BATCH_SIZE: _DEFAULT_COLLECTION_FANOUT_BATCH_SIZE,
            },
        )
        _append_collection_audit(
            collection=collection,
            action="preflight_requested",
            actor_id=actor_id,
            actor_username=actor_username,
            metadata={
                "target_mode": resolved_target_mode,
                "cluster_id": str(resolved_cluster_id) if resolved_cluster_id else None,
                "database_ids": [str(database.id) for database in databases],
                "entity_scope": normalized_scope,
            },
        )
        items = [
            _create_preflight_collection_item(
                collection=collection,
                database=database,
                entity_scope=normalized_scope,
                actor_id=actor_id,
            )
            for database in databases
        ]
        _recompute_collection_read_model(collection=collection, items=items)

    return _refresh_collection(collection_id=str(collection.id), include_items=False, refresh=False)


def create_pool_master_data_bootstrap_collection_request(
    *,
    tenant: Tenant,
    target_mode: str,
    cluster_id: str | None,
    database_ids: Iterable[str] | None,
    entity_scope: Iterable[str],
    mode: str,
    collection_id: str | None = None,
    actor_id: str,
    actor_username: str = "",
    chunk_size: int = 200,
) -> PoolMasterDataBootstrapCollectionRequest:
    resolved_mode = _normalize_mode(mode)
    if resolved_mode == PoolMasterDataBootstrapCollectionMode.PREFLIGHT:
        return create_pool_master_data_bootstrap_collection_preflight_request(
            tenant=tenant,
            target_mode=target_mode,
            cluster_id=cluster_id,
            database_ids=database_ids,
            entity_scope=entity_scope,
            actor_id=actor_id,
            actor_username=actor_username,
        )
    if resolved_mode == PoolMasterDataBootstrapCollectionMode.DRY_RUN:
        return _promote_collection_to_stage(
            tenant=tenant,
            collection_id=collection_id,
            target_mode=target_mode,
            cluster_id=cluster_id,
            database_ids=database_ids,
            entity_scope=entity_scope,
            stage=PoolMasterDataBootstrapCollectionMode.DRY_RUN,
            actor_id=actor_id,
            actor_username=actor_username,
            chunk_size=chunk_size,
        )
    return _promote_collection_to_stage(
        tenant=tenant,
        collection_id=collection_id,
        target_mode=target_mode,
        cluster_id=cluster_id,
        database_ids=database_ids,
        entity_scope=entity_scope,
        stage=PoolMasterDataBootstrapCollectionMode.EXECUTE,
        actor_id=actor_id,
        actor_username=actor_username,
        chunk_size=chunk_size,
    )


def _promote_collection_to_stage(
    *,
    tenant: Tenant,
    collection_id: str | None,
    target_mode: str,
    cluster_id: str | None,
    database_ids: Iterable[str] | None,
    entity_scope: Iterable[str],
    stage: str,
    actor_id: str,
    actor_username: str,
    chunk_size: int,
) -> PoolMasterDataBootstrapCollectionRequest:
    normalized_stage = _normalize_mode(stage)
    normalized_collection_id = str(collection_id or "").strip()
    if not normalized_collection_id:
        if normalized_stage == PoolMasterDataBootstrapCollectionMode.DRY_RUN:
            raise ValueError(
                f"{BOOTSTRAP_COLLECTION_DRY_RUN_COLLECTION_REQUIRED}: collection_id is required for dry-run"
            )
        raise ValueError(
            f"{BOOTSTRAP_COLLECTION_EXECUTE_COLLECTION_REQUIRED}: collection_id is required for execute"
        )

    normalized_scope = _normalize_entity_scope(entity_scope)
    normalized_target_mode = _normalize_target_mode(target_mode)
    normalized_chunk_size = int(_safe_chunk_size(chunk_size))
    fanout_batch_size = _derive_collection_fanout_batch_size(normalized_chunk_size)

    with transaction.atomic():
        collection = (
            PoolMasterDataBootstrapCollectionRequest.objects.select_for_update()
            .filter(id=normalized_collection_id, tenant_id=str(tenant.id))
            .first()
        )
        if collection is None:
            raise LookupError(
                f"{BOOTSTRAP_COLLECTION_REQUEST_NOT_FOUND}: collection '{normalized_collection_id}' was not found"
            )
        _validate_collection_scope(
            collection=collection,
            target_mode=normalized_target_mode,
            cluster_id=cluster_id,
            database_ids=database_ids,
            entity_scope=normalized_scope,
        )
        items = list(collection.items.select_related("database", "child_job").all())
        _recompute_collection_read_model(collection=collection, items=items)
        collection.refresh_from_db()

        if normalized_stage == PoolMasterDataBootstrapCollectionMode.DRY_RUN:
            if str(collection.mode) != PoolMasterDataBootstrapCollectionMode.PREFLIGHT:
                raise ValueError(
                    f"{BOOTSTRAP_COLLECTION_DRY_RUN_BLOCKED}: preflight snapshot is required before dry-run"
                )
            if str(collection.status) != PoolMasterDataBootstrapCollectionStatus.PREFLIGHT_COMPLETED:
                raise ValueError(
                    f"{BOOTSTRAP_COLLECTION_DRY_RUN_BLOCKED}: preflight must complete successfully before dry-run"
                )
        else:
            if str(collection.mode) != PoolMasterDataBootstrapCollectionMode.DRY_RUN:
                raise ValueError(
                    f"{BOOTSTRAP_COLLECTION_EXECUTE_BLOCKED}: dry-run snapshot is required before execute"
                )
            if str(collection.status) != PoolMasterDataBootstrapCollectionStatus.DRY_RUN_COMPLETED:
                raise ValueError(
                    f"{BOOTSTRAP_COLLECTION_EXECUTE_BLOCKED}: dry-run must complete successfully before execute"
                )

        aggregate_counters = _as_dict((collection.metadata or {}).get("aggregate_counters"))
        if int(aggregate_counters.get("failed") or 0) > 0:
            blocked_code = (
                BOOTSTRAP_COLLECTION_DRY_RUN_BLOCKED
                if normalized_stage == PoolMasterDataBootstrapCollectionMode.DRY_RUN
                else BOOTSTRAP_COLLECTION_EXECUTE_BLOCKED
            )
            blocked_stage = "preflight" if normalized_stage == PoolMasterDataBootstrapCollectionMode.DRY_RUN else "dry-run"
            raise ValueError(
                f"{blocked_code}: {blocked_stage} contains failed databases and blocks stage promotion"
            )

        metadata = dict(collection.metadata if isinstance(collection.metadata, dict) else {})
        metadata.pop(_COLLECTION_FORCED_STATUS, None)
        metadata.pop(_COLLECTION_STAGE_RUNNER, None)
        metadata["chunk_size"] = normalized_chunk_size
        metadata[_COLLECTION_FANOUT_BATCH_SIZE] = fanout_batch_size
        collection.metadata = sanitize_master_data_sync_value(metadata)
        collection.mode = normalized_stage
        collection.status = _running_status_for_stage(normalized_stage)
        collection.last_error_code = ""
        collection.last_error = ""
        collection.save(
            update_fields=["mode", "status", "last_error_code", "last_error", "metadata", "updated_at"]
        )

        for item in items:
            item_metadata = dict(item.metadata if isinstance(item.metadata, dict) else {})
            item.status = PoolMasterDataBootstrapCollectionItemStatus.PENDING
            item.reason_code = ""
            item.reason_detail = ""
            item.child_job = None
            item_metadata.pop("child_job_status", None)
            if normalized_stage == PoolMasterDataBootstrapCollectionMode.DRY_RUN:
                item_metadata.pop("dry_run_summary", None)
            item.metadata = sanitize_master_data_sync_value(item_metadata)
            item.save(
                update_fields=[
                    "status",
                    "reason_code",
                    "reason_detail",
                    "child_job",
                    "metadata",
                    "updated_at",
                ]
            )

        action = (
            "dry_run_requested"
            if normalized_stage == PoolMasterDataBootstrapCollectionMode.DRY_RUN
            else "execute_requested"
        )
        _append_collection_audit(
            collection=collection,
            action=action,
            actor_id=actor_id,
            actor_username=actor_username,
            metadata={
                "collection_id": str(collection.id),
                "database_ids": list(collection.database_ids or []),
                "entity_scope": list(collection.entity_scope or []),
                "fanout_batch_size": fanout_batch_size,
            },
        )
        _recompute_collection_read_model(
            collection=collection,
            items=list(collection.items.select_related("database", "child_job").all()),
        )

    from .master_data_bootstrap_collection_workflow_runtime import (
        start_pool_master_data_bootstrap_collection_stage_workflow,
    )

    start_pool_master_data_bootstrap_collection_stage_workflow(
        collection=collection,
        stage=normalized_stage,
        correlation_id=f"corr-bootstrap-collection-{normalized_stage}-{collection.id}",
        origin_system=f"bootstrap_collection_{normalized_stage}",
        origin_event_id=f"bootstrap-collection:{normalized_stage}:{collection.id}",
        actor_username=actor_username,
    )
    return _refresh_collection(collection_id=str(collection.id), include_items=False, refresh=True)


def list_pool_master_data_bootstrap_collection_requests(
    *,
    tenant_id: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[PoolMasterDataBootstrapCollectionRequest], int]:
    queryset = PoolMasterDataBootstrapCollectionRequest.objects.filter(
        tenant_id=str(tenant_id or "").strip()
    )
    total = queryset.count()
    rows = list(
        queryset.select_related("requested_by")
        .order_by("-created_at")[max(0, offset) : max(0, offset) + max(1, limit)]
    )
    refreshed_rows: list[PoolMasterDataBootstrapCollectionRequest] = []
    for row in rows:
        refreshed_rows.append(
            _refresh_collection(collection_id=str(row.id), include_items=False, refresh=True)
        )
    return refreshed_rows, total


def get_pool_master_data_bootstrap_collection_request(
    *,
    tenant_id: str,
    collection_id: str,
) -> PoolMasterDataBootstrapCollectionRequest:
    collection = (
        PoolMasterDataBootstrapCollectionRequest.objects.filter(
            id=str(collection_id or "").strip(),
            tenant_id=str(tenant_id or "").strip(),
        )
        .select_related("requested_by")
        .first()
    )
    if collection is None:
        raise LookupError(
            f"{BOOTSTRAP_COLLECTION_REQUEST_NOT_FOUND}: collection '{collection_id}' was not found"
        )
    return _refresh_collection(collection_id=str(collection.id), include_items=True, refresh=True)


def serialize_pool_master_data_bootstrap_collection_request(
    *,
    collection: PoolMasterDataBootstrapCollectionRequest,
    include_items: bool = False,
) -> dict[str, Any]:
    metadata = collection.metadata if isinstance(collection.metadata, dict) else {}
    payload: dict[str, Any] = {
        "id": str(collection.id),
        "tenant_id": str(collection.tenant_id),
        "target_mode": str(collection.target_mode),
        "mode": str(collection.mode),
        "cluster_id": str(collection.cluster_id) if collection.cluster_id else None,
        "database_ids": list(collection.database_ids or []),
        "entity_scope": list(collection.entity_scope or []),
        "status": str(collection.status),
        "requested_by_id": collection.requested_by_id,
        "requested_by_username": _read_requested_by_username(collection),
        "last_error_code": str(collection.last_error_code or ""),
        "last_error": sanitize_master_data_sync_text(str(collection.last_error or "")),
        "aggregate_counters": _as_dict(metadata.get("aggregate_counters")),
        "progress": _as_dict(metadata.get("progress")),
        "child_job_status_counts": _as_dict(metadata.get("child_job_status_counts")),
        "aggregate_preflight_result": _as_dict(metadata.get("aggregate_preflight_result")),
        "aggregate_dry_run_summary": _as_dict(metadata.get("aggregate_dry_run_summary")),
        "audit_trail": _as_list(metadata.get("audit_trail")),
        "created_at": collection.created_at,
        "updated_at": collection.updated_at,
    }
    if include_items:
        payload["items"] = [_serialize_collection_item(item) for item in _get_collection_items(collection)]
    return payload


def run_pool_master_data_bootstrap_collection_stage_chunk(
    *,
    collection_id: str,
    stage: str,
    runner_token: str | None = None,
) -> PoolMasterDataBootstrapCollectionStageChunkResult:
    normalized_stage = _normalize_mode(stage)
    with transaction.atomic():
        collection = (
            PoolMasterDataBootstrapCollectionRequest.objects.select_for_update()
            .filter(id=str(collection_id or "").strip())
            .first()
        )
        if collection is None:
            raise LookupError(
                f"{BOOTSTRAP_COLLECTION_REQUEST_NOT_FOUND}: collection '{collection_id}' was not found"
            )
        if str(collection.mode) != normalized_stage:
            raise ValueError(
                f"{BOOTSTRAP_COLLECTION_STAGE_SCOPE_MISMATCH}: collection is not in stage '{normalized_stage}'"
            )
        if runner_token and not _runner_token_matches(collection=collection, stage=normalized_stage, runner_token=runner_token):
            refreshed = _refresh_collection(
                collection_id=str(collection.id),
                include_items=True,
                refresh=normalized_stage == PoolMasterDataBootstrapCollectionMode.EXECUTE,
            )
            items = _get_collection_items(refreshed)
            pending_items = sum(1 for item in items if item.status == PoolMasterDataBootstrapCollectionItemStatus.PENDING)
            return PoolMasterDataBootstrapCollectionStageChunkResult(
                collection=refreshed,
                stage=normalized_stage,
                processed_items=0,
                pending_items=pending_items,
                should_continue=pending_items > 0,
                stale_runner=True,
            )

    collection = _refresh_collection(
        collection_id=str(collection_id),
        include_items=True,
        refresh=normalized_stage == PoolMasterDataBootstrapCollectionMode.EXECUTE,
    )
    items = _get_collection_items(collection)
    pending_items = [
        item for item in items if item.status == PoolMasterDataBootstrapCollectionItemStatus.PENDING
    ]
    fanout_batch_size = int(
        _safe_fanout_batch_size((collection.metadata or {}).get(_COLLECTION_FANOUT_BATCH_SIZE))
    )
    selected_items = pending_items[:fanout_batch_size]
    processed = 0
    for item in selected_items:
        if normalized_stage == PoolMasterDataBootstrapCollectionMode.DRY_RUN:
            _process_dry_run_collection_item(collection=collection, item=item)
        else:
            _process_execute_collection_item(collection=collection, item=item)
        processed += 1

    refreshed = _refresh_collection(
        collection_id=str(collection.id),
        include_items=True,
        refresh=normalized_stage == PoolMasterDataBootstrapCollectionMode.EXECUTE,
    )
    refreshed_items = _get_collection_items(refreshed)
    _recompute_collection_read_model(collection=refreshed, items=refreshed_items)
    refreshed = _refresh_collection(
        collection_id=str(refreshed.id),
        include_items=True,
        refresh=normalized_stage == PoolMasterDataBootstrapCollectionMode.EXECUTE,
    )
    refreshed_items = _get_collection_items(refreshed)
    pending_count = sum(
        1 for item in refreshed_items if item.status == PoolMasterDataBootstrapCollectionItemStatus.PENDING
    )
    if pending_count == 0:
        _append_collection_audit(
            collection=refreshed,
            action=f"{normalized_stage}_fanout_completed",
            actor_id=str(refreshed.requested_by_id or ""),
            actor_username=_read_requested_by_username(refreshed),
            metadata={
                "aggregate_counters": _as_dict((refreshed.metadata or {}).get("aggregate_counters")),
                "processed_items": processed,
            },
        )
        refreshed = _refresh_collection(
            collection_id=str(refreshed.id),
            include_items=True,
            refresh=normalized_stage == PoolMasterDataBootstrapCollectionMode.EXECUTE,
        )
    return PoolMasterDataBootstrapCollectionStageChunkResult(
        collection=refreshed,
        stage=normalized_stage,
        processed_items=processed,
        pending_items=pending_count,
        should_continue=pending_count > 0,
    )


def mark_pool_master_data_bootstrap_collection_failed(
    *,
    collection_id: str,
    error_code: str,
    error_detail: str,
) -> PoolMasterDataBootstrapCollectionRequest | None:
    collection = (
        PoolMasterDataBootstrapCollectionRequest.objects.select_related("requested_by")
        .filter(id=str(collection_id or "").strip())
        .first()
    )
    if collection is None:
        return None
    collection.status = PoolMasterDataBootstrapCollectionStatus.FAILED
    collection.last_error_code = str(error_code or "").strip() or "BOOTSTRAP_COLLECTION_STAGE_FAILED"
    collection.last_error = sanitize_master_data_sync_text(error_detail) or collection.last_error_code
    metadata = dict(collection.metadata if isinstance(collection.metadata, dict) else {})
    metadata[_COLLECTION_FORCED_STATUS] = PoolMasterDataBootstrapCollectionStatus.FAILED
    collection.metadata = sanitize_master_data_sync_value(metadata)
    _append_collection_audit(
        collection=collection,
        action=f"{collection.mode}_fanout_failed",
        actor_id=str(collection.requested_by_id or ""),
        actor_username=_read_requested_by_username(collection),
        metadata={
            "error_code": collection.last_error_code,
            "detail": collection.last_error,
        },
    )
    collection.save(update_fields=["status", "last_error_code", "last_error", "metadata", "updated_at"])
    return _refresh_collection(collection_id=str(collection.id), include_items=True, refresh=True)


def _create_preflight_collection_item(
    *,
    collection: PoolMasterDataBootstrapCollectionRequest,
    database: Database,
    entity_scope: list[str],
    actor_id: str,
) -> PoolMasterDataBootstrapCollectionItem:
    item_metadata: dict[str, Any] = {
        "database_name": str(database.name),
        "cluster_id": str(database.cluster_id) if database.cluster_id else None,
    }
    preflight = run_pool_master_data_bootstrap_preflight_preview(
        tenant_id=str(collection.tenant_id),
        database=database,
        entity_scope=entity_scope,
        actor_id=actor_id,
    )
    item_metadata["preflight_result"] = preflight
    if not bool(preflight.get("ok")):
        first_error = _first_preflight_error(preflight)
        return PoolMasterDataBootstrapCollectionItem.objects.create(
            collection=collection,
            database=database,
            status=PoolMasterDataBootstrapCollectionItemStatus.FAILED,
            reason_code=str(first_error.get("code") or "BOOTSTRAP_PREFLIGHT_FAILED"),
            reason_detail=sanitize_master_data_sync_text(
                str(first_error.get("detail") or "Bootstrap preflight failed.")
            ),
            metadata=sanitize_master_data_sync_value(item_metadata),
        )
    return PoolMasterDataBootstrapCollectionItem.objects.create(
        collection=collection,
        database=database,
        status=PoolMasterDataBootstrapCollectionItemStatus.COMPLETED,
        metadata=sanitize_master_data_sync_value(item_metadata),
    )


def _process_dry_run_collection_item(
    *,
    collection: PoolMasterDataBootstrapCollectionRequest,
    item: PoolMasterDataBootstrapCollectionItem,
) -> PoolMasterDataBootstrapCollectionItem:
    item_metadata = dict(item.metadata if isinstance(item.metadata, dict) else {})
    database = item.database
    preflight = _as_dict(item_metadata.get("preflight_result"))
    if not bool(preflight.get("ok")):
        first_error = _first_preflight_error(preflight)
        item.status = PoolMasterDataBootstrapCollectionItemStatus.FAILED
        item.reason_code = str(first_error.get("code") or "BOOTSTRAP_PREFLIGHT_FAILED")
        item.reason_detail = sanitize_master_data_sync_text(
            str(first_error.get("detail") or "Bootstrap preflight failed.")
        )
        item.metadata = sanitize_master_data_sync_value(item_metadata)
        item.save(update_fields=["status", "reason_code", "reason_detail", "metadata", "updated_at"])
        return item

    try:
        dry_run_summary = run_pool_master_data_bootstrap_dry_run_preview(
            tenant_id=str(collection.tenant_id),
            database=database,
            entity_scope=list(collection.entity_scope or []),
            actor_id=str(collection.requested_by_id or ""),
            chunk_size=int(_safe_chunk_size((collection.metadata or {}).get("chunk_size"))),
        )
    except ValueError as exc:
        error_code, detail = _resolve_error(exc)
        item.status = PoolMasterDataBootstrapCollectionItemStatus.FAILED
        item.reason_code = error_code
        item.reason_detail = detail
        item.metadata = sanitize_master_data_sync_value(item_metadata)
        item.save(update_fields=["status", "reason_code", "reason_detail", "metadata", "updated_at"])
        return item

    item_metadata["dry_run_summary"] = dry_run_summary
    item.status = PoolMasterDataBootstrapCollectionItemStatus.COMPLETED
    item.reason_code = ""
    item.reason_detail = ""
    item.metadata = sanitize_master_data_sync_value(item_metadata)
    item.save(update_fields=["status", "reason_code", "reason_detail", "metadata", "updated_at"])
    return item


def _process_execute_collection_item(
    *,
    collection: PoolMasterDataBootstrapCollectionRequest,
    item: PoolMasterDataBootstrapCollectionItem,
) -> PoolMasterDataBootstrapCollectionItem:
    database = item.database
    item_metadata = dict(item.metadata if isinstance(item.metadata, dict) else {})
    entity_scope = list(collection.entity_scope or [])
    chunk_size = int(_safe_chunk_size((collection.metadata or {}).get("chunk_size")))

    active_job = _find_compatible_active_execute_job(
        tenant_id=str(collection.tenant_id),
        database_id=str(database.id),
        entity_scope=entity_scope,
    )
    if active_job is not None:
        item_metadata["child_job_status"] = str(active_job.status)
        item.status = PoolMasterDataBootstrapCollectionItemStatus.COALESCED
        item.child_job = active_job
        item.reason_code = "BOOTSTRAP_CHILD_JOB_COALESCED"
        item.reason_detail = "Compatible bootstrap import job is already active for this database."
        item.metadata = sanitize_master_data_sync_value(item_metadata)
        item.save(
            update_fields=[
                "status",
                "child_job",
                "reason_code",
                "reason_detail",
                "metadata",
                "updated_at",
            ]
        )
        return item

    try:
        child_job = create_pool_master_data_bootstrap_import_job(
            tenant=collection.tenant,
            database=database,
            entity_scope=entity_scope,
            mode=BOOTSTRAP_IMPORT_MODE_EXECUTE,
            chunk_size=chunk_size,
            actor_id=str(collection.requested_by_id or ""),
        )
    except BootstrapImportPreflightBlockedError as exc:
        item_metadata["preflight_result"] = dict(exc.preflight_result)
        item.status = PoolMasterDataBootstrapCollectionItemStatus.FAILED
        item.child_job = None
        item.reason_code = str(exc.error_code)
        item.reason_detail = sanitize_master_data_sync_text(str(exc.detail))
        item.metadata = sanitize_master_data_sync_value(item_metadata)
        item.save(
            update_fields=[
                "status",
                "child_job",
                "reason_code",
                "reason_detail",
                "metadata",
                "updated_at",
            ]
        )
        return item
    except ValueError as exc:
        error_code, detail = _resolve_error(exc)
        item.status = PoolMasterDataBootstrapCollectionItemStatus.FAILED
        item.child_job = None
        item.reason_code = error_code
        item.reason_detail = detail
        item.metadata = sanitize_master_data_sync_value(item_metadata)
        item.save(
            update_fields=[
                "status",
                "child_job",
                "reason_code",
                "reason_detail",
                "metadata",
                "updated_at",
            ]
        )
        return item

    item_metadata["child_job_status"] = str(child_job.status)
    item.status = PoolMasterDataBootstrapCollectionItemStatus.SCHEDULED
    item.child_job = child_job
    item.reason_code = ""
    item.reason_detail = ""
    item.metadata = sanitize_master_data_sync_value(item_metadata)
    item.save(
        update_fields=[
            "status",
            "child_job",
            "reason_code",
            "reason_detail",
            "metadata",
            "updated_at",
        ]
    )
    return item


def _refresh_collection(
    *,
    collection_id: str,
    include_items: bool,
    refresh: bool,
) -> PoolMasterDataBootstrapCollectionRequest:
    queryset = PoolMasterDataBootstrapCollectionRequest.objects.select_related("requested_by")
    if include_items:
        queryset = queryset.prefetch_related("items__database", "items__child_job")
    collection = queryset.get(id=str(collection_id))
    if refresh and str(collection.mode) == PoolMasterDataBootstrapCollectionMode.EXECUTE:
        _refresh_scheduled_execute_items(collection_id=str(collection.id))
        queryset = PoolMasterDataBootstrapCollectionRequest.objects.select_related("requested_by")
        if include_items:
            queryset = queryset.prefetch_related("items__database", "items__child_job")
        collection = queryset.get(id=str(collection.id))
    return collection


def _refresh_scheduled_execute_items(*, collection_id: str) -> None:
    collection = (
        PoolMasterDataBootstrapCollectionRequest.objects.select_related("requested_by")
        .prefetch_related("items__database", "items__child_job")
        .get(id=str(collection_id))
    )
    changed = False
    items = _get_collection_items(collection)
    for item in items:
        if item.status != PoolMasterDataBootstrapCollectionItemStatus.SCHEDULED or item.child_job_id is None:
            continue
        child_job = item.child_job
        if child_job is None or child_job.status not in _CHILD_TERMINAL_JOB_STATUSES:
            continue
        item_metadata = dict(item.metadata if isinstance(item.metadata, dict) else {})
        item_metadata["child_job_status"] = str(child_job.status)
        if child_job.status == PoolMasterDataBootstrapImportJobStatus.FINALIZED:
            item.status = PoolMasterDataBootstrapCollectionItemStatus.COMPLETED
            item.reason_code = ""
            item.reason_detail = ""
        else:
            item.status = PoolMasterDataBootstrapCollectionItemStatus.FAILED
            item.reason_code = str(child_job.last_error_code or "BOOTSTRAP_IMPORT_CHILD_JOB_FAILED")
            item.reason_detail = sanitize_master_data_sync_text(
                str(child_job.last_error or "Bootstrap import child job failed.")
            )
        item.metadata = sanitize_master_data_sync_value(item_metadata)
        item.save(update_fields=["status", "reason_code", "reason_detail", "metadata", "updated_at"])
        changed = True
    if changed:
        collection = (
            PoolMasterDataBootstrapCollectionRequest.objects.select_related("requested_by")
            .prefetch_related("items__database", "items__child_job")
            .get(id=str(collection_id))
        )
    _recompute_collection_read_model(collection=collection, items=_get_collection_items(collection))


def _recompute_collection_read_model(
    *,
    collection: PoolMasterDataBootstrapCollectionRequest,
    items: list[PoolMasterDataBootstrapCollectionItem],
) -> None:
    metadata = dict(collection.metadata if isinstance(collection.metadata, dict) else {})
    counters = {
        "total_items": len(items),
        "pending": 0,
        "scheduled": 0,
        "coalesced": 0,
        "skipped": 0,
        "failed": 0,
        "completed": 0,
    }
    child_job_status_counts: dict[str, int] = defaultdict(int)
    for item in items:
        status_key = str(item.status or "").strip().lower()
        if status_key in counters:
            counters[status_key] += 1
        if item.child_job_id and item.child_job is not None:
            child_job_status_counts[str(item.child_job.status)] += 1

    terminal_items = counters["coalesced"] + counters["skipped"] + counters["failed"] + counters["completed"]
    progress = {
        **counters,
        "terminal_items": terminal_items,
        "fanout_processed_items": terminal_items,
        "completion_ratio": round((terminal_items / len(items)), 4) if items else 0.0,
    }
    forced_status = str(metadata.get(_COLLECTION_FORCED_STATUS) or "").strip()
    if forced_status == PoolMasterDataBootstrapCollectionStatus.FAILED:
        collection_status = PoolMasterDataBootstrapCollectionStatus.FAILED
    else:
        collection_status = _resolve_collection_status(mode=str(collection.mode), counters=counters)

    latest_failed_item = next(
        (
            current
            for current in sorted(items, key=lambda item: item.updated_at, reverse=True)
            if str(current.reason_code or "").strip()
            and current.status == PoolMasterDataBootstrapCollectionItemStatus.FAILED
        ),
        None,
    )

    metadata["aggregate_counters"] = counters
    metadata["progress"] = progress
    metadata["child_job_status_counts"] = dict(child_job_status_counts)
    metadata["aggregate_preflight_result"] = _aggregate_preflight_result(collection=collection, items=items)
    metadata["aggregate_dry_run_summary"] = _aggregate_dry_run_summary(items)
    collection.metadata = sanitize_master_data_sync_value(metadata)
    collection.status = collection_status
    if latest_failed_item is not None:
        collection.last_error_code = str(latest_failed_item.reason_code or "")
        collection.last_error = sanitize_master_data_sync_text(str(latest_failed_item.reason_detail or ""))
    elif collection.status == PoolMasterDataBootstrapCollectionStatus.FAILED:
        collection.last_error_code = str(collection.last_error_code or "").strip() or "BOOTSTRAP_COLLECTION_FAILED"
        collection.last_error = sanitize_master_data_sync_text(str(collection.last_error or "").strip())
        if not collection.last_error:
            collection.last_error = "Bootstrap collection failed."
    else:
        collection.last_error_code = ""
        collection.last_error = ""
    collection.save(update_fields=["status", "last_error_code", "last_error", "metadata", "updated_at"])


def _resolve_collection_status(*, mode: str, counters: Mapping[str, int]) -> str:
    pending = int(counters.get("pending") or 0)
    scheduled = int(counters.get("scheduled") or 0)
    failed = int(counters.get("failed") or 0)
    total_items = int(counters.get("total_items") or 0)
    if mode == PoolMasterDataBootstrapCollectionMode.PREFLIGHT:
        if failed > 0:
            return PoolMasterDataBootstrapCollectionStatus.FAILED
        return PoolMasterDataBootstrapCollectionStatus.PREFLIGHT_COMPLETED
    if mode == PoolMasterDataBootstrapCollectionMode.DRY_RUN:
        if pending > 0:
            return PoolMasterDataBootstrapCollectionStatus.DRY_RUN_RUNNING
        if failed > 0 and total_items > 0:
            return PoolMasterDataBootstrapCollectionStatus.FAILED
        return PoolMasterDataBootstrapCollectionStatus.DRY_RUN_COMPLETED
    if pending > 0 or scheduled > 0:
        return PoolMasterDataBootstrapCollectionStatus.EXECUTE_RUNNING
    if failed >= total_items and total_items > 0:
        return PoolMasterDataBootstrapCollectionStatus.FAILED
    return PoolMasterDataBootstrapCollectionStatus.FINALIZED


def _validate_collection_scope(
    *,
    collection: PoolMasterDataBootstrapCollectionRequest,
    target_mode: str,
    cluster_id: str | None,
    database_ids: Iterable[str] | None,
    entity_scope: list[str],
) -> None:
    if str(collection.target_mode) != str(target_mode):
        raise ValueError(
            f"{BOOTSTRAP_COLLECTION_STAGE_SCOPE_MISMATCH}: target_mode does not match stored snapshot"
        )
    if target_mode == PoolMasterDataBootstrapCollectionTargetMode.CLUSTER_ALL:
        if str(collection.cluster_id or "") != str(cluster_id or "").strip():
            raise ValueError(
                f"{BOOTSTRAP_COLLECTION_STAGE_SCOPE_MISMATCH}: cluster_id does not match stored snapshot"
            )
    else:
        normalized_database_ids = [
            str(value or "").strip() for value in (database_ids or []) if str(value or "").strip()
        ]
        if list(collection.database_ids or []) != list(dict.fromkeys(normalized_database_ids)):
            raise ValueError(
                f"{BOOTSTRAP_COLLECTION_STAGE_SCOPE_MISMATCH}: database_ids do not match stored snapshot"
            )
    if list(collection.entity_scope or []) != list(entity_scope or []):
        raise ValueError(
            f"{BOOTSTRAP_COLLECTION_STAGE_SCOPE_MISMATCH}: entity_scope does not match stored snapshot"
        )


def _get_collection_items(
    collection: PoolMasterDataBootstrapCollectionRequest,
) -> list[PoolMasterDataBootstrapCollectionItem]:
    rows = list(collection.items.select_related("database", "child_job").all())
    order = {database_id: index for index, database_id in enumerate(collection.database_ids or [])}
    return sorted(
        rows,
        key=lambda item: (
            order.get(str(item.database_id), len(order)),
            str(getattr(item.database, "name", "") or ""),
            str(item.database_id),
        ),
    )


def _resolve_collection_targets(
    *,
    tenant_id: str,
    target_mode: str,
    cluster_id: str | None,
    database_ids: Iterable[str] | None,
) -> tuple[UUID | None, list[Database]]:
    normalized_tenant_id = str(tenant_id or "").strip()
    if target_mode == PoolMasterDataBootstrapCollectionTargetMode.CLUSTER_ALL:
        normalized_cluster_id = str(cluster_id or "").strip()
        if not normalized_cluster_id:
            raise ValueError(f"{BOOTSTRAP_COLLECTION_CLUSTER_REQUIRED}: cluster_id is required")
        cluster = Cluster.objects.filter(id=normalized_cluster_id, tenant_id=normalized_tenant_id).first()
        if cluster is None:
            raise LookupError(
                f"{BOOTSTRAP_COLLECTION_CLUSTER_NOT_FOUND}: cluster '{normalized_cluster_id}' was not found"
            )
        databases = list(
            Database.objects.filter(tenant_id=normalized_tenant_id, cluster_id=cluster.id)
            .order_by("name", "id")
            .all()
        )
        if not databases:
            raise ValueError(
                f"{BOOTSTRAP_COLLECTION_EMPTY_TARGETS}: cluster '{normalized_cluster_id}' does not have databases"
            )
        return cluster.id, databases

    selected_database_ids = [str(value or "").strip() for value in (database_ids or []) if str(value or "").strip()]
    if not selected_database_ids:
        raise ValueError(f"{BOOTSTRAP_COLLECTION_DATABASE_IDS_REQUIRED}: database_ids must not be empty")
    deduped_database_ids = list(dict.fromkeys(selected_database_ids))
    database_map = {
        str(database.id): database
        for database in Database.objects.filter(
            tenant_id=normalized_tenant_id,
            id__in=deduped_database_ids,
        ).all()
    }
    missing_ids = [database_id for database_id in deduped_database_ids if database_id not in database_map]
    if missing_ids:
        raise LookupError(
            f"{BOOTSTRAP_COLLECTION_DATABASE_NOT_FOUND}: "
            f"databases were not found in current tenant context: {', '.join(missing_ids)}"
        )
    return None, [database_map[database_id] for database_id in deduped_database_ids]


def _normalize_target_mode(target_mode: str) -> str:
    normalized = str(target_mode or "").strip().lower()
    if normalized not in {
        PoolMasterDataBootstrapCollectionTargetMode.CLUSTER_ALL,
        PoolMasterDataBootstrapCollectionTargetMode.DATABASE_SET,
    }:
        raise ValueError(f"{BOOTSTRAP_COLLECTION_TARGET_MODE_INVALID}: unsupported target_mode '{target_mode}'")
    return normalized


def _normalize_mode(mode: str) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized not in {
        PoolMasterDataBootstrapCollectionMode.PREFLIGHT,
        PoolMasterDataBootstrapCollectionMode.DRY_RUN,
        PoolMasterDataBootstrapCollectionMode.EXECUTE,
    }:
        raise ValueError(f"{BOOTSTRAP_COLLECTION_MODE_INVALID}: unsupported mode '{mode}'")
    return normalized


def _normalize_entity_scope(entity_scope: Iterable[str]) -> list[str]:
    selected = [str(value or "").strip() for value in (entity_scope or []) if str(value or "").strip()]
    if not selected:
        raise ValueError(f"{BOOTSTRAP_COLLECTION_SCOPE_EMPTY}: entity_scope must not be empty")
    return list(resolve_bootstrap_import_dependency_order(selected_scope=selected))


def _find_compatible_active_execute_job(
    *,
    tenant_id: str,
    database_id: str,
    entity_scope: list[str],
) -> PoolMasterDataBootstrapImportJob | None:
    rows = (
        PoolMasterDataBootstrapImportJob.objects.filter(
            tenant_id=str(tenant_id),
            database_id=str(database_id),
            status__in=_CHILD_ACTIVE_EXECUTE_JOB_STATUSES,
        )
        .order_by("-created_at")
        .all()
    )
    normalized_scope = list(entity_scope or [])
    for row in rows:
        metadata = row.metadata if isinstance(row.metadata, dict) else {}
        if str(metadata.get("mode") or "").strip() != BOOTSTRAP_IMPORT_MODE_EXECUTE:
            continue
        if list(row.entity_scope or []) == normalized_scope:
            return row
    return None


def _aggregate_preflight_result(
    *,
    collection: PoolMasterDataBootstrapCollectionRequest,
    items: list[PoolMasterDataBootstrapCollectionItem],
) -> dict[str, Any]:
    database_entries: list[dict[str, Any]] = []
    aggregate_errors: list[dict[str, Any]] = []
    all_ok = True
    for item in items:
        metadata = item.metadata if isinstance(item.metadata, dict) else {}
        preflight = _as_dict(metadata.get("preflight_result"))
        item_ok = bool(preflight.get("ok"))
        if not item_ok:
            all_ok = False
            first_error = _first_preflight_error(preflight)
            aggregate_errors.append(
                {
                    "database_id": str(item.database_id),
                    "database_name": str(getattr(item.database, "name", "") or metadata.get("database_name") or ""),
                    "cluster_id": (
                        str(getattr(item.database, "cluster_id", None))
                        if getattr(item.database, "cluster_id", None)
                        else metadata.get("cluster_id")
                    ),
                    "code": str(first_error.get("code") or ""),
                    "detail": str(first_error.get("detail") or ""),
                }
            )
        database_entries.append(
            {
                "database_id": str(item.database_id),
                "database_name": str(getattr(item.database, "name", "") or metadata.get("database_name") or ""),
                "cluster_id": (
                    str(getattr(item.database, "cluster_id", None))
                    if getattr(item.database, "cluster_id", None)
                    else metadata.get("cluster_id")
                ),
                "ok": item_ok,
                "preflight_result": preflight,
            }
        )
    return sanitize_master_data_sync_value(
        {
            "ok": all_ok,
            "target_mode": str(collection.target_mode),
            "cluster_id": str(collection.cluster_id) if collection.cluster_id else None,
            "database_ids": list(collection.database_ids or []),
            "database_count": len(items),
            "entity_scope": list(collection.entity_scope or []),
            "databases": database_entries,
            "errors": aggregate_errors,
            "generated_at": timezone.now().isoformat(),
        }
    )


def _aggregate_dry_run_summary(
    items: list[PoolMasterDataBootstrapCollectionItem],
) -> dict[str, Any]:
    entity_totals: dict[str, dict[str, Any]] = {}
    rows_total = 0
    chunks_total = 0
    for item in items:
        metadata = item.metadata if isinstance(item.metadata, dict) else {}
        summary = metadata.get("dry_run_summary")
        if not isinstance(summary, dict):
            continue
        rows_total += int(summary.get("rows_total") or 0)
        chunks_total += int(summary.get("chunks_total") or 0)
        for entity_summary in summary.get("entities") or []:
            if not isinstance(entity_summary, dict):
                continue
            entity_type = str(entity_summary.get("entity_type") or "").strip()
            if not entity_type:
                continue
            current = entity_totals.setdefault(
                entity_type,
                {
                    "entity_type": entity_type,
                    "rows_total": 0,
                    "chunks_total": 0,
                },
            )
            current["rows_total"] += int(entity_summary.get("rows_total") or 0)
            current["chunks_total"] += int(entity_summary.get("chunks_total") or 0)
    return sanitize_master_data_sync_value(
        {
            "rows_total": rows_total,
            "chunks_total": chunks_total,
            "entities": sorted(entity_totals.values(), key=lambda item: str(item["entity_type"])),
            "generated_at": timezone.now().isoformat(),
        }
    )


def _serialize_collection_item(item: PoolMasterDataBootstrapCollectionItem) -> dict[str, Any]:
    metadata = item.metadata if isinstance(item.metadata, dict) else {}
    child_job = item.child_job
    return {
        "id": str(item.id),
        "database_id": str(item.database_id),
        "database_name": str(getattr(item.database, "name", "") or metadata.get("database_name") or ""),
        "cluster_id": (
            str(getattr(item.database, "cluster_id", None))
            if getattr(item.database, "cluster_id", None)
            else metadata.get("cluster_id")
        ),
        "status": str(item.status),
        "reason_code": str(item.reason_code or ""),
        "reason_detail": sanitize_master_data_sync_text(str(item.reason_detail or "")),
        "child_job_id": str(item.child_job_id) if item.child_job_id else None,
        "child_job_status": (
            str(child_job.status) if child_job is not None else str(metadata.get("child_job_status") or "")
        ),
        "preflight_result": _as_dict(metadata.get("preflight_result")),
        "dry_run_summary": _as_dict(metadata.get("dry_run_summary")),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _append_collection_audit(
    *,
    collection: PoolMasterDataBootstrapCollectionRequest,
    action: str,
    actor_id: str,
    actor_username: str,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    payload = sanitize_master_data_sync_value(dict(metadata or {}))
    collection_metadata = dict(collection.metadata if isinstance(collection.metadata, dict) else {})
    history = collection_metadata.get("audit_trail")
    events = list(history) if isinstance(history, list) else []
    events.append(
        {
            "action": str(action or "").strip(),
            "actor_id": str(actor_id or "").strip(),
            "actor_username": str(actor_username or "").strip(),
            "at": timezone.now().isoformat(),
            "metadata": payload,
        }
    )
    collection_metadata["audit_trail"] = events[-200:]
    collection.metadata = sanitize_master_data_sync_value(collection_metadata)
    collection.save(update_fields=["metadata", "updated_at"])


def _read_requested_by_username(collection: PoolMasterDataBootstrapCollectionRequest) -> str:
    requested_by = getattr(collection, "requested_by", None)
    if requested_by is None:
        return ""
    return str(getattr(requested_by, "username", "") or "").strip()


def _first_preflight_error(preflight: Mapping[str, Any]) -> dict[str, Any]:
    errors = preflight.get("errors")
    if isinstance(errors, list):
        for error in errors:
            if isinstance(error, dict):
                return error
    return {"code": "BOOTSTRAP_PREFLIGHT_FAILED", "detail": "Bootstrap preflight failed."}


def _resolve_error(exc: Exception) -> tuple[str, str]:
    detail = sanitize_master_data_sync_text(str(exc) or "Bootstrap collection failed.")
    if ":" in detail:
        prefix, remainder = detail.split(":", 1)
        error_code = str(prefix or "").strip()
        error_detail = sanitize_master_data_sync_text(str(remainder or "").strip() or detail)
        if error_code and error_code.upper() == error_code:
            return error_code, error_detail
    return "BOOTSTRAP_COLLECTION_FAILED", detail


def _running_status_for_stage(stage: str) -> str:
    if stage == PoolMasterDataBootstrapCollectionMode.DRY_RUN:
        return PoolMasterDataBootstrapCollectionStatus.DRY_RUN_RUNNING
    return PoolMasterDataBootstrapCollectionStatus.EXECUTE_RUNNING


def _runner_token_matches(
    *,
    collection: PoolMasterDataBootstrapCollectionRequest,
    stage: str,
    runner_token: str,
) -> bool:
    metadata = collection.metadata if isinstance(collection.metadata, dict) else {}
    runner = metadata.get(_COLLECTION_STAGE_RUNNER)
    if not isinstance(runner, dict):
        return False
    return (
        str(runner.get("stage") or "").strip() == str(stage)
        and str(runner.get("token") or "").strip() == str(runner_token or "").strip()
    )


def _derive_collection_fanout_batch_size(chunk_size: int) -> int:
    return max(1, min(int(chunk_size or 0) or _DEFAULT_COLLECTION_FANOUT_BATCH_SIZE, _DEFAULT_COLLECTION_FANOUT_BATCH_SIZE))


def _safe_chunk_size(value: Any) -> int:
    try:
        chunk_size = int(value)
    except (TypeError, ValueError):
        return 200
    return max(1, min(chunk_size, 1000))


def _safe_fanout_batch_size(value: Any) -> int:
    try:
        fanout_batch_size = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_COLLECTION_FANOUT_BATCH_SIZE
    return max(1, min(fanout_batch_size, _DEFAULT_COLLECTION_FANOUT_BATCH_SIZE))


def _as_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return sanitize_master_data_sync_value(dict(value))


def _as_list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    return sanitize_master_data_sync_value(list(value))


__all__ = [
    "BOOTSTRAP_COLLECTION_CLUSTER_NOT_FOUND",
    "BOOTSTRAP_COLLECTION_DATABASE_NOT_FOUND",
    "BOOTSTRAP_COLLECTION_DRY_RUN_BLOCKED",
    "BOOTSTRAP_COLLECTION_DRY_RUN_COLLECTION_REQUIRED",
    "BOOTSTRAP_COLLECTION_EMPTY_TARGETS",
    "BOOTSTRAP_COLLECTION_EXECUTE_BLOCKED",
    "BOOTSTRAP_COLLECTION_EXECUTE_COLLECTION_REQUIRED",
    "BOOTSTRAP_COLLECTION_REQUEST_NOT_FOUND",
    "BOOTSTRAP_COLLECTION_STAGE_SCOPE_MISMATCH",
    "PoolMasterDataBootstrapCollectionStageChunkResult",
    "_COLLECTION_OPERATION_ID",
    "_COLLECTION_STAGE_RUNNER",
    "_COLLECTION_WORKFLOW_EXECUTION_ID",
    "create_pool_master_data_bootstrap_collection_preflight_request",
    "create_pool_master_data_bootstrap_collection_request",
    "get_pool_master_data_bootstrap_collection_request",
    "list_pool_master_data_bootstrap_collection_requests",
    "mark_pool_master_data_bootstrap_collection_failed",
    "run_pool_master_data_bootstrap_collection_preflight_preview",
    "run_pool_master_data_bootstrap_collection_stage_chunk",
    "serialize_pool_master_data_bootstrap_collection_request",
]
