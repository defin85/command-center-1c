from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Callable

from django.db import transaction
from django.utils import timezone

from apps.operations.prometheus_metrics import (
    set_pool_master_data_sync_backlog_metrics,
    set_pool_master_data_sync_conflict_metrics,
)

from .master_data_sync_apply import apply_master_data_outbox_to_ib
from .master_data_sync_redaction import (
    sanitize_master_data_sync_text,
    sanitize_master_data_sync_value,
)
from .models import (
    PoolMasterDataSyncConflict,
    PoolMasterDataSyncConflictStatus,
    PoolMasterDataSyncOutbox,
    PoolMasterDataSyncOutboxStatus,
)


DISPATCH_ERROR_UNEXPECTED = "MASTER_DATA_SYNC_DISPATCH_UNEXPECTED"
MASTER_DATA_SYNC_RETRY_SATURATION_THRESHOLD_ATTEMPTS = 5

logger = logging.getLogger(__name__)


class MasterDataSyncTransportError(RuntimeError):
    def __init__(self, *, code: str, detail: str) -> None:
        self.code = str(code or "").strip() or "MASTER_DATA_SYNC_TRANSPORT_ERROR"
        self.detail = str(detail or "").strip() or "master-data sync transport error"
        super().__init__(f"{self.code}: {self.detail}")


@dataclass(frozen=True)
class MasterDataSyncDispatchBatchResult:
    claimed: int
    sent: int
    failed: int


def dispatch_pending_master_data_sync_outbox(
    *,
    transport_apply: Callable[[PoolMasterDataSyncOutbox], dict | None] | None = None,
    ib_apply: Callable[[PoolMasterDataSyncOutbox], dict | None] | None = None,
    batch_size: int = 100,
    max_retry_backoff_seconds: int = 900,
    tenant_id: str | None = None,
    database_id: str | None = None,
    entity_type: str | None = None,
) -> MasterDataSyncDispatchBatchResult:
    if transport_apply is None:
        transport_apply = _build_transport_apply(ib_apply=ib_apply)

    now = timezone.now()
    row_ids = _claim_pending_outbox_rows(
        batch_size=max(1, int(batch_size)),
        now=now,
        tenant_id=str(tenant_id or "").strip() or None,
        database_id=str(database_id or "").strip() or None,
        entity_type=str(entity_type or "").strip() or None,
    )
    sent = 0
    failed = 0

    for row_id in row_ids:
        row = PoolMasterDataSyncOutbox.objects.get(id=row_id)
        try:
            result_payload = transport_apply(row)
        except MasterDataSyncTransportError as exc:
            _mark_failed(
                row_id=row.id,
                now=now,
                max_retry_backoff_seconds=max_retry_backoff_seconds,
                error_code=exc.code,
                error_message=exc.detail,
            )
            failed += 1
            continue
        except Exception as exc:  # noqa: BLE001
            _mark_failed(
                row_id=row.id,
                now=now,
                max_retry_backoff_seconds=max_retry_backoff_seconds,
                error_code=DISPATCH_ERROR_UNEXPECTED,
                error_message=str(exc),
            )
            failed += 1
            continue

        _mark_sent(row_id=row.id, now=now, result_payload=result_payload)
        sent += 1

    batch_result = MasterDataSyncDispatchBatchResult(
        claimed=len(row_ids),
        sent=sent,
        failed=failed,
    )
    _record_master_data_sync_sli_metrics(now=now)
    return batch_result


def _build_transport_apply(
    *,
    ib_apply: Callable[[PoolMasterDataSyncOutbox], dict | None] | None,
) -> Callable[[PoolMasterDataSyncOutbox], dict | None]:
    if ib_apply is None:
        from .master_data_sync_live_odata_transport import (
            MasterDataSyncLiveODataError,
            apply_outbox_to_live_odata,
        )

        def _default_live_odata_apply(outbox: PoolMasterDataSyncOutbox) -> dict | None:
            try:
                return apply_outbox_to_live_odata(outbox=outbox)
            except MasterDataSyncLiveODataError as exc:
                raise MasterDataSyncTransportError(code=exc.code, detail=exc.detail) from exc

        ib_apply = _default_live_odata_apply

    def _apply(outbox: PoolMasterDataSyncOutbox) -> dict | None:
        return apply_master_data_outbox_to_ib(outbox=outbox, ib_apply=ib_apply)

    return _apply


def _claim_pending_outbox_rows(
    *,
    batch_size: int,
    now,
    tenant_id: str | None = None,
    database_id: str | None = None,
    entity_type: str | None = None,
) -> list[str]:
    with transaction.atomic():
        queryset = PoolMasterDataSyncOutbox.objects.select_for_update(skip_locked=True).filter(
            status__in=[
                PoolMasterDataSyncOutboxStatus.PENDING,
                PoolMasterDataSyncOutboxStatus.FAILED,
            ],
            available_at__lte=now,
        )
        if tenant_id is not None:
            queryset = queryset.filter(tenant_id=tenant_id)
        if database_id is not None:
            queryset = queryset.filter(database_id=database_id)
        if entity_type is not None:
            queryset = queryset.filter(entity_type=entity_type)

        rows = list(queryset.order_by("available_at", "created_at", "id")[:batch_size])
        row_ids: list[str] = []
        for row in rows:
            row.status = PoolMasterDataSyncOutboxStatus.PROCESSING
            row.attempt_count = int(row.attempt_count or 0) + 1
            row.save(update_fields=["status", "attempt_count", "updated_at"])
            row_ids.append(str(row.id))
    return row_ids


def _mark_sent(*, row_id: str, now, result_payload: dict | None) -> None:
    row = PoolMasterDataSyncOutbox.objects.get(id=row_id)
    metadata = dict(row.metadata or {})
    if isinstance(result_payload, dict) and result_payload:
        metadata["dispatch_result"] = sanitize_master_data_sync_value(dict(result_payload))
    row.status = PoolMasterDataSyncOutboxStatus.SENT
    row.dispatched_at = now
    row.last_error_code = ""
    row.last_error = ""
    row.metadata = metadata
    row.save(
        update_fields=[
            "status",
            "dispatched_at",
            "last_error_code",
            "last_error",
            "metadata",
            "updated_at",
        ]
    )


def _mark_failed(
    *,
    row_id: str,
    now,
    max_retry_backoff_seconds: int,
    error_code: str,
    error_message: str,
) -> None:
    row = PoolMasterDataSyncOutbox.objects.get(id=row_id)
    attempt_count = max(1, int(row.attempt_count or 1))
    delay_seconds = min(
        2 ** max(0, attempt_count - 1),
        max(1, int(max_retry_backoff_seconds)),
    )
    row.status = PoolMasterDataSyncOutboxStatus.FAILED
    row.last_error_code = str(error_code or DISPATCH_ERROR_UNEXPECTED)
    row.last_error = sanitize_master_data_sync_text(error_message)
    row.available_at = now + timedelta(seconds=delay_seconds)
    row.save(
        update_fields=[
            "status",
            "last_error_code",
            "last_error",
            "available_at",
            "updated_at",
        ]
    )


def _record_master_data_sync_sli_metrics(*, now) -> None:
    try:
        backlog_queryset = PoolMasterDataSyncOutbox.objects.filter(
            status__in=[
                PoolMasterDataSyncOutboxStatus.PENDING,
                PoolMasterDataSyncOutboxStatus.FAILED,
            ]
        )
        pending_total = int(
            backlog_queryset.filter(status=PoolMasterDataSyncOutboxStatus.PENDING).count()
        )
        retry_total = int(
            backlog_queryset.filter(status=PoolMasterDataSyncOutboxStatus.FAILED).count()
        )
        saturated_total = int(
            backlog_queryset.filter(
                attempt_count__gte=MASTER_DATA_SYNC_RETRY_SATURATION_THRESHOLD_ATTEMPTS
            ).count()
        )
        oldest_available_at = (
            backlog_queryset.order_by("available_at").values_list("available_at", flat=True).first()
        )
        lag_seconds = 0.0
        if oldest_available_at is not None:
            lag_seconds = max((now - oldest_available_at).total_seconds(), 0.0)

        set_pool_master_data_sync_backlog_metrics(
            lag_seconds=lag_seconds,
            pending_total=pending_total,
            retry_total=retry_total,
            saturated_total=saturated_total,
        )

        conflict_pending_total = int(
            PoolMasterDataSyncConflict.objects.filter(
                status=PoolMasterDataSyncConflictStatus.PENDING
            ).count()
        )
        conflict_retrying_total = int(
            PoolMasterDataSyncConflict.objects.filter(
                status=PoolMasterDataSyncConflictStatus.RETRYING
            ).count()
        )
        set_pool_master_data_sync_conflict_metrics(
            pending_total=conflict_pending_total,
            retrying_total=conflict_retrying_total,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to record master-data sync SLI metrics: %s", exc)
