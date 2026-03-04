from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta, timezone as dt_timezone
import math
from time import sleep as default_sleep
from typing import Callable, Mapping
from uuid import uuid4

from django.utils import timezone

from apps.operations.services import OperationsService

from .master_data_sync_execution import (
    PoolMasterDataSyncTriggerResult,
    trigger_pool_master_data_reconcile_sync_job,
)
from .models import PoolMasterDataSyncScope

RECONCILE_BACKPRESSURE_ACTIVE = "RECONCILE_BACKPRESSURE_ACTIVE"
RECONCILE_BACKPRESSURE_EXHAUSTED = "RECONCILE_BACKPRESSURE_EXHAUSTED"
RECONCILE_PROBE_ENQUEUE_FAILED = "RECONCILE_PROBE_ENQUEUE_FAILED"

_NON_RETRYABLE_ERROR_CODES = frozenset(
    {
        "SERVER_AFFINITY_UNRESOLVED",
        "SCHEDULING_CONTRACT_INVALID",
        "SCHEDULING_DEADLINE_INVALID",
        "MASTER_DATA_SYNC_DISABLED",
        "MASTER_DATA_SYNC_INBOUND_DISABLED",
        "MASTER_DATA_SYNC_OUTBOUND_DISABLED",
    }
)
_RETRYABLE_ERROR_CODE_HINTS = (
    "ENQUEUE_FAILED",
    "REDIS",
    "TIMEOUT",
    "OVERLOAD",
    "BACKPRESSURE",
    "THROTTLE",
    "RATE_LIMIT",
    "UNAVAILABLE",
)
_WORKFLOW_QUEUE_STREAM = "commands:worker:workflows"


@dataclass(frozen=True)
class MasterDataSyncReconcileFanOutResult:
    reconcile_window_id: str
    started_at: str
    deadline_at: str
    total_scopes: int
    scheduled: int
    skipped: int
    failed: int
    scope_results: tuple[dict[str, str], ...]

    def to_report(self) -> dict[str, object]:
        return {
            "schema_version": "pool_master_data_sync_reconcile_fanout.v1",
            "reconcile_window_id": self.reconcile_window_id,
            "started_at": self.started_at,
            "deadline_at": self.deadline_at,
            "total_scopes": self.total_scopes,
            "scheduled": self.scheduled,
            "skipped": self.skipped,
            "failed": self.failed,
            "scope_results": [dict(item) for item in self.scope_results],
        }


def _format_rfc3339_utc(value) -> str:
    return value.astimezone(dt_timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _is_retryable_failure(*, error_code: str, detail: str) -> bool:
    code_token = str(error_code or "").strip().upper()
    detail_token = str(detail or "").strip().upper()
    if code_token in _NON_RETRYABLE_ERROR_CODES:
        return False
    for hint in _RETRYABLE_ERROR_CODE_HINTS:
        if hint in code_token or hint in detail_token:
            return True
    return False


def _extract_failed_result_error(result: PoolMasterDataSyncTriggerResult) -> tuple[str, str]:
    sync_job = getattr(result, "sync_job", None)
    start_result = getattr(result, "start_result", None)
    error_code = str(getattr(sync_job, "last_error_code", "") or "").strip()
    if not error_code and start_result is not None:
        start_sync_job = getattr(start_result, "sync_job", None)
        error_code = str(getattr(start_sync_job, "last_error_code", "") or "").strip()

    detail = str(getattr(start_result, "enqueue_error", "") or "").strip()
    if not detail:
        detail = str(getattr(sync_job, "last_error", "") or "").strip()

    normalized_error_code = error_code or RECONCILE_PROBE_ENQUEUE_FAILED
    normalized_detail = detail or normalized_error_code
    return normalized_error_code, normalized_detail


def _compute_retry_backoff_seconds(
    *,
    retry_number: int,
    base_backoff_seconds: float,
    max_backoff_seconds: float,
) -> float:
    base_delay = max(float(base_backoff_seconds), 0.0)
    if base_delay <= 0:
        return 0.0
    ceiling = max(float(max_backoff_seconds), base_delay)
    exponent = max(int(retry_number) - 1, 0)
    return min(ceiling, base_delay * math.pow(2.0, exponent))


def _default_queue_depth_provider() -> int | None:
    try:
        return int(OperationsService.get_queue_depth(queue_name=_WORKFLOW_QUEUE_STREAM))
    except Exception:  # noqa: BLE001
        return None


def _with_retry_metadata(
    report: Mapping[str, str],
    *,
    attempts: int,
    retry_attempts: int,
    backpressure_retries: int,
) -> dict[str, str]:
    enriched = dict(report)
    enriched["attempts"] = str(max(1, int(attempts)))
    enriched["retry_attempts"] = str(max(0, int(retry_attempts)))
    enriched["backpressure_retries"] = str(max(0, int(backpressure_retries)))
    return enriched


def schedule_pool_master_data_reconcile_probe_jobs(
    *,
    tenant_id: str | None = None,
    batch_size: int = 720,
    window_seconds: int = 120,
    origin_system: str = "reconcile_scheduler",
    origin_event_id: str | None = None,
    correlation_prefix: str = "corr-reconcile",
    trigger_reconcile: Callable[..., PoolMasterDataSyncTriggerResult] | None = None,
    max_enqueue_attempts: int = 3,
    retry_base_backoff_seconds: float = 0.25,
    retry_max_backoff_seconds: float = 2.0,
    backpressure_queue_depth_limit: int = 0,
    queue_depth_provider: Callable[[], int | None] | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> MasterDataSyncReconcileFanOutResult:
    trigger = trigger_reconcile or trigger_pool_master_data_reconcile_sync_job
    normalized_tenant_id = str(tenant_id or "").strip() or None
    normalized_batch_size = max(1, int(batch_size))
    normalized_window_seconds = max(1, int(window_seconds))
    normalized_origin_event_id = str(origin_event_id or "").strip() or f"evt-{uuid4()}"
    normalized_max_enqueue_attempts = max(1, int(max_enqueue_attempts))
    normalized_retry_base_backoff_seconds = max(float(retry_base_backoff_seconds), 0.0)
    normalized_retry_max_backoff_seconds = max(
        float(retry_max_backoff_seconds),
        normalized_retry_base_backoff_seconds,
    )
    normalized_queue_depth_limit = max(0, int(backpressure_queue_depth_limit))
    read_queue_depth = queue_depth_provider or _default_queue_depth_provider
    sleep_fn_impl = sleep_fn or default_sleep

    started_at_dt = timezone.now().astimezone(dt_timezone.utc)
    deadline_at_dt = started_at_dt + timedelta(seconds=normalized_window_seconds)
    started_at = _format_rfc3339_utc(started_at_dt)
    deadline_at = _format_rfc3339_utc(deadline_at_dt)
    reconcile_window_id = f"reconcile-window-{uuid4()}"

    queryset = PoolMasterDataSyncScope.objects.filter(database_id__isnull=False)
    if normalized_tenant_id is not None:
        queryset = queryset.filter(tenant_id=normalized_tenant_id)
    scopes = list(
        queryset.order_by("tenant_id", "database_id", "entity_type", "id")[:normalized_batch_size]
    )

    scheduled = 0
    skipped = 0
    failed = 0
    scope_results: list[dict[str, str]] = []

    for index, scope in enumerate(scopes, start=1):
        correlation_id = f"{correlation_prefix}:{reconcile_window_id}:{index}"
        base_scope_report: dict[str, str] = {
            "tenant_id": str(scope.tenant_id),
            "database_id": str(scope.database_id),
            "entity_type": str(scope.entity_type),
        }
        attempts = 0
        backpressure_retries = 0
        last_failure_report: dict[str, str] | None = None

        while attempts < normalized_max_enqueue_attempts:
            attempts += 1

            if normalized_queue_depth_limit > 0:
                queue_depth = read_queue_depth()
                if queue_depth is not None and queue_depth >= normalized_queue_depth_limit:
                    backpressure_retries += 1
                    last_failure_report = {
                        **base_scope_report,
                        "status": "retrying",
                        "error_code": RECONCILE_BACKPRESSURE_ACTIVE,
                        "detail": (
                            "Queue depth exceeded backpressure limit "
                            f"({queue_depth} >= {normalized_queue_depth_limit})."
                        ),
                        "queue_depth": str(queue_depth),
                    }
                    if attempts < normalized_max_enqueue_attempts:
                        delay = _compute_retry_backoff_seconds(
                            retry_number=attempts,
                            base_backoff_seconds=normalized_retry_base_backoff_seconds,
                            max_backoff_seconds=normalized_retry_max_backoff_seconds,
                        )
                        if delay > 0:
                            sleep_fn_impl(delay)
                        continue
                    failed += 1
                    failed_report = dict(last_failure_report)
                    failed_report["status"] = "failed"
                    failed_report["error_code"] = RECONCILE_BACKPRESSURE_EXHAUSTED
                    failed_report = _with_retry_metadata(
                        failed_report,
                        attempts=attempts,
                        retry_attempts=attempts - 1,
                        backpressure_retries=backpressure_retries,
                    )
                    scope_results.append(failed_report)
                    break

            try:
                result = trigger(
                    tenant_id=str(scope.tenant_id),
                    database_id=str(scope.database_id),
                    entity_type=str(scope.entity_type),
                    origin_system=origin_system,
                    origin_event_id=normalized_origin_event_id,
                    correlation_id=correlation_id,
                    reconcile_window_id=reconcile_window_id,
                    reconcile_window_deadline_at=deadline_at,
                )
            except Exception as exc:  # noqa: BLE001
                error_code = str(getattr(exc, "code", "RECONCILE_PROBE_SCHEDULE_FAILED"))
                detail = str(exc or error_code)
                retryable = _is_retryable_failure(error_code=error_code, detail=detail)
                last_failure_report = {
                    **base_scope_report,
                    "status": "retrying" if retryable else "failed",
                    "error_code": error_code,
                    "detail": detail,
                }
                if retryable and attempts < normalized_max_enqueue_attempts:
                    delay = _compute_retry_backoff_seconds(
                        retry_number=attempts,
                        base_backoff_seconds=normalized_retry_base_backoff_seconds,
                        max_backoff_seconds=normalized_retry_max_backoff_seconds,
                    )
                    if delay > 0:
                        sleep_fn_impl(delay)
                    continue
                failed += 1
                failed_report = _with_retry_metadata(
                    {
                        **base_scope_report,
                        "status": "failed",
                        "error_code": error_code,
                        "detail": detail,
                    },
                    attempts=attempts,
                    retry_attempts=attempts - 1,
                    backpressure_retries=backpressure_retries,
                )
                scope_results.append(failed_report)
                break

            sync_job_id = str(getattr(result.sync_job, "id", "") or "")
            if result.started_workflow:
                scheduled += 1
                success_report = _with_retry_metadata(
                    {
                        **base_scope_report,
                        "status": "scheduled",
                        **({"sync_job_id": sync_job_id} if sync_job_id else {}),
                    },
                    attempts=attempts,
                    retry_attempts=attempts - 1,
                    backpressure_retries=backpressure_retries,
                )
                scope_results.append(success_report)
                break

            if result.skipped:
                skipped += 1
                skipped_report = _with_retry_metadata(
                    {
                        **base_scope_report,
                        "status": "skipped",
                        "skip_reason": str(result.skip_reason or ""),
                        **({"sync_job_id": sync_job_id} if sync_job_id else {}),
                    },
                    attempts=attempts,
                    retry_attempts=attempts - 1,
                    backpressure_retries=backpressure_retries,
                )
                scope_results.append(skipped_report)
                break

            error_code, detail = _extract_failed_result_error(result)
            retryable = _is_retryable_failure(error_code=error_code, detail=detail)
            if retryable and attempts < normalized_max_enqueue_attempts:
                last_failure_report = {
                    **base_scope_report,
                    "status": "retrying",
                    "error_code": error_code,
                    "detail": detail,
                    **({"sync_job_id": sync_job_id} if sync_job_id else {}),
                }
                delay = _compute_retry_backoff_seconds(
                    retry_number=attempts,
                    base_backoff_seconds=normalized_retry_base_backoff_seconds,
                    max_backoff_seconds=normalized_retry_max_backoff_seconds,
                )
                if delay > 0:
                    sleep_fn_impl(delay)
                continue

            failed += 1
            failed_report = _with_retry_metadata(
                {
                    **base_scope_report,
                    "status": "failed",
                    "error_code": error_code,
                    "detail": detail,
                    **({"sync_job_id": sync_job_id} if sync_job_id else {}),
                },
                attempts=attempts,
                retry_attempts=attempts - 1,
                backpressure_retries=backpressure_retries,
            )
            scope_results.append(failed_report)
            break

        else:
            failed += 1
            fallback_report = _with_retry_metadata(
                {
                    **base_scope_report,
                    "status": "failed",
                    "error_code": RECONCILE_PROBE_ENQUEUE_FAILED,
                    "detail": "Retry budget exhausted before scheduling reconcile probe.",
                },
                attempts=attempts,
                retry_attempts=max(0, attempts - 1),
                backpressure_retries=backpressure_retries,
            )
            if last_failure_report:
                fallback_report.update(
                    {
                        "error_code": str(last_failure_report.get("error_code") or RECONCILE_PROBE_ENQUEUE_FAILED),
                        "detail": str(last_failure_report.get("detail") or fallback_report["detail"]),
                    }
                )
            scope_results.append(fallback_report)

    return MasterDataSyncReconcileFanOutResult(
        reconcile_window_id=reconcile_window_id,
        started_at=started_at,
        deadline_at=deadline_at,
        total_scopes=len(scopes),
        scheduled=scheduled,
        skipped=skipped,
        failed=failed,
        scope_results=tuple(scope_results),
    )


__all__ = [
    "RECONCILE_BACKPRESSURE_ACTIVE",
    "RECONCILE_BACKPRESSURE_EXHAUSTED",
    "MasterDataSyncReconcileFanOutResult",
    "schedule_pool_master_data_reconcile_probe_jobs",
]
