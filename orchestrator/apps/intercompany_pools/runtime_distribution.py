from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
from typing import Any, Mapping

from django.core.exceptions import ValidationError
from django.db.models import Q

from .distribution import DistributionEdge, distribute_top_down
from .models import PoolEdgeVersion, PoolNodeVersion, PoolRun, PoolRunDirection
from .runtime_run_input import build_runtime_run_input
from .validators import validate_pool_graph


DISTRIBUTION_ARTIFACT_VERSION = "distribution_artifact.v1"

ERROR_CODE_DISTRIBUTION_INPUT_INVALID = "POOL_DISTRIBUTION_INPUT_INVALID"
ERROR_CODE_DISTRIBUTION_GRAPH_INVALID = "POOL_DISTRIBUTION_GRAPH_INVALID"

_MONEY_SCALE = 2
_MONEY_QUANTIZER = Decimal("0.01")


@dataclass(frozen=True)
class _TopologySegment:
    start_date: date
    end_date: date
    days: int
    topology: dict[str, Any]


def compute_distribution_runtime_state(
    *,
    run: PoolRun,
    run_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = build_runtime_run_input(run=run, run_input=run_input)
    period_start = run.period_start
    period_end = run.period_end or run.period_start
    if period_end < period_start:
        _fail(
            ERROR_CODE_DISTRIBUTION_INPUT_INVALID,
            f"period_end '{period_end.isoformat()}' must be >= period_start '{period_start.isoformat()}'",
        )
    topology_segments = _load_topology_segments(
        run=run,
        period_start=period_start,
        period_end=period_end,
    )

    if run.direction == PoolRunDirection.TOP_DOWN:
        state = _compute_top_down_distribution_over_segments(
            run=run,
            run_input=payload,
            segments=topology_segments,
        )
    else:
        state = _compute_bottom_up_distribution_over_segments(
            run=run,
            run_input=payload,
            segments=topology_segments,
        )
    topology = state["topology"]

    artifact = _build_distribution_artifact(
        run=run,
        run_input=payload,
        topology=topology,
        node_totals=state["node_totals"],
        edge_allocations=state["edge_allocations"],
        source_total=state["source_total"],
        distributed_total=state["distributed_total"],
        diagnostics=state.get("diagnostics", []),
    )
    publication_payload = build_publication_payload_from_artifact(
        artifact=artifact,
        run_input=payload,
    )
    summary = _build_distribution_summary(artifact=artifact)
    return {
        "artifact": artifact,
        "summary": summary,
        "publication_payload": publication_payload,
    }


def load_runtime_topology_for_period(*, run: PoolRun) -> dict[str, Any]:
    period_start = run.period_start
    period_end = run.period_end or run.period_start
    if period_end < period_start:
        _fail(
            ERROR_CODE_DISTRIBUTION_INPUT_INVALID,
            f"period_end '{period_end.isoformat()}' must be >= period_start '{period_start.isoformat()}'",
        )
    segments = _load_topology_segments(
        run=run,
        period_start=period_start,
        period_end=period_end,
    )
    return _merge_topology_segments(segments=segments)


def _compute_top_down_distribution_over_segments(
    *,
    run: PoolRun,
    run_input: dict[str, Any],
    segments: list[_TopologySegment],
) -> dict[str, Any]:
    starting_amount = _parse_decimal(run_input.get("starting_amount"))
    if starting_amount is None or starting_amount <= Decimal("0"):
        _fail(
            ERROR_CODE_DISTRIBUTION_INPUT_INVALID,
            "top_down run_input.starting_amount must be a positive decimal",
        )

    normalized_starting_amount = _money(starting_amount)
    segment_amounts = _allocate_total_by_segment_days(
        total_amount=normalized_starting_amount,
        segment_days=[segment.days for segment in segments],
    )

    node_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    edge_allocations: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))
    distributed_total = Decimal("0")
    diagnostics: list[dict[str, Any]] = []

    for index, segment in enumerate(segments):
        amount_for_segment = segment_amounts[index]
        segment_input = dict(run_input)
        segment_input["starting_amount"] = _decimal_to_string(amount_for_segment)
        segment_state = _compute_top_down_distribution(
            run=run,
            run_input=segment_input,
            topology=segment.topology,
            seed_suffix=segment.start_date.isoformat(),
        )
        for node_id, amount in segment_state["node_totals"].items():
            node_totals[node_id] = _money(node_totals[node_id] + amount)
        for edge_key, amount in segment_state["edge_allocations"].items():
            edge_allocations[edge_key] = _money(edge_allocations[edge_key] + amount)
        distributed_total = _money(distributed_total + segment_state["distributed_total"])
        diagnostics.append(
            {
                "code": "topology_segment",
                "status": "info",
                "segment_index": index + 1,
                "segment_start": segment.start_date.isoformat(),
                "segment_end": segment.end_date.isoformat(),
                "segment_days": segment.days,
                "topology_version_ref": segment.topology.get("topology_version_ref"),
                "segment_source_total": _decimal_to_string(amount_for_segment),
                "segment_distributed_total": _decimal_to_string(segment_state["distributed_total"]),
            }
        )

    return {
        "topology": _merge_topology_segments(segments=segments),
        "node_totals": dict(node_totals),
        "edge_allocations": dict(edge_allocations),
        "source_total": normalized_starting_amount,
        "distributed_total": _money(distributed_total),
        "diagnostics": diagnostics,
    }


def _compute_bottom_up_distribution_over_segments(
    *,
    run: PoolRun,
    run_input: dict[str, Any],
    segments: list[_TopologySegment],
) -> dict[str, Any]:
    rows_by_segment = _partition_source_rows_by_topology_segments(
        run_input=run_input,
        segments=segments,
    )

    node_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    edge_allocations: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))
    source_total = Decimal("0")
    distributed_total = Decimal("0")
    diagnostics: list[dict[str, Any]] = []

    for index, segment in enumerate(segments):
        segment_input = dict(run_input)
        segment_input["source_payload"] = rows_by_segment[index]
        segment_state = _compute_bottom_up_distribution(
            run=run,
            run_input=segment_input,
            topology=segment.topology,
        )
        for node_id, amount in segment_state["node_totals"].items():
            node_totals[node_id] = _money(node_totals[node_id] + amount)
        for edge_key, amount in segment_state["edge_allocations"].items():
            edge_allocations[edge_key] = _money(edge_allocations[edge_key] + amount)
        source_total = _money(source_total + segment_state["source_total"])
        distributed_total = _money(distributed_total + segment_state["distributed_total"])
        diagnostics.extend(segment_state.get("diagnostics", []))
        diagnostics.append(
            {
                "code": "topology_segment",
                "status": "info",
                "segment_index": index + 1,
                "segment_start": segment.start_date.isoformat(),
                "segment_end": segment.end_date.isoformat(),
                "segment_days": segment.days,
                "topology_version_ref": segment.topology.get("topology_version_ref"),
                "source_rows_count": len(rows_by_segment[index]),
            }
        )

    return {
        "topology": _merge_topology_segments(segments=segments),
        "node_totals": dict(node_totals),
        "edge_allocations": dict(edge_allocations),
        "source_total": _money(source_total),
        "distributed_total": _money(distributed_total),
        "diagnostics": diagnostics,
    }


def _partition_source_rows_by_topology_segments(
    *,
    run_input: dict[str, Any],
    segments: list[_TopologySegment],
) -> list[list[dict[str, Any]]]:
    rows = _source_rows(run_input=run_input)
    if not segments:
        return [rows]

    default_date = segments[0].start_date
    rows_by_segment: list[list[dict[str, Any]]] = [[] for _ in segments]
    for row in rows:
        row_date = _resolve_source_row_date(row=row, default_date=default_date)
        segment_index = _find_segment_index_for_date(segments=segments, target_date=row_date)
        if segment_index is None:
            _fail(
                ERROR_CODE_DISTRIBUTION_INPUT_INVALID,
                f"source row date '{row_date.isoformat()}' is out of run period range",
            )
        rows_by_segment[segment_index].append(dict(row))
    return rows_by_segment


def build_publication_payload_from_artifact(
    *,
    artifact: Mapping[str, Any],
    run_input: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = run_input if isinstance(run_input, Mapping) else {}

    node_totals_raw = artifact.get("node_totals")
    publish_target_node_ids = (
        artifact.get("coverage", {}).get("publish_target_node_ids")
        if isinstance(artifact.get("coverage"), Mapping)
        else None
    )

    node_totals_by_id: dict[str, dict[str, Any]] = {}
    if isinstance(node_totals_raw, list):
        for item in node_totals_raw:
            if not isinstance(item, Mapping):
                continue
            node_id = str(item.get("node_id") or "").strip()
            if not node_id:
                continue
            node_totals_by_id[node_id] = dict(item)

    ordered_target_ids: list[str] = []
    if isinstance(publish_target_node_ids, list):
        ordered_target_ids = sorted(
            str(node_id) for node_id in publish_target_node_ids if str(node_id).strip()
        )

    documents_by_database: dict[str, list[dict[str, Any]]] = {}
    for node_id in ordered_target_ids:
        node_entry = node_totals_by_id.get(node_id)
        if not isinstance(node_entry, dict):
            continue
        database_id = str(node_entry.get("database_id") or "").strip()
        if not database_id:
            continue
        amount = _parse_decimal(node_entry.get("amount"))
        if amount is None or amount <= Decimal("0"):
            continue
        documents_by_database.setdefault(database_id, []).append(
            {"Amount": _decimal_to_string(amount)}
        )

    publication_payload = {
        "entity_name": str(payload.get("entity_name") or "").strip(),
        "documents_by_database": documents_by_database,
        "max_attempts": payload.get("max_attempts"),
        "retry_interval_seconds": payload.get("retry_interval_seconds"),
        "external_key_field": str(payload.get("external_key_field") or "").strip(),
    }
    return {"pool_runtime": publication_payload}


def _compute_top_down_distribution(
    *,
    run: PoolRun,
    run_input: dict[str, Any],
    topology: dict[str, Any],
    seed_suffix: str | None = None,
) -> dict[str, Any]:
    starting_amount = _parse_decimal(run_input.get("starting_amount"))
    if starting_amount is None or starting_amount <= Decimal("0"):
        _fail(
            ERROR_CODE_DISTRIBUTION_INPUT_INVALID,
            "top_down run_input.starting_amount must be a positive decimal",
        )

    edge_models: list[PoolEdgeVersion] = topology["edges"]
    distribution_edges = [
        DistributionEdge(
            parent_id=str(edge.parent_node_id),
            child_id=str(edge.child_node_id),
            weight=Decimal(edge.weight),
            min_amount=edge.min_amount,
            max_amount=edge.max_amount,
        )
        for edge in edge_models
    ]

    seed_base = run.seed if run.seed is not None else str(run.id)
    seed_value = f"{seed_base}:{seed_suffix}" if seed_suffix else seed_base
    try:
        result = distribute_top_down(
            total_amount=_money(starting_amount),
            root_node_id=topology["root_node_id"],
            edges=distribution_edges,
            seed=seed_value,
            scale=_MONEY_SCALE,
        )
    except ValidationError as exc:
        _fail(ERROR_CODE_DISTRIBUTION_GRAPH_INVALID, str(exc))

    node_totals = {
        node_id: _money(result.node_totals.get(node_id, Decimal("0")))
        for node_id in topology["node_ids"]
    }
    edge_allocations = {
        edge_key: _money(result.edge_allocations.get(edge_key, Decimal("0")))
        for edge_key in topology["edge_pairs"]
    }

    distributed_total = _money(
        sum(node_totals.get(node_id, Decimal("0")) for node_id in topology["leaf_node_ids"])
    )
    return {
        "node_totals": node_totals,
        "edge_allocations": edge_allocations,
        "source_total": _money(starting_amount),
        "distributed_total": distributed_total,
        "diagnostics": [],
    }


def _compute_bottom_up_distribution(
    *,
    run: PoolRun,
    run_input: dict[str, Any],
    topology: dict[str, Any],
) -> dict[str, Any]:
    source_rows = _source_rows(run_input=run_input)
    node_by_inn = topology["node_id_by_inn"]

    node_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    diagnostics: list[dict[str, Any]] = []
    source_total = Decimal("0")
    accepted_rows = 0

    for row in source_rows:
        inn = str(row.get("inn") or "").strip()
        amount = _parse_decimal(row.get("amount"))
        if amount is None:
            diagnostics.append(
                {
                    "code": "invalid_amount",
                    "status": "error",
                    "message": "row amount is missing or invalid",
                    "inn": inn,
                }
            )
            continue
        if not inn:
            diagnostics.append(
                {
                    "code": "missing_inn",
                    "status": "error",
                    "message": "row inn is required",
                }
            )
            continue

        node_id = node_by_inn.get(inn)
        if not node_id:
            diagnostics.append(
                {
                    "code": "unknown_inn",
                    "status": "error",
                    "message": f"unknown INN '{inn}' for active pool topology",
                    "inn": inn,
                }
            )
            continue

        node_totals[node_id] = _money(node_totals[node_id] + amount)
        source_total = _money(source_total + amount)
        accepted_rows += 1

    edge_allocations = _aggregate_bottom_up_to_root(
        node_totals=node_totals,
        edge_pairs=topology["edge_pairs"],
        root_node_id=topology["root_node_id"],
    )
    distributed_total = _money(node_totals.get(topology["root_node_id"], Decimal("0")))
    diagnostics.append(
        {
            "code": "bottom_up_summary",
            "status": "info",
            "processed_rows": len(source_rows),
            "accepted_rows": accepted_rows,
        }
    )
    return {
        "node_totals": {
            node_id: _money(node_totals.get(node_id, Decimal("0")))
            for node_id in topology["node_ids"]
        },
        "edge_allocations": {
            edge_key: _money(edge_allocations.get(edge_key, Decimal("0")))
            for edge_key in topology["edge_pairs"]
        },
        "source_total": _money(source_total),
        "distributed_total": distributed_total,
        "diagnostics": diagnostics,
    }


def _aggregate_bottom_up_to_root(
    *,
    node_totals: dict[str, Decimal],
    edge_pairs: list[tuple[str, str]],
    root_node_id: str,
) -> dict[tuple[str, str], Decimal]:
    parents_by_child: dict[str, list[str]] = defaultdict(list)
    for parent_id, child_id in edge_pairs:
        parents_by_child[child_id].append(parent_id)

    edge_allocations: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))
    for node_id in _reverse_topological_nodes(root_node_id=root_node_id, edge_pairs=edge_pairs):
        amount = _money(node_totals.get(node_id, Decimal("0")))
        parents = parents_by_child.get(node_id, [])
        if not parents:
            continue
        shares = _split_amount_equally(amount=amount, buckets=len(parents))
        for idx, parent_id in enumerate(parents):
            share = _money(shares[idx])
            edge_allocations[(parent_id, node_id)] = _money(
                edge_allocations[(parent_id, node_id)] + share
            )
            node_totals[parent_id] = _money(node_totals.get(parent_id, Decimal("0")) + share)
    return dict(edge_allocations)


def _build_distribution_artifact(
    *,
    run: PoolRun,
    run_input: dict[str, Any],
    topology: dict[str, Any],
    node_totals: dict[str, Decimal],
    edge_allocations: dict[tuple[str, str], Decimal],
    source_total: Decimal,
    distributed_total: Decimal,
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any]:
    node_models: dict[str, PoolNodeVersion] = topology["node_models"]
    edge_models: dict[tuple[str, str], PoolEdgeVersion] = topology["edge_models"]
    publish_target_node_ids: list[str] = topology["publish_target_node_ids"]
    root_node_ids = {
        str(node_id).strip()
        for node_id in (
            topology.get("root_node_ids")
            if isinstance(topology.get("root_node_ids"), list)
            else [topology.get("root_node_id")]
        )
        if str(node_id).strip()
    }

    covered_node_ids = sorted(
        node_id
        for node_id in publish_target_node_ids
        if _money(node_totals.get(node_id, Decimal("0"))) > Decimal("0")
    )
    missing_node_ids = sorted(set(publish_target_node_ids) - set(covered_node_ids))

    delta = _money(distributed_total - source_total)
    balance = {
        "source_total": _decimal_to_string(source_total),
        "distributed_total": _decimal_to_string(distributed_total),
        "delta": _decimal_to_string(delta),
        "tolerance": _decimal_to_string(Decimal("0")),
        "is_balanced": delta == Decimal("0"),
    }
    coverage = {
        "publish_target_node_ids": publish_target_node_ids,
        "covered_target_node_ids": covered_node_ids,
        "missing_target_node_ids": missing_node_ids,
        "is_full": len(missing_node_ids) == 0,
    }

    node_totals_payload: list[dict[str, Any]] = []
    for node_id in topology["node_ids"]:
        node = node_models[node_id]
        database_id = (
            str(node.organization.database_id)
            if getattr(node.organization, "database_id", None)
            else ""
        )
        node_totals_payload.append(
            {
                "node_id": node_id,
                "organization_id": str(node.organization_id),
                "database_id": database_id,
                "is_root": node_id in root_node_ids,
                "amount": _decimal_to_string(node_totals.get(node_id, Decimal("0"))),
            }
        )

    edge_allocations_payload: list[dict[str, Any]] = []
    for edge_key in topology["edge_pairs"]:
        edge_model = edge_models[edge_key]
        edge_allocations_payload.append(
            {
                "parent_node_id": edge_key[0],
                "child_node_id": edge_key[1],
                "amount": _decimal_to_string(edge_allocations.get(edge_key, Decimal("0"))),
                "weight": _decimal_to_string(Decimal(edge_model.weight)),
                "min_amount": _decimal_to_string(edge_model.min_amount),
                "max_amount": _decimal_to_string(edge_model.max_amount),
            }
        )

    input_provenance = {
        "run_input_documents_by_database": _normalize_documents_by_database(
            run_input.get("documents_by_database")
        ),
        "source_payload_rows_count": len(_source_rows(run_input=run_input)),
    }

    artifact = {
        "version": DISTRIBUTION_ARTIFACT_VERSION,
        "direction": run.direction,
        "topology_version_ref": topology["topology_version_ref"],
        "node_totals": node_totals_payload,
        "edge_allocations": edge_allocations_payload,
        "coverage": coverage,
        "balance": balance,
        "diagnostics": diagnostics,
        "input_provenance": input_provenance,
    }
    return artifact


def _build_distribution_summary(*, artifact: dict[str, Any]) -> dict[str, Any]:
    balance = artifact.get("balance") if isinstance(artifact.get("balance"), Mapping) else {}
    coverage = artifact.get("coverage") if isinstance(artifact.get("coverage"), Mapping) else {}
    return {
        "artifact_version": artifact.get("version"),
        "direction": artifact.get("direction"),
        "topology_version_ref": artifact.get("topology_version_ref"),
        "source_total_amount": balance.get("source_total"),
        "distributed_total_amount": balance.get("distributed_total"),
        "delta": balance.get("delta"),
        "balanced": bool(balance.get("is_balanced")),
        "coverage_full": bool(coverage.get("is_full")),
        "missing_targets_count": len(coverage.get("missing_target_node_ids") or []),
    }


def _load_active_topology(*, run: PoolRun, target_date: date) -> dict[str, Any]:
    active_nodes = list(
        PoolNodeVersion.objects.select_related("organization")
        .filter(pool=run.pool, effective_from__lte=target_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=target_date))
        .order_by("id")
    )
    if not active_nodes:
        _fail(
            ERROR_CODE_DISTRIBUTION_GRAPH_INVALID,
            f"no active topology nodes for period_start={target_date.isoformat()}",
        )

    node_ids = [str(node.id) for node in active_nodes]
    node_id_set = set(node_ids)
    active_edges = list(
        PoolEdgeVersion.objects.select_related("parent_node", "child_node")
        .filter(pool=run.pool, effective_from__lte=target_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=target_date))
        .filter(parent_node_id__in=node_id_set, child_node_id__in=node_id_set)
        .order_by("parent_node_id", "child_node_id")
    )
    edge_pairs = [
        (str(edge.parent_node_id), str(edge.child_node_id))
        for edge in active_edges
    ]

    try:
        graph = validate_pool_graph(node_ids=node_ids, edge_pairs=edge_pairs)
    except ValidationError as exc:
        _fail(ERROR_CODE_DISTRIBUTION_GRAPH_INVALID, str(exc))

    node_models = {str(node.id): node for node in active_nodes}
    edge_models = {
        (str(edge.parent_node_id), str(edge.child_node_id)): edge
        for edge in active_edges
    }
    parent_node_ids = {parent_id for parent_id, _ in edge_pairs}
    leaf_node_ids = sorted(node_id for node_id in graph.node_ids if node_id not in parent_node_ids)

    target_leaf_node_ids = [
        node_id
        for node_id in leaf_node_ids
        if getattr(node_models[node_id].organization, "database_id", None) is not None
    ]
    if not target_leaf_node_ids:
        target_leaf_node_ids = [
            node_id
            for node_id in graph.node_ids
            if (
                getattr(node_models[node_id].organization, "database_id", None) is not None
                and node_id != graph.root_id
            )
        ]
    if not target_leaf_node_ids and getattr(node_models[graph.root_id].organization, "database_id", None) is not None:
        target_leaf_node_ids = [graph.root_id]

    target_leaf_node_ids = sorted(target_leaf_node_ids)
    node_id_by_inn: dict[str, str] = {}
    for node in active_nodes:
        inn = str(node.organization.inn or "").strip()
        if inn and inn not in node_id_by_inn:
            node_id_by_inn[inn] = str(node.id)

    topology_version_ref = _build_topology_version_ref(
        node_ids=list(graph.node_ids),
        edge_pairs=list(graph.edge_pairs),
        target_date=target_date,
    )
    return {
        "root_node_id": graph.root_id,
        "root_node_ids": [graph.root_id],
        "node_ids": list(graph.node_ids),
        "edge_pairs": list(graph.edge_pairs),
        "leaf_node_ids": leaf_node_ids,
        "publish_target_node_ids": target_leaf_node_ids,
        "nodes": active_nodes,
        "edges": active_edges,
        "node_models": node_models,
        "edge_models": edge_models,
        "node_id_by_inn": node_id_by_inn,
        "topology_version_ref": topology_version_ref,
    }


def _load_topology_segments(
    *,
    run: PoolRun,
    period_start: date,
    period_end: date,
) -> list[_TopologySegment]:
    end_exclusive = period_end + timedelta(days=1)
    boundaries: set[date] = {period_start, end_exclusive}

    node_versions = (
        PoolNodeVersion.objects.filter(pool=run.pool, effective_from__lte=period_end)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=period_start))
        .only("effective_from", "effective_to")
    )
    edge_versions = (
        PoolEdgeVersion.objects.filter(pool=run.pool, effective_from__lte=period_end)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=period_start))
        .only("effective_from", "effective_to")
    )

    for version in list(node_versions) + list(edge_versions):
        if period_start < version.effective_from <= period_end:
            boundaries.add(version.effective_from)
        if version.effective_to is not None and period_start <= version.effective_to < period_end:
            boundaries.add(version.effective_to + timedelta(days=1))

    sorted_boundaries = sorted(boundaries)
    segments: list[_TopologySegment] = []
    for idx in range(len(sorted_boundaries) - 1):
        segment_start = sorted_boundaries[idx]
        next_boundary = sorted_boundaries[idx + 1]
        if segment_start >= next_boundary:
            continue
        segment_end = next_boundary - timedelta(days=1)
        topology = _load_active_topology(run=run, target_date=segment_start)
        segment_days = (segment_end - segment_start).days + 1
        segments.append(
            _TopologySegment(
                start_date=segment_start,
                end_date=segment_end,
                days=segment_days,
                topology=topology,
            )
        )
    if not segments:
        _fail(
            ERROR_CODE_DISTRIBUTION_GRAPH_INVALID,
            f"no active topology segments for period {period_start.isoformat()}..{period_end.isoformat()}",
        )
    return segments


def _merge_topology_segments(
    *,
    segments: list[_TopologySegment],
) -> dict[str, Any]:
    if not segments:
        _fail(ERROR_CODE_DISTRIBUTION_GRAPH_INVALID, "topology segments are required")

    node_ids: set[str] = set()
    edge_pairs: set[tuple[str, str]] = set()
    leaf_node_ids: set[str] = set()
    publish_target_node_ids: set[str] = set()
    root_node_ids: set[str] = set()
    node_models: dict[str, PoolNodeVersion] = {}
    edge_models: dict[tuple[str, str], PoolEdgeVersion] = {}
    segment_refs: list[dict[str, str]] = []

    for segment in segments:
        topology = segment.topology
        node_ids.update(str(node_id) for node_id in topology.get("node_ids", []))
        edge_pairs.update(tuple(item) for item in topology.get("edge_pairs", []))
        leaf_node_ids.update(str(node_id) for node_id in topology.get("leaf_node_ids", []))
        publish_target_node_ids.update(str(node_id) for node_id in topology.get("publish_target_node_ids", []))
        root_node_id = str(topology.get("root_node_id") or "").strip()
        if root_node_id:
            root_node_ids.add(root_node_id)
        node_models.update(topology.get("node_models", {}))
        edge_models.update(topology.get("edge_models", {}))
        segment_refs.append(
            {
                "segment_start": segment.start_date.isoformat(),
                "segment_end": segment.end_date.isoformat(),
                "topology_version_ref": str(topology.get("topology_version_ref") or ""),
            }
        )

    root_candidates = sorted(root_node_ids)
    if not root_candidates:
        _fail(ERROR_CODE_DISTRIBUTION_GRAPH_INVALID, "merged topology has no root nodes")
    topology_version_ref = _build_period_topology_version_ref(segment_refs=segment_refs)
    return {
        "root_node_id": root_candidates[0],
        "root_node_ids": root_candidates,
        "node_ids": sorted(node_ids),
        "edge_pairs": sorted(edge_pairs),
        "leaf_node_ids": sorted(leaf_node_ids),
        "publish_target_node_ids": sorted(publish_target_node_ids),
        "node_models": node_models,
        "edge_models": edge_models,
        "topology_version_ref": topology_version_ref,
    }


def _build_period_topology_version_ref(*, segment_refs: list[dict[str, str]]) -> str:
    payload = {"segments": segment_refs}
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"pool_topology_window:{digest[:16]}"


def _build_topology_version_ref(
    *,
    node_ids: list[str],
    edge_pairs: list[tuple[str, str]],
    target_date: date,
) -> str:
    payload = {
        "target_date": target_date.isoformat(),
        "node_ids": sorted(node_ids),
        "edge_pairs": sorted([list(item) for item in edge_pairs]),
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"pool_topology:{digest[:16]}"


def _source_rows(*, run_input: dict[str, Any]) -> list[dict[str, Any]]:
    source_payload = run_input.get("source_payload")
    if isinstance(source_payload, list):
        return [dict(item) for item in source_payload if isinstance(item, Mapping)]
    if isinstance(source_payload, Mapping):
        rows = source_payload.get("rows")
        if isinstance(rows, list):
            return [dict(item) for item in rows if isinstance(item, Mapping)]
    return []


def _normalize_documents_by_database(raw_value: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(raw_value, Mapping):
        return {}
    normalized: dict[str, list[dict[str, Any]]] = {}
    for raw_db_id, raw_docs in raw_value.items():
        database_id = str(raw_db_id or "").strip()
        if not database_id or not isinstance(raw_docs, list):
            continue
        docs = [dict(item) for item in raw_docs if isinstance(item, Mapping)]
        if docs:
            normalized[database_id] = docs
    return normalized


def _resolve_source_row_date(*, row: Mapping[str, Any], default_date: date) -> date:
    for key in ("date", "document_date", "operation_date"):
        raw_value = row.get(key)
        if raw_value in (None, ""):
            continue
        try:
            return date.fromisoformat(str(raw_value))
        except (TypeError, ValueError):
            _fail(
                ERROR_CODE_DISTRIBUTION_INPUT_INVALID,
                f"source row field '{key}' must be ISO date (YYYY-MM-DD), got '{raw_value}'",
            )
    return default_date


def _find_segment_index_for_date(*, segments: list[_TopologySegment], target_date: date) -> int | None:
    for index, segment in enumerate(segments):
        if segment.start_date <= target_date <= segment.end_date:
            return index
    return None


def _allocate_total_by_segment_days(*, total_amount: Decimal, segment_days: list[int]) -> list[Decimal]:
    if not segment_days:
        return []
    positive_days = [max(0, int(days)) for days in segment_days]
    total_days = sum(positive_days)
    if total_days <= 0:
        return [_money(Decimal("0")) for _ in segment_days]

    factor = Decimal(10) ** _MONEY_SCALE
    total_units = int((total_amount * factor).to_integral_value(rounding=ROUND_HALF_UP))
    unit_floors: list[int] = []
    fractions: list[Decimal] = []
    allocated_units = 0

    for days in positive_days:
        exact_units = (Decimal(total_units) * Decimal(days)) / Decimal(total_days)
        floor_units = int(exact_units)
        unit_floors.append(floor_units)
        fractions.append(exact_units - Decimal(floor_units))
        allocated_units += floor_units

    remainder = total_units - allocated_units
    if remainder > 0:
        ordering = sorted(
            range(len(fractions)),
            key=lambda idx: (-fractions[idx], idx),
        )
        for idx in ordering[:remainder]:
            unit_floors[idx] += 1

    return [_money(Decimal(units) / factor) for units in unit_floors]


def _split_amount_equally(*, amount: Decimal, buckets: int) -> list[Decimal]:
    if buckets <= 0:
        return []
    factor = Decimal(10) ** _MONEY_SCALE
    units = int((amount * factor).to_integral_value(rounding=ROUND_HALF_UP))
    base = units // buckets
    remainder = units % buckets
    values = [base for _ in range(buckets)]
    if remainder:
        values[-1] += remainder
    return [_money(Decimal(value) / factor) for value in values]


def _reverse_topological_nodes(
    *,
    root_node_id: str,
    edge_pairs: list[tuple[str, str]],
) -> list[str]:
    nodes = {root_node_id}
    children_by_parent: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = defaultdict(int)

    for parent_id, child_id in edge_pairs:
        nodes.add(parent_id)
        nodes.add(child_id)
        children_by_parent[parent_id].append(child_id)
        in_degree[child_id] += 1
        in_degree.setdefault(parent_id, 0)

    queue = [node_id for node_id in nodes if in_degree.get(node_id, 0) == 0]
    order: list[str] = []
    while queue:
        node_id = queue.pop(0)
        order.append(node_id)
        for child_id in children_by_parent.get(node_id, []):
            in_degree[child_id] -= 1
            if in_degree[child_id] == 0:
                queue.append(child_id)
    return list(reversed(order))
def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _money(value: Decimal | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(value).quantize(_MONEY_QUANTIZER, rounding=ROUND_HALF_UP)


def _decimal_to_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(_money(value), "f")


def _fail(code: str, detail: str) -> None:
    raise ValueError(f"{code}: {detail}")
