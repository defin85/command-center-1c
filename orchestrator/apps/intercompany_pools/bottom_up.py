from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping

from django.core.exceptions import ValidationError
from django.db.models import Q

from .batch_intake_parsers import parse_pool_schema_template_amount, parse_pool_schema_template_rows
from .models import OrganizationPool, PoolSchemaTemplate
from .validators import validate_pool_graph_for_date


@dataclass(frozen=True)
class ImportDiagnostic:
    code: str
    message: str
    line_no: int | None = None
    severity: str = "error"


@dataclass(frozen=True)
class BottomUpLineResult:
    line_no: int
    inn: str | None
    amount: Decimal | None
    status: str
    message: str = ""


@dataclass(frozen=True)
class BottomUpImportSummary:
    processed_rows: int
    accepted_rows: int
    diagnostics_count: int
    total_input_amount: Decimal
    total_root_amount: Decimal
    balance_delta: Decimal
    is_balanced: bool


@dataclass(frozen=True)
class BottomUpImportResult:
    summary: BottomUpImportSummary
    aggregate_report: dict[str, Decimal]
    detailed_report: list[BottomUpLineResult]
    diagnostics: list[ImportDiagnostic]


def run_bottom_up_import(
    *,
    pool: OrganizationPool,
    template: PoolSchemaTemplate,
    period_date: date,
    json_payload: Any | None = None,
    xlsx_bytes: bytes | None = None,
    scale: int = 2,
) -> BottomUpImportResult:
    if template.tenant_id != pool.tenant_id:
        raise ValidationError("Template tenant must match pool tenant.")
    if not template.is_public:
        raise ValidationError("Bottom-up import accepts only public templates.")
    if not template.is_active:
        raise ValidationError("Bottom-up import template is inactive.")

    rows = parse_pool_schema_template_rows(
        template=template,
        json_payload=json_payload,
        xlsx_bytes=xlsx_bytes,
    )
    graph = validate_pool_graph_for_date(pool, period_date)
    quantizer = Decimal(10) ** (-scale)

    node_by_inn = _get_active_node_by_inn(pool=pool, period_date=period_date)
    diagnostics: list[ImportDiagnostic] = []
    line_results: list[BottomUpLineResult] = []
    node_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    total_input_amount = Decimal("0")
    accepted_rows = 0

    inn_key, amount_key = _resolve_mapping(template.schema)
    for line_no, row in enumerate(rows, start=2):
        try:
            raw_inn = row.get(inn_key)
            raw_amount = row.get(amount_key)
            inn = str(raw_inn or "").strip()
            if not inn:
                raise ValidationError("Missing INN value")

            amount = parse_pool_schema_template_amount(
                raw_amount,
                quantizer=quantizer,
                field_name="amount",
            )
            node_id = node_by_inn.get(inn)
            if node_id is None:
                diagnostics.append(
                    ImportDiagnostic(
                        code="unknown_inn",
                        line_no=line_no,
                        message=f"Unknown INN '{inn}' for active pool graph.",
                    )
                )
                line_results.append(
                    BottomUpLineResult(
                        line_no=line_no,
                        inn=inn,
                        amount=amount,
                        status="error",
                        message="unknown_inn",
                    )
                )
                continue

            node_totals[node_id] += amount
            total_input_amount += amount
            accepted_rows += 1
            line_results.append(
                BottomUpLineResult(
                    line_no=line_no,
                    inn=inn,
                    amount=amount,
                    status="accepted",
                )
            )
        except ValidationError as exc:
            diagnostics.append(
                ImportDiagnostic(
                    code="invalid_row",
                    line_no=line_no,
                    message=str(exc),
                )
            )
            line_results.append(
                BottomUpLineResult(
                    line_no=line_no,
                    inn=None,
                    amount=None,
                    status="error",
                    message="invalid_row",
                )
            )

    root_total = _propagate_to_root(
        node_totals=node_totals,
        edge_pairs=list(graph.edge_pairs),
        root_id=graph.root_id,
        scale=scale,
    )
    total_input_amount = total_input_amount.quantize(quantizer, rounding=ROUND_HALF_UP)
    root_total = root_total.quantize(quantizer, rounding=ROUND_HALF_UP)
    balance_delta = (root_total - total_input_amount).quantize(quantizer, rounding=ROUND_HALF_UP)
    is_balanced = balance_delta == Decimal("0")

    if not is_balanced:
        diagnostics.append(
            ImportDiagnostic(
                code="balance_mismatch",
                message=f"Bottom-up balance mismatch: delta={balance_delta}",
            )
        )

    summary = BottomUpImportSummary(
        processed_rows=len(rows),
        accepted_rows=accepted_rows,
        diagnostics_count=len(diagnostics),
        total_input_amount=total_input_amount,
        total_root_amount=root_total,
        balance_delta=balance_delta,
        is_balanced=is_balanced,
    )
    aggregate_report = {
        "input_total": total_input_amount,
        "root_total": root_total,
        "delta": balance_delta,
    }
    return BottomUpImportResult(
        summary=summary,
        aggregate_report=aggregate_report,
        detailed_report=line_results,
        diagnostics=diagnostics,
    )


def _resolve_mapping(schema: Mapping[str, Any]) -> tuple[str, str]:
    columns = schema.get("columns") if isinstance(schema, Mapping) else None
    if not isinstance(columns, Mapping):
        columns = {}
    inn_key = str(columns.get("inn") or "inn")
    amount_key = str(columns.get("amount") or "amount")
    return inn_key, amount_key
def _get_active_node_by_inn(*, pool: OrganizationPool, period_date: date) -> dict[str, str]:
    qs = (
        pool.node_versions.filter(effective_from__lte=period_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=period_date))
        .select_related("organization")
    )
    by_inn: dict[str, str] = {}
    for node in qs:
        inn = str(node.organization.inn or "").strip()
        if not inn or inn in by_inn:
            continue
        by_inn[inn] = str(node.id)
    return by_inn


def _propagate_to_root(
    *,
    node_totals: dict[str, Decimal],
    edge_pairs: list[tuple[str, str]],
    root_id: str,
    scale: int,
) -> Decimal:
    quantizer = Decimal(10) ** (-scale)
    parents_by_child: dict[str, list[str]] = defaultdict(list)
    for parent_id, child_id in edge_pairs:
        parents_by_child[child_id].append(parent_id)

    for node_id in _reverse_topological_nodes(root_id=root_id, edge_pairs=edge_pairs):
        amount = node_totals.get(node_id, Decimal("0")).quantize(quantizer, rounding=ROUND_HALF_UP)
        parents = parents_by_child.get(node_id, [])
        if not parents:
            continue

        shares = _split_amount_equally(amount=amount, buckets=len(parents), scale=scale)
        for idx, parent_id in enumerate(parents):
            node_totals[parent_id] = node_totals.get(parent_id, Decimal("0")) + shares[idx]

    return node_totals.get(root_id, Decimal("0"))


def _split_amount_equally(*, amount: Decimal, buckets: int, scale: int) -> list[Decimal]:
    if buckets <= 0:
        return []
    quantizer = Decimal(10) ** (-scale)
    factor = Decimal(10) ** scale
    units = int((amount * factor).to_integral_value(rounding=ROUND_HALF_UP))
    base = units // buckets
    remainder = units % buckets
    values = [base for _ in range(buckets)]
    if remainder:
        values[-1] += remainder
    return [(Decimal(v) / factor).quantize(quantizer, rounding=ROUND_HALF_UP) for v in values]


def _reverse_topological_nodes(*, root_id: str, edge_pairs: list[tuple[str, str]]) -> list[str]:
    nodes = {root_id}
    children_by_parent: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = defaultdict(int)

    for parent_id, child_id in edge_pairs:
        nodes.add(parent_id)
        nodes.add(child_id)
        children_by_parent[parent_id].append(child_id)
        in_degree[child_id] += 1
        in_degree.setdefault(parent_id, 0)

    order: list[str] = []
    queue = [node for node in nodes if in_degree.get(node, 0) == 0]
    while queue:
        node_id = queue.pop(0)
        order.append(node_id)
        for child_id in children_by_parent.get(node_id, []):
            in_degree[child_id] -= 1
            if in_degree[child_id] == 0:
                queue.append(child_id)
    return list(reversed(order))
