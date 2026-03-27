from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from .models import Organization, PoolFactualBalanceSnapshot


DECIMAL_CENTS = Decimal("0.01")


@dataclass(frozen=True)
class FactualSaleAttributionAllocation:
    snapshot_id: UUID
    batch_id: UUID | None
    edge_id: UUID | None
    attributed_amount: Decimal


@dataclass(frozen=True)
class FactualSaleAttributionPlan:
    organization_id: UUID
    sale_amount: Decimal
    allocations: tuple[FactualSaleAttributionAllocation, ...]
    unattributed_amount: Decimal


@dataclass(frozen=True)
class FactualSaleAttributionApplyResult:
    plan: FactualSaleAttributionPlan
    unattributed_amount: Decimal


def build_leaf_sale_attribution_plan(
    *,
    organization: Organization,
    snapshots: Iterable[PoolFactualBalanceSnapshot],
    sale_amount: Decimal | str,
) -> FactualSaleAttributionPlan:
    normalized_sale_amount = _quantize_cents(Decimal(str(sale_amount or "0")))
    remaining = normalized_sale_amount
    candidate_snapshots = sorted(
        _iter_leaf_attribution_candidates(
            organization=organization,
            snapshots=snapshots,
        ),
        key=_snapshot_sort_key,
    )
    allocations: list[FactualSaleAttributionAllocation] = []
    for snapshot in candidate_snapshots:
        if remaining <= Decimal("0.00"):
            break
        open_balance = _quantize_cents(Decimal(str(snapshot.open_balance or "0")))
        attributed_amount = min(open_balance, remaining)
        if attributed_amount <= Decimal("0.00"):
            continue
        allocations.append(
            FactualSaleAttributionAllocation(
                snapshot_id=snapshot.id,
                batch_id=snapshot.batch_id,
                edge_id=snapshot.edge_id,
                attributed_amount=attributed_amount,
            )
        )
        remaining = _quantize_cents(remaining - attributed_amount)
    return FactualSaleAttributionPlan(
        organization_id=organization.id,
        sale_amount=normalized_sale_amount,
        allocations=tuple(allocations),
        unattributed_amount=max(_quantize_cents(remaining), Decimal("0.00")),
    )


def apply_leaf_sale_attribution_plan(
    *,
    plan: FactualSaleAttributionPlan,
    applied_at: datetime | None = None,
) -> FactualSaleAttributionApplyResult:
    timestamp = applied_at or timezone.now()
    with transaction.atomic():
        for allocation in plan.allocations:
            snapshot = PoolFactualBalanceSnapshot.objects.select_for_update().get(id=allocation.snapshot_id)
            _apply_allocation_to_snapshot(
                snapshot=snapshot,
                allocation=allocation,
                total_sale_amount=plan.sale_amount,
                applied_at=timestamp,
            )
    return FactualSaleAttributionApplyResult(
        plan=plan,
        unattributed_amount=plan.unattributed_amount,
    )


def _iter_leaf_attribution_candidates(
    *,
    organization: Organization,
    snapshots: Iterable[PoolFactualBalanceSnapshot],
) -> Iterable[PoolFactualBalanceSnapshot]:
    organization_id = organization.id
    for snapshot in snapshots:
        if snapshot.organization_id != organization_id:
            continue
        if snapshot.edge_id is None:
            continue
        open_balance = Decimal(str(snapshot.open_balance or "0"))
        if open_balance <= Decimal("0"):
            continue
        yield snapshot


def _snapshot_sort_key(snapshot: PoolFactualBalanceSnapshot) -> tuple:
    return (
        snapshot.quarter_start,
        snapshot.created_at,
        str(snapshot.batch_id or ""),
        str(snapshot.edge_id or ""),
        str(snapshot.id),
    )


def _apply_allocation_to_snapshot(
    *,
    snapshot: PoolFactualBalanceSnapshot,
    allocation: FactualSaleAttributionAllocation,
    total_sale_amount: Decimal,
    applied_at: datetime,
) -> None:
    current_open_balance = _quantize_cents(Decimal(str(snapshot.open_balance or "0")))
    attributed_amount = _quantize_cents(allocation.attributed_amount)
    if current_open_balance <= Decimal("0.00") or attributed_amount <= Decimal("0.00"):
        return
    ratio = _quantize_ratio((current_open_balance - attributed_amount) / current_open_balance)
    snapshot.amount_with_vat = _quantize_cents(Decimal(str(snapshot.amount_with_vat or "0")) * ratio)
    snapshot.amount_without_vat = _quantize_cents(Decimal(str(snapshot.amount_without_vat or "0")) * ratio)
    snapshot.vat_amount = _quantize_cents(Decimal(str(snapshot.vat_amount or "0")) * ratio)
    snapshot.outgoing_amount = _quantize_cents(Decimal(str(snapshot.outgoing_amount or "0")) + attributed_amount)
    snapshot.open_balance = _quantize_cents(current_open_balance - attributed_amount)

    metadata = dict(snapshot.metadata or {})
    history = list(metadata.get("sale_attribution_history") or [])
    history.append(
        {
            "applied_at": applied_at.isoformat(),
            "attributed_amount": f"{attributed_amount:.2f}",
            "sale_amount": f"{_quantize_cents(total_sale_amount):.2f}",
            "remaining_open_balance": f"{_quantize_cents(snapshot.open_balance):.2f}",
            "edge_id": str(snapshot.edge_id or ""),
            "batch_id": str(snapshot.batch_id or ""),
            "rule": "oldest_first_leaf_sale",
        }
    )
    metadata["sale_attribution_history"] = history
    snapshot.metadata = metadata
    snapshot.save(
        update_fields=[
            "amount_with_vat",
            "amount_without_vat",
            "vat_amount",
            "outgoing_amount",
            "open_balance",
            "metadata",
            "updated_at",
        ]
    )


def _quantize_cents(value: Decimal) -> Decimal:
    return value.quantize(DECIMAL_CENTS, rounding=ROUND_HALF_UP)


def _quantize_ratio(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0000001"), rounding=ROUND_HALF_UP)


__all__ = [
    "FactualSaleAttributionAllocation",
    "FactualSaleAttributionApplyResult",
    "FactualSaleAttributionPlan",
    "apply_leaf_sale_attribution_plan",
    "build_leaf_sale_attribution_plan",
]
