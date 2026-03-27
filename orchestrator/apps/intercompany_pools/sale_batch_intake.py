from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db.models import Q

from .batch_intake_normalization import CanonicalPoolBatchLine, CanonicalPoolBatchNormalizationResult
from .models import OrganizationPool, PoolBatchKind
from .validators import validate_pool_graph_for_date


@dataclass(frozen=True)
class SaleBatchClosingIntent:
    organization_id: UUID
    organization_inn: str
    database_id: UUID
    amount_with_vat: Decimal
    source_line_nos: tuple[int, ...]
    source_external_ids: tuple[str, ...]


@dataclass(frozen=True)
class SaleBatchClosingContract:
    pool_id: str
    period_start: date
    period_end: date | None
    closing_intents: tuple[SaleBatchClosingIntent, ...]
    total_amount_with_vat: Decimal
    line_level_receipt_pairing_required: bool = False


def build_sale_batch_closing_contract(
    *,
    pool: OrganizationPool,
    normalized_batch: CanonicalPoolBatchNormalizationResult,
) -> SaleBatchClosingContract:
    if normalized_batch.provenance.batch_kind != PoolBatchKind.SALE:
        raise ValidationError("Sale batch closing contract accepts only sale batches.")
    if normalized_batch.pool_id != str(pool.id):
        raise ValidationError("Sale batch pool must match the selected pool.")
    if not normalized_batch.lines:
        raise ValidationError("Sale batch closing contract requires at least one normalized line.")

    leaf_targets = _load_active_leaf_publish_targets(pool=pool, target_date=normalized_batch.period_start)
    grouped = _aggregate_sale_lines(lines=normalized_batch.lines, leaf_targets=leaf_targets)
    closing_intents = tuple(sorted(grouped.values(), key=lambda item: (item.organization_inn, str(item.organization_id))))
    total_amount_with_vat = sum((intent.amount_with_vat for intent in closing_intents), Decimal("0.00"))
    return SaleBatchClosingContract(
        pool_id=str(pool.id),
        period_start=normalized_batch.period_start,
        period_end=normalized_batch.period_end,
        closing_intents=closing_intents,
        total_amount_with_vat=total_amount_with_vat,
        line_level_receipt_pairing_required=False,
    )


@dataclass(frozen=True)
class _LeafPublishTarget:
    organization_id: UUID
    organization_inn: str
    database_id: UUID


def _load_active_leaf_publish_targets(
    *,
    pool: OrganizationPool,
    target_date,
) -> dict[str, _LeafPublishTarget]:
    graph = validate_pool_graph_for_date(pool, target_date)
    active_nodes = list(
        pool.node_versions.select_related("organization")
        .filter(effective_from__lte=target_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=target_date))
        .order_by("id")
    )
    parent_node_ids = {
        str(edge.parent_node_id)
        for edge in pool.edge_versions.filter(effective_from__lte=target_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=target_date))
        .only("parent_node_id")
    }
    leaf_node_ids = {node_id for node_id in graph.node_ids if node_id not in parent_node_ids}
    targets: dict[str, _LeafPublishTarget] = {}
    for node in active_nodes:
        if str(node.id) not in leaf_node_ids:
            continue
        database_id = getattr(node.organization, "database_id", None)
        if database_id is None:
            continue
        organization_inn = str(node.organization.inn or "").strip()
        if not organization_inn:
            continue
        targets.setdefault(
            organization_inn,
            _LeafPublishTarget(
                organization_id=node.organization_id,
                organization_inn=organization_inn,
                database_id=database_id,
            ),
        )
    return targets


def _aggregate_sale_lines(
    *,
    lines: Iterable[CanonicalPoolBatchLine],
    leaf_targets: dict[str, _LeafPublishTarget],
) -> dict[UUID, SaleBatchClosingIntent]:
    aggregated: dict[UUID, SaleBatchClosingIntent] = {}
    for line in lines:
        target = leaf_targets.get(line.organization_inn)
        if target is None:
            raise ValidationError(
                f"Organization INN '{line.organization_inn}' is not an active leaf publish target for sale batch intake."
            )
        current = aggregated.get(target.organization_id)
        if current is None:
            aggregated[target.organization_id] = SaleBatchClosingIntent(
                organization_id=target.organization_id,
                organization_inn=target.organization_inn,
                database_id=target.database_id,
                amount_with_vat=line.amount_with_vat,
                source_line_nos=(line.line_no,),
                source_external_ids=((line.external_id,) if line.external_id else ()),
            )
            continue
        aggregated[target.organization_id] = SaleBatchClosingIntent(
            organization_id=current.organization_id,
            organization_inn=current.organization_inn,
            database_id=current.database_id,
            amount_with_vat=current.amount_with_vat + line.amount_with_vat,
            source_line_nos=(*current.source_line_nos, line.line_no),
            source_external_ids=(
                (*current.source_external_ids, line.external_id) if line.external_id else current.source_external_ids
            ),
        )
    return aggregated


__all__ = [
    "SaleBatchClosingContract",
    "SaleBatchClosingIntent",
    "build_sale_batch_closing_contract",
]
