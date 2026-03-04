from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta, timezone as dt_timezone
from typing import Any

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.operations.events import event_publisher
from apps.operations.models import WorkflowEnqueueOutbox
from apps.operations.services import OperationsService
from apps.operations.workflow_root_projection_backfill import (
    DEFAULT_BACKFILL_CHUNK_SIZE,
    DEFAULT_BACKFILL_SLA_SECONDS,
    run_workflow_root_projection_backfill,
)


DEFAULT_STUCK_OUTBOX_AGE_SECONDS = 300
DEFAULT_STUCK_OUTBOX_RETRY_SATURATION_ATTEMPTS = 5
DEFAULT_REPAIR_RELAY_BATCH_SIZE = 200
DEFAULT_DIAGNOSTIC_SAMPLE_LIMIT = 20
OUTBOX_REPAIR_FAILED_ERROR_CODE = "WORKFLOW_ENQUEUE_STUCK_OUTBOX_FAILED"
OUTBOX_REPAIR_FAILED_EVENT_CODE = "WORKFLOW_ENQUEUE_OUTBOX_TERMINAL_FAILED"


@dataclass(frozen=True)
class WorkflowEnqueueRepairReport:
    generated_at_utc: str
    status: str
    stuck_outbox_candidates_before: int
    stuck_outbox_candidates_after: int
    relay_claimed: int
    relay_dispatched: int
    relay_failed: int
    terminal_failed: int
    diagnostic_events_published: int
    root_missing_before: int
    root_repaired: int
    root_repair_failed: int
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "workflow_enqueue_repair.v1",
            "generated_at_utc": self.generated_at_utc,
            "status": self.status,
            "stuck_outbox_candidates_before": self.stuck_outbox_candidates_before,
            "stuck_outbox_candidates_after": self.stuck_outbox_candidates_after,
            "relay": {
                "claimed": self.relay_claimed,
                "dispatched": self.relay_dispatched,
                "failed": self.relay_failed,
            },
            "terminal_failed": {
                "count": self.terminal_failed,
                "diagnostic_events_published": self.diagnostic_events_published,
            },
            "root_projection_backfill": {
                "missing_before": self.root_missing_before,
                "repaired": self.root_repaired,
                "repair_failed": self.root_repair_failed,
            },
            "diagnostics": self.diagnostics,
        }


def _build_stuck_outbox_queryset(
    *,
    now,
    stuck_age_seconds: int,
    retry_saturation_attempts: int,
    require_due_retry: bool = True,
) -> QuerySet[WorkflowEnqueueOutbox]:
    age_threshold = now - timedelta(seconds=max(1, int(stuck_age_seconds)))
    retry_threshold = max(1, int(retry_saturation_attempts))
    queryset = WorkflowEnqueueOutbox.objects.filter(
        status=WorkflowEnqueueOutbox.STATUS_PENDING,
    )
    if require_due_retry:
        queryset = queryset.filter(next_retry_at__lte=now)
    return queryset.filter(
        Q(dispatch_attempts__gte=retry_threshold) | Q(created_at__lte=age_threshold)
    )


def _sample_outbox_rows(
    queryset: QuerySet[WorkflowEnqueueOutbox],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    rows = (
        queryset.order_by("next_retry_at", "id")
        .values(
            "id",
            "operation_id",
            "dispatch_attempts",
            "next_retry_at",
            "last_error_code",
            "last_error",
            "created_at",
        )[: max(1, int(limit))]
    )
    diagnostics: list[dict[str, Any]] = []
    for row in rows:
        diagnostics.append(
            {
                "outbox_id": int(row["id"]),
                "operation_id": str(row["operation_id"] or ""),
                "dispatch_attempts": int(row["dispatch_attempts"] or 0),
                "next_retry_at": row["next_retry_at"].isoformat() if row.get("next_retry_at") else None,
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                "last_error_code": str(row.get("last_error_code") or ""),
                "last_error": str(row.get("last_error") or ""),
            }
        )
    return diagnostics


def _mark_stuck_outbox_entries_as_failed(
    queryset: QuerySet[WorkflowEnqueueOutbox],
    *,
    now,
    sample_limit: int,
) -> tuple[int, int, list[dict[str, Any]]]:
    pending_ids = list(queryset.order_by("next_retry_at", "id").values_list("id", flat=True))
    if not pending_ids:
        return 0, 0, []

    failed_rows: list[dict[str, Any]] = []
    diagnostic_events_published = 0

    for outbox_id in pending_ids:
        with transaction.atomic():
            outbox = (
                WorkflowEnqueueOutbox.objects.select_for_update()
                .filter(id=outbox_id, status=WorkflowEnqueueOutbox.STATUS_PENDING)
                .first()
            )
            if outbox is None:
                continue

            operation_id = str(outbox.operation_id or "")
            failure_reason = (
                f"Workflow enqueue outbox marked as failed by detect+repair after "
                f"{int(outbox.dispatch_attempts or 0)} attempts."
            )

            outbox.status = WorkflowEnqueueOutbox.STATUS_FAILED
            outbox.last_error_code = OUTBOX_REPAIR_FAILED_ERROR_CODE
            outbox.last_error = failure_reason[:4000]
            outbox.next_retry_at = now
            outbox.save(
                update_fields=[
                    "status",
                    "last_error_code",
                    "last_error",
                    "next_retry_at",
                    "updated_at",
                ]
            )

            event_publisher.publish(
                operation_id=operation_id,
                state="FAILED",
                microservice="orchestrator",
                message="workflow enqueue outbox entry moved to terminal failed state by detect+repair",
                workflow_execution_id=operation_id,
                queue=str(outbox.stream_name or "commands:worker:workflows"),
                error_code=OUTBOX_REPAIR_FAILED_ERROR_CODE,
                error=failure_reason,
                diagnostic_code=OUTBOX_REPAIR_FAILED_EVENT_CODE,
                diagnostic_source="workflow_enqueue_repair",
                outbox_id=int(outbox.id),
                dispatch_attempts=int(outbox.dispatch_attempts or 0),
            )
            diagnostic_events_published += 1

            if len(failed_rows) < sample_limit:
                failed_rows.append(
                    {
                        "outbox_id": int(outbox.id),
                        "operation_id": operation_id,
                        "status": WorkflowEnqueueOutbox.STATUS_FAILED,
                        "dispatch_attempts": int(outbox.dispatch_attempts or 0),
                        "last_error_code": str(outbox.last_error_code or ""),
                        "last_error": str(outbox.last_error or ""),
                    }
                )

    return len(pending_ids), diagnostic_events_published, failed_rows


def run_workflow_enqueue_detect_repair(
    *,
    relay_batch_size: int = DEFAULT_REPAIR_RELAY_BATCH_SIZE,
    stuck_age_seconds: int = DEFAULT_STUCK_OUTBOX_AGE_SECONDS,
    retry_saturation_attempts: int = DEFAULT_STUCK_OUTBOX_RETRY_SATURATION_ATTEMPTS,
    root_backfill_sla_seconds: int = DEFAULT_BACKFILL_SLA_SECONDS,
    root_backfill_chunk_size: int = DEFAULT_BACKFILL_CHUNK_SIZE,
    diagnostic_sample_limit: int = DEFAULT_DIAGNOSTIC_SAMPLE_LIMIT,
) -> WorkflowEnqueueRepairReport:
    now = timezone.now()
    sample_limit = max(1, int(diagnostic_sample_limit))

    stuck_before_qs = _build_stuck_outbox_queryset(
        now=now,
        stuck_age_seconds=stuck_age_seconds,
        retry_saturation_attempts=retry_saturation_attempts,
        require_due_retry=True,
    )
    stuck_before_count = stuck_before_qs.count()
    stuck_before_sample = _sample_outbox_rows(stuck_before_qs, limit=sample_limit)

    relay_stats = OperationsService.dispatch_pending_workflow_enqueue_outbox(
        batch_size=max(1, int(relay_batch_size)),
        now=now,
    )

    stuck_after_qs = _build_stuck_outbox_queryset(
        now=timezone.now(),
        stuck_age_seconds=stuck_age_seconds,
        retry_saturation_attempts=retry_saturation_attempts,
        require_due_retry=False,
    )
    stuck_after_sample = _sample_outbox_rows(stuck_after_qs, limit=sample_limit)
    terminal_failed, diagnostic_events_published, terminal_failed_sample = _mark_stuck_outbox_entries_as_failed(
        stuck_after_qs,
        now=timezone.now(),
        sample_limit=sample_limit,
    )

    stuck_after_count = _build_stuck_outbox_queryset(
        now=timezone.now(),
        stuck_age_seconds=stuck_age_seconds,
        retry_saturation_attempts=retry_saturation_attempts,
        require_due_retry=False,
    ).count()

    root_backfill_stats = run_workflow_root_projection_backfill(
        sla_seconds=max(0, int(root_backfill_sla_seconds)),
        chunk_size=max(1, int(root_backfill_chunk_size)),
    )

    diagnostics = {
        "stuck_outbox_before": stuck_before_sample,
        "stuck_outbox_after": stuck_after_sample,
        "terminal_failed_outbox": terminal_failed_sample,
        "root_backfill": root_backfill_stats.to_dict(),
    }

    status = "ok"
    if (
        stuck_after_count > 0
        or terminal_failed > 0
        or int(root_backfill_stats.executions_repair_failed) > 0
        or int(relay_stats.get("failed") or 0) > 0
    ):
        status = "needs_follow_up"

    return WorkflowEnqueueRepairReport(
        generated_at_utc=now.astimezone(dt_timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        status=status,
        stuck_outbox_candidates_before=stuck_before_count,
        stuck_outbox_candidates_after=stuck_after_count,
        relay_claimed=int(relay_stats.get("claimed") or 0),
        relay_dispatched=int(relay_stats.get("dispatched") or 0),
        relay_failed=int(relay_stats.get("failed") or 0),
        terminal_failed=terminal_failed,
        diagnostic_events_published=diagnostic_events_published,
        root_missing_before=int(root_backfill_stats.executions_missing_root),
        root_repaired=int(root_backfill_stats.executions_repaired),
        root_repair_failed=int(root_backfill_stats.executions_repair_failed),
        diagnostics=diagnostics,
    )
