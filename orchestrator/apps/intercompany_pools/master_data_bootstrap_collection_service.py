from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.databases.models import Cluster, Database
from apps.tenancy.models import Tenant

from .master_data_bootstrap_import_service import (
    BOOTSTRAP_IMPORT_MODE_EXECUTE,
    BootstrapImportPreflightBlockedError,
    create_pool_master_data_bootstrap_import_job,
    run_pool_master_data_bootstrap_dry_run_preview,
    run_pool_master_data_bootstrap_preflight_preview,
)
from .master_data_bootstrap_import_dependency_order import resolve_bootstrap_import_dependency_order
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

_CHILD_TERMINAL_JOB_STATUSES = {
    PoolMasterDataBootstrapImportJobStatus.FINALIZED,
    PoolMasterDataBootstrapImportJobStatus.FAILED,
    PoolMasterDataBootstrapImportJobStatus.CANCELED,
}
_CHILD_ACTIVE_EXECUTE_JOB_STATUSES = {
    PoolMasterDataBootstrapImportJobStatus.EXECUTE_PENDING,
    PoolMasterDataBootstrapImportJobStatus.RUNNING,
}


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


def create_pool_master_data_bootstrap_collection_request(
    *,
    tenant: Tenant,
    target_mode: str,
    cluster_id: str | None,
    database_ids: Iterable[str] | None,
    entity_scope: Iterable[str],
    mode: str,
    actor_id: str,
    actor_username: str = "",
    chunk_size: int = 200,
) -> PoolMasterDataBootstrapCollectionRequest:
    resolved_target_mode = _normalize_target_mode(target_mode)
    resolved_mode = _normalize_mode(mode)
    normalized_scope = _normalize_entity_scope(entity_scope)
    resolved_cluster_id, databases = _resolve_collection_targets(
        tenant_id=str(tenant.id),
        target_mode=resolved_target_mode,
        cluster_id=cluster_id,
        database_ids=database_ids,
    )
    initial_status = (
        PoolMasterDataBootstrapCollectionStatus.DRY_RUN_COMPLETED
        if resolved_mode == PoolMasterDataBootstrapCollectionMode.DRY_RUN
        else PoolMasterDataBootstrapCollectionStatus.EXECUTE_RUNNING
    )
    with transaction.atomic():
        collection = PoolMasterDataBootstrapCollectionRequest.objects.create(
            tenant=tenant,
            target_mode=resolved_target_mode,
            mode=resolved_mode,
            cluster_id=resolved_cluster_id,
            database_ids=[str(database.id) for database in databases],
            entity_scope=normalized_scope,
            status=initial_status,
            requested_by_id=str(actor_id or "").strip() or None,
            metadata={
                "chunk_size": int(_safe_chunk_size(chunk_size)),
                "audit_trail": [],
            },
        )
        _append_collection_audit(
            collection=collection,
            action="collection_created",
            actor_id=actor_id,
            actor_username=actor_username,
            metadata={
                "target_mode": resolved_target_mode,
                "mode": resolved_mode,
                "database_ids": [str(database.id) for database in databases],
                "entity_scope": normalized_scope,
            },
        )
        items: list[PoolMasterDataBootstrapCollectionItem] = []
        for database in databases:
            items.append(
                _create_collection_item(
                    collection=collection,
                    database=database,
                    mode=resolved_mode,
                    entity_scope=normalized_scope,
                    actor_id=actor_id,
                    chunk_size=int(_safe_chunk_size(chunk_size)),
                )
            )
        _recompute_collection_read_model(collection=collection, items=items)
        collection = _refresh_collection(
            collection_id=str(collection.id),
            include_items=False,
            refresh=True,
        )
    return collection


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
        "aggregate_dry_run_summary": _as_dict(metadata.get("aggregate_dry_run_summary")),
        "audit_trail": _as_list(metadata.get("audit_trail")),
        "created_at": collection.created_at,
        "updated_at": collection.updated_at,
    }
    if include_items:
        payload["items"] = [
            _serialize_collection_item(item)
            for item in collection.items.select_related("database", "child_job")
            .order_by("database__name", "database_id")
            .all()
        ]
    return payload


def _create_collection_item(
    *,
    collection: PoolMasterDataBootstrapCollectionRequest,
    database: Database,
    mode: str,
    entity_scope: list[str],
    actor_id: str,
    chunk_size: int,
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
        item = PoolMasterDataBootstrapCollectionItem.objects.create(
            collection=collection,
            database=database,
            status=PoolMasterDataBootstrapCollectionItemStatus.FAILED,
            reason_code=str(first_error.get("code") or "BOOTSTRAP_PREFLIGHT_FAILED"),
            reason_detail=sanitize_master_data_sync_text(
                str(first_error.get("detail") or "Bootstrap preflight failed.")
            ),
            metadata=sanitize_master_data_sync_value(item_metadata),
        )
        return item

    dry_run_summary = run_pool_master_data_bootstrap_dry_run_preview(
        tenant_id=str(collection.tenant_id),
        database=database,
        entity_scope=entity_scope,
        actor_id=actor_id,
        chunk_size=chunk_size,
    )
    item_metadata["dry_run_summary"] = dry_run_summary

    if mode == PoolMasterDataBootstrapCollectionMode.DRY_RUN:
        return PoolMasterDataBootstrapCollectionItem.objects.create(
            collection=collection,
            database=database,
            status=PoolMasterDataBootstrapCollectionItemStatus.COMPLETED,
            metadata=sanitize_master_data_sync_value(item_metadata),
        )

    active_job = _find_compatible_active_execute_job(
        tenant_id=str(collection.tenant_id),
        database_id=str(database.id),
        entity_scope=entity_scope,
    )
    if active_job is not None:
        item_metadata["child_job_status"] = str(active_job.status)
        return PoolMasterDataBootstrapCollectionItem.objects.create(
            collection=collection,
            database=database,
            status=PoolMasterDataBootstrapCollectionItemStatus.COALESCED,
            child_job=active_job,
            reason_code="BOOTSTRAP_CHILD_JOB_COALESCED",
            reason_detail="Compatible bootstrap import job is already active for this database.",
            metadata=sanitize_master_data_sync_value(item_metadata),
        )

    try:
        child_job = create_pool_master_data_bootstrap_import_job(
            tenant=collection.tenant,
            database=database,
            entity_scope=entity_scope,
            mode=BOOTSTRAP_IMPORT_MODE_EXECUTE,
            chunk_size=chunk_size,
            actor_id=actor_id,
        )
    except BootstrapImportPreflightBlockedError as exc:
        item_metadata["preflight_result"] = dict(exc.preflight_result)
        return PoolMasterDataBootstrapCollectionItem.objects.create(
            collection=collection,
            database=database,
            status=PoolMasterDataBootstrapCollectionItemStatus.FAILED,
            reason_code=str(exc.error_code),
            reason_detail=sanitize_master_data_sync_text(str(exc.detail)),
            metadata=sanitize_master_data_sync_value(item_metadata),
        )
    except ValueError as exc:
        error_code, detail = _resolve_error(exc)
        return PoolMasterDataBootstrapCollectionItem.objects.create(
            collection=collection,
            database=database,
            status=PoolMasterDataBootstrapCollectionItemStatus.FAILED,
            reason_code=error_code,
            reason_detail=detail,
            metadata=sanitize_master_data_sync_value(item_metadata),
        )

    item_metadata["child_job_status"] = str(child_job.status)
    return PoolMasterDataBootstrapCollectionItem.objects.create(
        collection=collection,
        database=database,
        status=PoolMasterDataBootstrapCollectionItemStatus.SCHEDULED,
        child_job=child_job,
        metadata=sanitize_master_data_sync_value(item_metadata),
    )


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
    items = list(collection.items.select_related("database", "child_job").all())
    for item in items:
        if item.status != PoolMasterDataBootstrapCollectionItemStatus.SCHEDULED or item.child_job_id is None:
            continue
        child_job = item.child_job
        if child_job is None or child_job.status not in _CHILD_TERMINAL_JOB_STATUSES:
            continue
        item_metadata = item.metadata if isinstance(item.metadata, dict) else {}
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
        item.save(
            update_fields=[
                "status",
                "reason_code",
                "reason_detail",
                "metadata",
                "updated_at",
            ]
        )
        changed = True
    if changed:
        collection = (
            PoolMasterDataBootstrapCollectionRequest.objects.select_related("requested_by")
            .prefetch_related("items__database", "items__child_job")
            .get(id=str(collection_id))
        )
    _recompute_collection_read_model(collection=collection, items=list(collection.items.all()))


def _recompute_collection_read_model(
    *,
    collection: PoolMasterDataBootstrapCollectionRequest,
    items: list[PoolMasterDataBootstrapCollectionItem],
) -> None:
    metadata = collection.metadata if isinstance(collection.metadata, dict) else {}
    aggregate_dry_run = _aggregate_dry_run_summary(items)
    counters = {
        "total_items": len(items),
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
        "completion_ratio": round((terminal_items / len(items)), 4) if items else 0.0,
    }
    collection_status = _resolve_collection_status(
        mode=str(collection.mode),
        counters=counters,
    )
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
    metadata["aggregate_dry_run_summary"] = aggregate_dry_run
    collection.metadata = sanitize_master_data_sync_value(metadata)
    collection.status = collection_status
    if latest_failed_item is not None:
        collection.last_error_code = str(latest_failed_item.reason_code or "")
        collection.last_error = sanitize_master_data_sync_text(str(latest_failed_item.reason_detail or ""))
    elif collection.status == PoolMasterDataBootstrapCollectionStatus.FAILED:
        collection.last_error_code = "BOOTSTRAP_COLLECTION_FAILED"
        collection.last_error = "Bootstrap collection failed."
    else:
        collection.last_error_code = ""
        collection.last_error = ""
    collection.save(
        update_fields=[
            "status",
            "last_error_code",
            "last_error",
            "metadata",
            "updated_at",
        ]
    )


def _resolve_collection_status(*, mode: str, counters: Mapping[str, int]) -> str:
    scheduled = int(counters.get("scheduled") or 0)
    failed = int(counters.get("failed") or 0)
    total_items = sum(int(value or 0) for value in counters.values() if isinstance(value, int))
    if mode == PoolMasterDataBootstrapCollectionMode.DRY_RUN:
        return (
            PoolMasterDataBootstrapCollectionStatus.FAILED
            if failed >= total_items and total_items > 0
            else PoolMasterDataBootstrapCollectionStatus.DRY_RUN_COMPLETED
        )
    if scheduled > 0:
        return PoolMasterDataBootstrapCollectionStatus.EXECUTE_RUNNING
    if failed >= total_items and total_items > 0:
        return PoolMasterDataBootstrapCollectionStatus.FAILED
    return PoolMasterDataBootstrapCollectionStatus.FINALIZED


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
        "child_job_status": str(child_job.status) if child_job is not None else str(metadata.get("child_job_status") or ""),
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
    collection_metadata = collection.metadata if isinstance(collection.metadata, dict) else {}
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
    collection.metadata = collection_metadata
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


def _safe_chunk_size(value: Any) -> int:
    try:
        chunk_size = int(value)
    except (TypeError, ValueError):
        return 200
    return max(1, min(chunk_size, 1000))


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
    "BOOTSTRAP_COLLECTION_EMPTY_TARGETS",
    "BOOTSTRAP_COLLECTION_REQUEST_NOT_FOUND",
    "create_pool_master_data_bootstrap_collection_request",
    "get_pool_master_data_bootstrap_collection_request",
    "list_pool_master_data_bootstrap_collection_requests",
    "run_pool_master_data_bootstrap_collection_preflight_preview",
    "serialize_pool_master_data_bootstrap_collection_request",
]
