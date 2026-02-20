from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.utils import timezone

from apps.operations.models import BatchOperation
from apps.operations.services import OperationsService
from apps.templates.workflow.models import WorkflowExecution


DEFAULT_BACKFILL_SLA_SECONDS = 3600
DEFAULT_BACKFILL_CHUNK_SIZE = 500


@dataclass
class WorkflowRootProjectionBackfillStats:
    executions_scanned: int = 0
    executions_with_root: int = 0
    executions_missing_root: int = 0
    executions_repaired: int = 0
    executions_repair_failed: int = 0
    sla_evaluated: int = 0
    sla_breaches: int = 0
    max_lag_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "executions_scanned": self.executions_scanned,
            "executions_with_root": self.executions_with_root,
            "executions_missing_root": self.executions_missing_root,
            "executions_repaired": self.executions_repaired,
            "executions_repair_failed": self.executions_repair_failed,
            "sla_evaluated": self.sla_evaluated,
            "sla_breaches": self.sla_breaches,
            "max_lag_seconds": round(float(self.max_lag_seconds), 3),
        }


def _iter_execution_rows(*, chunk_size: int):
    queryset = (
        WorkflowExecution.objects.order_by("id")
        .values(
            "id",
            "status",
            "current_node_id",
            "trace_id",
            "error_message",
            "error_code",
            "error_details",
            "started_at",
            "completed_at",
        )
    )

    batch: list[dict[str, Any]] = []
    for row in queryset.iterator(chunk_size=chunk_size):
        batch.append(row)
        if len(batch) >= chunk_size:
            yield batch
            batch = []
    if batch:
        yield batch


def _resolve_reference_ts(*, row: dict[str, Any]) -> datetime | None:
    started_at = row.get("started_at")
    if started_at is not None:
        return started_at
    completed_at = row.get("completed_at")
    if completed_at is not None:
        return completed_at
    return None


def run_workflow_root_projection_backfill(
    *,
    sla_seconds: int = DEFAULT_BACKFILL_SLA_SECONDS,
    chunk_size: int = DEFAULT_BACKFILL_CHUNK_SIZE,
) -> WorkflowRootProjectionBackfillStats:
    normalized_sla_seconds = max(0, int(sla_seconds))
    normalized_chunk_size = max(1, int(chunk_size))

    stats = WorkflowRootProjectionBackfillStats()
    now = timezone.now()

    for rows in _iter_execution_rows(chunk_size=normalized_chunk_size):
        execution_ids = [str(row.get("id") or "") for row in rows]
        existing_root_ids = set(
            BatchOperation.objects.filter(id__in=execution_ids).values_list("id", flat=True)
        )

        for row in rows:
            execution_id = str(row.get("id") or "").strip()
            if not execution_id:
                continue

            stats.executions_scanned += 1
            if execution_id in existing_root_ids:
                stats.executions_with_root += 1
                continue

            stats.executions_missing_root += 1
            reference_ts = _resolve_reference_ts(row=row)
            if reference_ts is not None:
                lag_seconds = max((now - reference_ts).total_seconds(), 0.0)
                stats.sla_evaluated += 1
                if lag_seconds > stats.max_lag_seconds:
                    stats.max_lag_seconds = lag_seconds
                if lag_seconds > normalized_sla_seconds:
                    stats.sla_breaches += 1

            repaired = OperationsService.sync_workflow_root_operation_status(
                execution_id=execution_id,
                workflow_status=str(row.get("status") or ""),
                node_id=row.get("current_node_id"),
                trace_id=row.get("trace_id"),
                error_message=str(row.get("error_message") or ""),
                error_code=str(row.get("error_code") or ""),
                error_details=row.get("error_details"),
            )
            if repaired:
                stats.executions_repaired += 1
            else:
                stats.executions_repair_failed += 1

    return stats

