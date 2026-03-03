from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from time import sleep as default_sleep
from typing import Callable, Iterable

from django.utils import timezone
from apps.operations.prometheus_metrics import (
    record_pool_master_data_sync_reconcile_window_metrics,
)

from .master_data_sync_reconcile_scheduler import MasterDataSyncReconcileFanOutResult
from .models import (
    PoolMasterDataSyncDirection,
    PoolMasterDataSyncJob,
    PoolMasterDataSyncJobStatus,
)

_TERMINAL_STATUSES = frozenset(
    {
        PoolMasterDataSyncJobStatus.SUCCEEDED,
        PoolMasterDataSyncJobStatus.FAILED,
        PoolMasterDataSyncJobStatus.CANCELED,
    }
)


@dataclass(frozen=True)
class MasterDataSyncReconcileFanInResult:
    reconcile_window_id: str
    started_at: str
    deadline_at: str
    finished_at: str
    outcome: str
    deadline_state: str
    total_scopes: int
    scheduled: int
    skipped: int
    failed: int
    on_time_completed: int
    late_completed: int
    pending: int
    coverage_ratio: float
    on_time_scope_results: tuple[dict[str, str], ...]
    late_scope_results: tuple[dict[str, str], ...]
    pending_scope_results: tuple[dict[str, str], ...]

    def to_report(self) -> dict[str, object]:
        return {
            "schema_version": "pool_master_data_sync_reconcile_fanin.v1",
            "reconcile_window_id": self.reconcile_window_id,
            "started_at": self.started_at,
            "deadline_at": self.deadline_at,
            "finished_at": self.finished_at,
            "outcome": self.outcome,
            "deadline_state": self.deadline_state,
            "total_scopes": self.total_scopes,
            "scheduled": self.scheduled,
            "skipped": self.skipped,
            "failed": self.failed,
            "on_time_completed": self.on_time_completed,
            "late_completed": self.late_completed,
            "pending": self.pending,
            "coverage_ratio": self.coverage_ratio,
            "on_time_scope_results": [dict(item) for item in self.on_time_scope_results],
            "late_scope_results": [dict(item) for item in self.late_scope_results],
            "pending_scope_results": [dict(item) for item in self.pending_scope_results],
        }


def _format_rfc3339_utc(value: datetime) -> str:
    normalized = value.astimezone(dt_timezone.utc).replace(microsecond=0)
    return normalized.isoformat().replace("+00:00", "Z")


def _parse_rfc3339_utc(value: str) -> datetime:
    token = str(value or "").strip()
    if not token:
        raise ValueError("deadline_at is required")
    normalized = token[:-1] + "+00:00" if token.endswith("Z") else token
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:  # noqa: BLE001
        raise ValueError(f"Invalid RFC3339 timestamp '{value}'") from exc
    if timezone.is_naive(parsed):
        raise ValueError(f"Timestamp '{value}' must include UTC timezone")
    if parsed.utcoffset() != timedelta(0):
        raise ValueError(f"Timestamp '{value}' must use UTC timezone")
    return parsed.astimezone(dt_timezone.utc)


def _coerce_datetime_utc(value: datetime | None) -> datetime:
    current = value or timezone.now()
    if timezone.is_naive(current):
        return timezone.make_aware(current, dt_timezone.utc).astimezone(dt_timezone.utc)
    return current.astimezone(dt_timezone.utc)


def _scope_key(tenant_id: str, database_id: str, entity_type: str) -> tuple[str, str, str]:
    return (
        str(tenant_id or "").strip(),
        str(database_id or "").strip(),
        str(entity_type or "").strip(),
    )


def _scope_key_from_report(report: dict[str, str]) -> tuple[str, str, str] | None:
    tenant_id = str(report.get("tenant_id") or "").strip()
    database_id = str(report.get("database_id") or "").strip()
    entity_type = str(report.get("entity_type") or "").strip()
    if not tenant_id or not database_id or not entity_type:
        return None
    return _scope_key(tenant_id, database_id, entity_type)


def _scope_key_from_job(job: PoolMasterDataSyncJob) -> tuple[str, str, str]:
    return _scope_key(str(job.tenant_id), str(job.database_id), str(job.entity_type))


def _job_order_key(job: PoolMasterDataSyncJob) -> datetime:
    timestamp = getattr(job, "updated_at", None) or getattr(job, "created_at", None)
    return _coerce_datetime_utc(timestamp)


def _load_reconcile_window_jobs(reconcile_window_id: str) -> Iterable[PoolMasterDataSyncJob]:
    normalized_window_id = str(reconcile_window_id or "").strip()
    if not normalized_window_id:
        return ()

    rows = (
        PoolMasterDataSyncJob.objects.filter(direction=PoolMasterDataSyncDirection.BIDIRECTIONAL)
        .order_by("-updated_at", "-created_at")
    )
    selected: list[PoolMasterDataSyncJob] = []
    for job in rows:
        metadata = job.metadata if isinstance(job.metadata, dict) else {}
        last_trigger = metadata.get("last_trigger")
        if not isinstance(last_trigger, dict):
            continue
        if str(last_trigger.get("reconcile_window_id") or "").strip() != normalized_window_id:
            continue
        selected.append(job)
    return selected


def _build_latest_job_map(jobs: Iterable[PoolMasterDataSyncJob]) -> dict[tuple[str, str, str], PoolMasterDataSyncJob]:
    by_scope: dict[tuple[str, str, str], PoolMasterDataSyncJob] = {}
    for job in jobs:
        key = _scope_key_from_job(job)
        previous = by_scope.get(key)
        if previous is None or _job_order_key(job) > _job_order_key(previous):
            by_scope[key] = job
    return by_scope


def _build_scope_result(
    *,
    key: tuple[str, str, str],
    sync_job_id: str,
    job_status: str,
    deadline_state: str,
    finished_at: datetime | None = None,
    detail: str = "",
) -> dict[str, str]:
    result = {
        "tenant_id": key[0],
        "database_id": key[1],
        "entity_type": key[2],
        "sync_job_id": sync_job_id,
        "job_status": job_status,
        "deadline_state": deadline_state,
    }
    if finished_at is not None:
        result["finished_at"] = _format_rfc3339_utc(finished_at)
    if detail:
        result["detail"] = detail
    return result


def aggregate_pool_master_data_reconcile_window(
    *,
    fanout_result: MasterDataSyncReconcileFanOutResult,
    poll_interval_seconds: float = 1.0,
    now_fn: Callable[[], datetime] | None = None,
    sleep_fn: Callable[[float], None] | None = None,
    jobs_loader: Callable[[str], Iterable[PoolMasterDataSyncJob]] | None = None,
) -> MasterDataSyncReconcileFanInResult:
    normalized_window_id = str(fanout_result.reconcile_window_id or "").strip()
    if not normalized_window_id:
        raise ValueError("reconcile_window_id is required")

    deadline_at_dt = _parse_rfc3339_utc(fanout_result.deadline_at)
    now_impl = now_fn or timezone.now
    sleep_impl = sleep_fn or default_sleep
    load_jobs = jobs_loader or _load_reconcile_window_jobs
    poll_interval = max(float(poll_interval_seconds), 0.0)

    scheduled_scope_reports = [
        dict(scope_report)
        for scope_report in fanout_result.scope_results
        if str(scope_report.get("status") or "").strip().lower() == "scheduled"
    ]
    scheduled_scope_keys = {
        key
        for key in (_scope_key_from_report(report) for report in scheduled_scope_reports)
        if key is not None
    }

    on_time_scope_results: list[dict[str, str]] = []
    late_scope_results: list[dict[str, str]] = []
    pending_scope_results: list[dict[str, str]] = []

    while True:
        jobs = list(load_jobs(normalized_window_id))
        latest_jobs_by_scope = _build_latest_job_map(jobs)

        on_time_scope_results = []
        late_scope_results = []
        pending_scope_results = []

        for scope_key in sorted(scheduled_scope_keys):
            sync_job = latest_jobs_by_scope.get(scope_key)
            if sync_job is None:
                pending_scope_results.append(
                    _build_scope_result(
                        key=scope_key,
                        sync_job_id="",
                        job_status="missing",
                        deadline_state="pending",
                        detail="No reconcile probe execution found for scheduled scope.",
                    )
                )
                continue

            finished_at_dt = _coerce_datetime_utc(
                getattr(sync_job, "finished_at", None) or getattr(sync_job, "updated_at", None)
            )
            sync_job_status = str(sync_job.status or "").strip().lower() or "unknown"
            sync_job_id = str(sync_job.id)

            if sync_job_status in _TERMINAL_STATUSES:
                if finished_at_dt <= deadline_at_dt:
                    on_time_scope_results.append(
                        _build_scope_result(
                            key=scope_key,
                            sync_job_id=sync_job_id,
                            job_status=sync_job_status,
                            deadline_state="met",
                            finished_at=finished_at_dt,
                        )
                    )
                else:
                    late_scope_results.append(
                        _build_scope_result(
                            key=scope_key,
                            sync_job_id=sync_job_id,
                            job_status=sync_job_status,
                            deadline_state="missed",
                            finished_at=finished_at_dt,
                            detail="Probe finished after reconcile window deadline.",
                        )
                    )
                continue

            pending_scope_results.append(
                _build_scope_result(
                    key=scope_key,
                    sync_job_id=sync_job_id,
                    job_status=sync_job_status,
                    deadline_state="pending",
                    detail="Probe is not in terminal status yet.",
                )
            )

        now_dt = _coerce_datetime_utc(now_impl())
        if not pending_scope_results or now_dt >= deadline_at_dt:
            break

        remaining = (deadline_at_dt - now_dt).total_seconds()
        if remaining <= 0:
            break
        sleep_seconds = min(poll_interval, remaining)
        if sleep_seconds <= 0:
            break
        sleep_impl(sleep_seconds)

    finished_at_dt = _coerce_datetime_utc(now_impl())
    deadline_state = "missed" if pending_scope_results or late_scope_results else "met"
    outcome = (
        "completed"
        if not pending_scope_results
        and not late_scope_results
        and int(fanout_result.failed) == 0
        and int(fanout_result.skipped) == 0
        else "partial"
    )
    scheduled_total = int(fanout_result.scheduled)
    if scheduled_total <= 0:
        coverage_ratio = 1.0
    else:
        coverage_ratio = len(on_time_scope_results) / float(scheduled_total)

    try:
        started_at_dt = _parse_rfc3339_utc(str(fanout_result.started_at))
    except ValueError:
        started_at_dt = _coerce_datetime_utc(now_impl())
    latency_seconds = max((finished_at_dt - started_at_dt).total_seconds(), 0.0)
    record_pool_master_data_sync_reconcile_window_metrics(
        coverage_ratio=coverage_ratio,
        deadline_state=deadline_state,
        outcome=outcome,
        latency_seconds=latency_seconds,
    )

    return MasterDataSyncReconcileFanInResult(
        reconcile_window_id=normalized_window_id,
        started_at=str(fanout_result.started_at),
        deadline_at=str(fanout_result.deadline_at),
        finished_at=_format_rfc3339_utc(finished_at_dt),
        outcome=outcome,
        deadline_state=deadline_state,
        total_scopes=int(fanout_result.total_scopes),
        scheduled=scheduled_total,
        skipped=int(fanout_result.skipped),
        failed=int(fanout_result.failed),
        on_time_completed=len(on_time_scope_results),
        late_completed=len(late_scope_results),
        pending=len(pending_scope_results),
        coverage_ratio=coverage_ratio,
        on_time_scope_results=tuple(on_time_scope_results),
        late_scope_results=tuple(late_scope_results),
        pending_scope_results=tuple(pending_scope_results),
    )


__all__ = [
    "MasterDataSyncReconcileFanInResult",
    "aggregate_pool_master_data_reconcile_window",
]
