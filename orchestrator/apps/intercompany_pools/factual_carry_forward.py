from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import (
    PoolBatchSettlement,
    PoolBatchSettlementStatus,
    PoolFactualBalanceSnapshot,
)


@dataclass(frozen=True)
class FactualCarryForwardResult:
    source_snapshot: PoolFactualBalanceSnapshot
    target_snapshot: PoolFactualBalanceSnapshot
    settlement: PoolBatchSettlement | None
    created: bool


def materialize_factual_carry_forward(
    *,
    source_snapshot: PoolFactualBalanceSnapshot,
    applied_at: datetime | None = None,
) -> FactualCarryForwardResult | None:
    open_balance = Decimal(str(source_snapshot.open_balance or "0"))
    if open_balance <= Decimal("0"):
        return None

    timestamp = applied_at or timezone.now()
    next_quarter_start, next_quarter_end = resolve_next_quarter_window(
        quarter_start=source_snapshot.quarter_start
    )
    source_snapshot_id = str(source_snapshot.id)

    with transaction.atomic():
        locked_source = PoolFactualBalanceSnapshot.objects.select_for_update().get(id=source_snapshot.id)
        target_snapshot, created = PoolFactualBalanceSnapshot.objects.update_or_create(
            tenant=locked_source.tenant,
            pool=locked_source.pool,
            batch=locked_source.batch,
            organization=locked_source.organization,
            edge=locked_source.edge,
            quarter_start=next_quarter_start,
            quarter_end=next_quarter_end,
            defaults={
                "amount_with_vat": locked_source.amount_with_vat,
                "amount_without_vat": locked_source.amount_without_vat,
                "vat_amount": locked_source.vat_amount,
                "incoming_amount": locked_source.open_balance,
                "outgoing_amount": Decimal("0.00"),
                "open_balance": locked_source.open_balance,
                "freshness_at": locked_source.freshness_at,
                "metadata": {
                    **_carry_forward_target_metadata(
                        source_snapshot=locked_source,
                        applied_at=timestamp,
                    ),
                    **_preserve_non_carry_forward_metadata(locked_source.metadata),
                },
            },
        )

        source_metadata = _preserve_non_carry_forward_metadata(locked_source.metadata)
        source_metadata["carry_forward"] = {
            "target_snapshot_id": str(target_snapshot.id),
            "target_quarter_start": next_quarter_start.isoformat(),
            "target_quarter_end": next_quarter_end.isoformat(),
            "applied_at": timestamp.isoformat(),
        }
        locked_source.metadata = source_metadata
        locked_source.save(update_fields=["metadata", "updated_at"])

        settlement = None
        if locked_source.batch_id:
            settlement = (
                PoolBatchSettlement.objects.select_for_update()
                .filter(batch_id=locked_source.batch_id)
                .first()
            )
            if settlement is not None:
                settlement.status = PoolBatchSettlementStatus.CARRIED_FORWARD
                settlement.freshness_at = locked_source.freshness_at
                settlement.summary = {
                    **_preserve_non_carry_forward_metadata(settlement.summary),
                    "carry_forward": {
                        "source_snapshot_id": source_snapshot_id,
                        "target_snapshot_id": str(target_snapshot.id),
                        "target_quarter_start": next_quarter_start.isoformat(),
                        "target_quarter_end": next_quarter_end.isoformat(),
                        "applied_at": timestamp.isoformat(),
                    },
                }
                settlement.save(update_fields=["status", "freshness_at", "summary", "updated_at"])

    refreshed_target = PoolFactualBalanceSnapshot.objects.get(id=target_snapshot.id)
    refreshed_source = PoolFactualBalanceSnapshot.objects.get(id=source_snapshot.id)
    refreshed_settlement = None
    if settlement is not None:
        refreshed_settlement = PoolBatchSettlement.objects.get(id=settlement.id)
    return FactualCarryForwardResult(
        source_snapshot=refreshed_source,
        target_snapshot=refreshed_target,
        settlement=refreshed_settlement,
        created=created,
    )


def resolve_next_quarter_window(*, quarter_start: date) -> tuple[date, date]:
    quarter_index = (int(quarter_start.month) - 1) // 3
    next_year = int(quarter_start.year)
    next_quarter_index = quarter_index + 1
    if next_quarter_index >= 4:
        next_quarter_index = 0
        next_year += 1

    next_start_month = (next_quarter_index * 3) + 1
    next_quarter_start = date(next_year, next_start_month, 1)
    next_quarter_end = date(
        next_year,
        next_start_month + 2,
        _resolve_month_end_day(year=next_year, month=next_start_month + 2),
    )
    return next_quarter_start, next_quarter_end


def _carry_forward_target_metadata(
    *,
    source_snapshot: PoolFactualBalanceSnapshot,
    applied_at: datetime,
) -> dict[str, dict[str, str]]:
    return {
        "carry_forward": {
            "source_snapshot_id": str(source_snapshot.id),
            "source_quarter_start": source_snapshot.quarter_start.isoformat(),
            "source_quarter_end": source_snapshot.quarter_end.isoformat(),
            "applied_at": applied_at.isoformat(),
        }
    }


def _preserve_non_carry_forward_metadata(raw_metadata: object) -> dict:
    if not isinstance(raw_metadata, dict):
        return {}
    metadata = dict(raw_metadata)
    metadata.pop("carry_forward", None)
    return metadata


def _resolve_month_end_day(*, year: int, month: int) -> int:
    if month == 2:
        is_leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        return 29 if is_leap else 28
    if month in {4, 6, 9, 11}:
        return 30
    return 31


__all__ = [
    "FactualCarryForwardResult",
    "materialize_factual_carry_forward",
    "resolve_next_quarter_window",
]
