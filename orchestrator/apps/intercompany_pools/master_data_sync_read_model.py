from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from typing import Any

from django.utils import timezone

from apps.operations.models import BatchOperation, WorkflowEnqueueOutbox

from .models import (
    PoolMasterDataSyncCheckpoint,
    PoolMasterDataSyncConflict,
    PoolMasterDataSyncConflictStatus,
    PoolMasterDataSyncJob,
    PoolMasterDataSyncJobStatus,
    PoolMasterDataSyncOutbox,
    PoolMasterDataSyncOutboxStatus,
)


def list_master_data_sync_status_rows(
    *,
    tenant_id: str,
    database_id: str | None = None,
    entity_type: str | None = None,
    priority: str | None = None,
    role: str | None = None,
    server_affinity: str | None = None,
    deadline_state: str | None = None,
) -> list[dict[str, Any]]:
    checkpoint_filters: dict[str, Any] = {"tenant_id": tenant_id}
    outbox_filters: dict[str, Any] = {"tenant_id": tenant_id}
    conflict_filters: dict[str, Any] = {"tenant_id": tenant_id}
    sync_job_filters: dict[str, Any] = {"tenant_id": tenant_id}
    if database_id:
        checkpoint_filters["database_id"] = database_id
        outbox_filters["database_id"] = database_id
        conflict_filters["database_id"] = database_id
        sync_job_filters["database_id"] = database_id
    if entity_type:
        checkpoint_filters["entity_type"] = entity_type
        outbox_filters["entity_type"] = entity_type
        conflict_filters["entity_type"] = entity_type
        sync_job_filters["entity_type"] = entity_type

    scopes: dict[tuple[str, str], dict[str, Any]] = {}
    now = timezone.now()

    for checkpoint in PoolMasterDataSyncCheckpoint.objects.filter(**checkpoint_filters).order_by("database_id", "entity_type"):
        key = (str(checkpoint.database_id), str(checkpoint.entity_type))
        row = scopes.setdefault(key, _empty_scope_row(tenant_id=tenant_id, database_id=key[0], entity_type=key[1]))
        metadata = checkpoint.metadata if isinstance(checkpoint.metadata, dict) else {}
        row["checkpoint_token"] = str(checkpoint.checkpoint_token or "")
        row["pending_checkpoint_token"] = str(metadata.get("pending_checkpoint_token") or "")
        row["checkpoint_status"] = str(checkpoint.status or "")
        row["last_error_code"] = str(checkpoint.last_error_code or "")
        row["last_applied_at"] = checkpoint.last_applied_at
        row["last_success_at"] = _latest_dt(row.get("last_success_at"), checkpoint.last_applied_at)

    for outbox in PoolMasterDataSyncOutbox.objects.filter(**outbox_filters).order_by("database_id", "entity_type"):
        key = (str(outbox.database_id), str(outbox.entity_type))
        row = scopes.setdefault(key, _empty_scope_row(tenant_id=tenant_id, database_id=key[0], entity_type=key[1]))
        status = str(outbox.status or "")
        if status == PoolMasterDataSyncOutboxStatus.PENDING:
            row["pending_count"] += 1
            row["lag_seconds"] = _lag_seconds(now=now, current=row["lag_seconds"], candidate=outbox.available_at)
        elif status == PoolMasterDataSyncOutboxStatus.FAILED:
            row["retry_count"] += 1
            row["lag_seconds"] = _lag_seconds(now=now, current=row["lag_seconds"], candidate=outbox.available_at)
        row["last_success_at"] = _latest_dt(row.get("last_success_at"), outbox.dispatched_at)

    for conflict in PoolMasterDataSyncConflict.objects.filter(**conflict_filters).order_by("database_id", "entity_type"):
        key = (str(conflict.database_id), str(conflict.entity_type))
        row = scopes.setdefault(key, _empty_scope_row(tenant_id=tenant_id, database_id=key[0], entity_type=key[1]))
        status = str(conflict.status or "")
        if status == PoolMasterDataSyncConflictStatus.PENDING:
            row["conflict_pending_count"] += 1
        elif status == PoolMasterDataSyncConflictStatus.RETRYING:
            row["conflict_retrying_count"] += 1

    sync_jobs = list(
        PoolMasterDataSyncJob.objects.filter(**sync_job_filters).order_by("database_id", "entity_type", "-updated_at")
    )
    operation_ids = [
        str(job.operation_id)
        for job in sync_jobs
        if getattr(job, "operation_id", None) is not None
    ]
    operation_metadata_map: dict[str, dict[str, Any]] = {}
    if operation_ids:
        for operation in BatchOperation.objects.filter(id__in=operation_ids).values("id", "metadata"):
            metadata = operation.get("metadata")
            operation_metadata_map[str(operation["id"])] = metadata if isinstance(metadata, dict) else {}

    workflow_outbox_map: dict[str, dict[str, Any]] = {}
    if operation_ids:
        for outbox in WorkflowEnqueueOutbox.objects.filter(
            operation_id__in=operation_ids,
            status=WorkflowEnqueueOutbox.STATUS_PENDING,
        ).values("operation_id", "dispatch_attempts", "last_error_code", "last_error"):
            workflow_outbox_map[str(outbox["operation_id"])] = {
                "dispatch_attempts": int(outbox.get("dispatch_attempts") or 0),
                "last_error_code": str(outbox.get("last_error_code") or ""),
                "last_error": str(outbox.get("last_error") or ""),
            }

    for sync_job in sync_jobs:
        key = (str(sync_job.database_id), str(sync_job.entity_type))
        row = scopes.setdefault(key, _empty_scope_row(tenant_id=tenant_id, database_id=key[0], entity_type=key[1]))

        operation_id = str(sync_job.operation_id) if sync_job.operation_id is not None else ""
        scheduling = _extract_scheduling_metadata(operation_metadata_map.get(operation_id, {}))

        latest_job_updated_at = _latest_dt(row.get("_latest_job_updated_at"), sync_job.updated_at)
        if latest_job_updated_at == sync_job.updated_at:
            row["_latest_job_updated_at"] = sync_job.updated_at
            row["_latest_job_finished_at"] = sync_job.finished_at or sync_job.updated_at
            row["_latest_job_status"] = str(sync_job.status or "")
            row["priority"] = scheduling["priority"]
            row["role"] = scheduling["role"]
            row["server_affinity"] = scheduling["server_affinity"]
            row["deadline_at"] = scheduling["deadline_at"]

        queue_state = _resolve_queue_state(sync_job=sync_job, workflow_outbox_map=workflow_outbox_map)
        row["queue_states"][queue_state] = int(row["queue_states"].get(queue_state) or 0) + 1

        if queue_state == "retrying":
            outbox_snapshot = workflow_outbox_map.get(operation_id, {})
            if outbox_snapshot.get("last_error_code"):
                row["last_error_code"] = str(outbox_snapshot["last_error_code"])
            if outbox_snapshot.get("last_error"):
                row["last_error_reason"] = str(outbox_snapshot["last_error"])
        elif str(sync_job.status or "") == PoolMasterDataSyncJobStatus.FAILED:
            if sync_job.last_error_code:
                row["last_error_code"] = str(sync_job.last_error_code)
            if sync_job.last_error:
                row["last_error_reason"] = str(sync_job.last_error)

    filtered_rows: list[dict[str, Any]] = []
    rows = list(scopes.values())
    normalized_priority_filter = str(priority or "").strip().lower() or None
    normalized_role_filter = str(role or "").strip().lower() or None
    normalized_affinity_filter = str(server_affinity or "").strip().lower() or None
    normalized_deadline_state_filter = str(deadline_state or "").strip().lower() or None

    for row in rows:
        row["deadline_state"] = _resolve_deadline_state(
            deadline_at=row.get("deadline_at"),
            latest_status=str(row.get("_latest_job_status") or ""),
            latest_finished_at=row.get("_latest_job_finished_at"),
            now=now,
        )
        if normalized_priority_filter and str(row.get("priority") or "").lower() != normalized_priority_filter:
            continue
        if normalized_role_filter and str(row.get("role") or "").lower() != normalized_role_filter:
            continue
        if normalized_affinity_filter and str(row.get("server_affinity") or "").lower() != normalized_affinity_filter:
            continue
        if normalized_deadline_state_filter and str(row.get("deadline_state") or "").lower() != normalized_deadline_state_filter:
            continue

        row.pop("_latest_job_updated_at", None)
        row.pop("_latest_job_finished_at", None)
        row.pop("_latest_job_status", None)
        filtered_rows.append(row)

    filtered_rows.sort(key=lambda item: (str(item["database_id"]), str(item["entity_type"])))
    return filtered_rows


def _empty_scope_row(*, tenant_id: str, database_id: str, entity_type: str) -> dict[str, Any]:
    return {
        "tenant_id": str(tenant_id),
        "database_id": str(database_id),
        "entity_type": str(entity_type),
        "checkpoint_token": "",
        "pending_checkpoint_token": "",
        "checkpoint_status": "",
        "pending_count": 0,
        "retry_count": 0,
        "conflict_pending_count": 0,
        "conflict_retrying_count": 0,
        "lag_seconds": 0,
        "last_success_at": None,
        "last_applied_at": None,
        "last_error_code": "",
        "last_error_reason": "",
        "priority": "",
        "role": "",
        "server_affinity": "",
        "deadline_at": "",
        "deadline_state": "none",
        "queue_states": {
            "queued": 0,
            "processing": 0,
            "retrying": 0,
            "failed": 0,
            "completed": 0,
        },
        "_latest_job_updated_at": None,
        "_latest_job_finished_at": None,
        "_latest_job_status": "",
    }


def _lag_seconds(*, now: datetime, current: int, candidate: datetime | None) -> int:
    if candidate is None:
        return int(current or 0)
    delta_seconds = int(max(0.0, (now - candidate).total_seconds()))
    if current <= 0:
        return delta_seconds
    return max(current, delta_seconds)


def _latest_dt(current: datetime | None, candidate: datetime | None) -> datetime | None:
    if current is None:
        return candidate
    if candidate is None:
        return current
    return current if current >= candidate else candidate


def _extract_scheduling_metadata(metadata: dict[str, Any]) -> dict[str, str]:
    payload = metadata if isinstance(metadata, dict) else {}
    return {
        "priority": str(payload.get("priority") or "").strip().lower(),
        "role": str(payload.get("role") or "").strip().lower(),
        "server_affinity": str(payload.get("server_affinity") or "").strip().lower(),
        "deadline_at": str(payload.get("deadline_at") or "").strip(),
    }


def _resolve_queue_state(
    *,
    sync_job: PoolMasterDataSyncJob,
    workflow_outbox_map: dict[str, dict[str, Any]],
) -> str:
    job_status = str(sync_job.status or "")
    operation_id = str(sync_job.operation_id) if sync_job.operation_id is not None else ""
    outbox_snapshot = workflow_outbox_map.get(operation_id, {})

    if job_status == PoolMasterDataSyncJobStatus.PENDING:
        dispatch_attempts = int(outbox_snapshot.get("dispatch_attempts") or 0)
        return "retrying" if dispatch_attempts > 0 else "queued"
    if job_status == PoolMasterDataSyncJobStatus.RUNNING:
        return "processing"
    if job_status == PoolMasterDataSyncJobStatus.FAILED:
        return "failed"
    return "completed"


def _resolve_deadline_state(
    *,
    deadline_at: str | None,
    latest_status: str,
    latest_finished_at: datetime | None,
    now: datetime,
) -> str:
    token = str(deadline_at or "").strip()
    if not token:
        return "none"
    parsed_deadline = _parse_rfc3339_utc(token)
    if parsed_deadline is None:
        return "none"

    normalized_status = str(latest_status or "").strip().lower()
    if normalized_status in {
        PoolMasterDataSyncJobStatus.SUCCEEDED,
        PoolMasterDataSyncJobStatus.CANCELED,
    }:
        if latest_finished_at is None:
            return "missed"
        return "met" if latest_finished_at <= parsed_deadline else "missed"
    if normalized_status == PoolMasterDataSyncJobStatus.FAILED:
        if latest_finished_at is None:
            return "missed"
        return "met" if latest_finished_at <= parsed_deadline else "missed"
    return "missed" if now > parsed_deadline else "pending"


def _parse_rfc3339_utc(value: str) -> datetime | None:
    token = str(value or "").strip()
    if not token or "T" not in token:
        return None
    normalized = token[:-1] + "+00:00" if token.endswith("Z") else token
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if timezone.is_naive(parsed):
        return None
    return parsed.astimezone(dt_timezone.utc)
