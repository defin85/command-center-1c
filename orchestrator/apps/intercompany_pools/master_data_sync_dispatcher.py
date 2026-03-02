from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Callable

from django.db import transaction
from django.utils import timezone

from .master_data_sync_apply import apply_master_data_outbox_to_ib
from .models import PoolMasterDataSyncOutbox, PoolMasterDataSyncOutboxStatus


DISPATCH_ERROR_UNEXPECTED = "MASTER_DATA_SYNC_DISPATCH_UNEXPECTED"


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
) -> MasterDataSyncDispatchBatchResult:
    if transport_apply is None:
        transport_apply = _build_transport_apply(ib_apply=ib_apply)

    now = timezone.now()
    row_ids = _claim_pending_outbox_rows(batch_size=max(1, int(batch_size)), now=now)
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

    return MasterDataSyncDispatchBatchResult(
        claimed=len(row_ids),
        sent=sent,
        failed=failed,
    )


def _build_transport_apply(
    *,
    ib_apply: Callable[[PoolMasterDataSyncOutbox], dict | None] | None,
) -> Callable[[PoolMasterDataSyncOutbox], dict | None]:
    if ib_apply is None:
        def _not_configured(_outbox: PoolMasterDataSyncOutbox) -> dict | None:
            raise MasterDataSyncTransportError(
                code="MASTER_DATA_SYNC_TRANSPORT_NOT_CONFIGURED",
                detail="IB apply transport is not configured for dispatcher",
            )

        ib_apply = _not_configured

    def _apply(outbox: PoolMasterDataSyncOutbox) -> dict | None:
        return apply_master_data_outbox_to_ib(outbox=outbox, ib_apply=ib_apply)

    return _apply


def _claim_pending_outbox_rows(*, batch_size: int, now) -> list[str]:
    with transaction.atomic():
        rows = list(
            PoolMasterDataSyncOutbox.objects.select_for_update(skip_locked=True)
            .filter(
                status__in=[
                    PoolMasterDataSyncOutboxStatus.PENDING,
                    PoolMasterDataSyncOutboxStatus.FAILED,
                ],
                available_at__lte=now,
            )
            .order_by("available_at", "created_at", "id")[:batch_size]
        )
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
        metadata["dispatch_result"] = dict(result_payload)
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
    row.last_error = str(error_message or "")
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
