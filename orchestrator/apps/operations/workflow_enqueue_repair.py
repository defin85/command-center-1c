from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta, timezone as dt_timezone
from typing import Any

from django.db.models import Q, QuerySet
from django.utils import timezone

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


@dataclass(frozen=True)
class WorkflowEnqueueRepairReport:
    generated_at_utc: str
    status: str
    stuck_outbox_candidates_before: int
    stuck_outbox_candidates_after: int
    relay_claimed: int
    relay_dispatched: int
    relay_failed: int
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
) -> QuerySet[WorkflowEnqueueOutbox]:
    age_threshold = now - timedelta(seconds=max(1, int(stuck_age_seconds)))
    retry_threshold = max(1, int(retry_saturation_attempts))
    return WorkflowEnqueueOutbox.objects.filter(
        status=WorkflowEnqueueOutbox.STATUS_PENDING,
        next_retry_at__lte=now,
    ).filter(
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
    )
    stuck_after_count = stuck_after_qs.count()
    stuck_after_sample = _sample_outbox_rows(stuck_after_qs, limit=sample_limit)

    root_backfill_stats = run_workflow_root_projection_backfill(
        sla_seconds=max(0, int(root_backfill_sla_seconds)),
        chunk_size=max(1, int(root_backfill_chunk_size)),
    )

    diagnostics = {
        "stuck_outbox_before": stuck_before_sample,
        "stuck_outbox_after": stuck_after_sample,
        "root_backfill": root_backfill_stats.to_dict(),
    }

    status = "ok"
    if (
        stuck_after_count > 0
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
        root_missing_before=int(root_backfill_stats.executions_missing_root),
        root_repaired=int(root_backfill_stats.executions_repaired),
        root_repair_failed=int(root_backfill_stats.executions_repair_failed),
        diagnostics=diagnostics,
    )
