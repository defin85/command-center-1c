from __future__ import annotations

import random
from collections import defaultdict, deque
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from django.core.exceptions import ValidationError

from .validators import validate_pool_graph


@dataclass(frozen=True)
class DistributionEdge:
    parent_id: str
    child_id: str
    weight: Decimal
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None


@dataclass(frozen=True)
class TopDownDistributionResult:
    edge_allocations: dict[tuple[str, str], Decimal]
    node_totals: dict[str, Decimal]


def distribute_top_down(
    total_amount: Decimal,
    root_node_id: str,
    edges: Iterable[DistributionEdge],
    seed: int | str,
    scale: int = 2,
) -> TopDownDistributionResult:
    edge_list = list(edges)
    node_ids = {root_node_id}
    edge_pairs: list[tuple[str, str]] = []
    for edge in edge_list:
        node_ids.add(edge.parent_id)
        node_ids.add(edge.child_id)
        edge_pairs.append((edge.parent_id, edge.child_id))

    validate_pool_graph(node_ids=list(node_ids), edge_pairs=edge_pairs)
    quantizer = Decimal(10) ** (-scale)
    total_amount = total_amount.quantize(quantizer, rounding=ROUND_HALF_UP)
    if total_amount < Decimal("0"):
        raise ValidationError("Total amount must be non-negative.")

    rng = random.Random(str(seed))
    edges_by_parent: dict[str, list[DistributionEdge]] = defaultdict(list)
    for edge in edge_list:
        edges_by_parent[edge.parent_id].append(edge)

    node_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    node_totals[root_node_id] = total_amount
    edge_allocations: dict[tuple[str, str], Decimal] = {}

    for parent_id in _topological_order(root_node_id=root_node_id, edge_pairs=edge_pairs):
        parent_total = node_totals[parent_id].quantize(quantizer, rounding=ROUND_HALF_UP)
        child_edges = edges_by_parent.get(parent_id, [])
        if not child_edges:
            continue

        split = _distribute_parent_to_children(
            total_amount=parent_total,
            edges=child_edges,
            rng=rng,
            scale=scale,
        )
        distributed_total = Decimal("0")
        for edge, amount in split:
            key = (edge.parent_id, edge.child_id)
            edge_allocations[key] = edge_allocations.get(key, Decimal("0")) + amount
            node_totals[edge.child_id] += amount
            distributed_total += amount

        if distributed_total != parent_total:
            raise ValidationError("Top-down split does not preserve parent balance.")

    return TopDownDistributionResult(
        edge_allocations=edge_allocations,
        node_totals=dict(node_totals),
    )


def _distribute_parent_to_children(
    total_amount: Decimal,
    edges: list[DistributionEdge],
    rng: random.Random,
    scale: int,
) -> list[tuple[DistributionEdge, Decimal]]:
    if not edges:
        return []

    factor = Decimal(10) ** scale
    total_units = int((total_amount * factor).to_integral_value(rounding=ROUND_HALF_UP))
    min_units = [_to_units(edge.min_amount or Decimal("0"), scale=scale) for edge in edges]
    max_units = [
        _to_units(edge.max_amount, scale=scale) if edge.max_amount is not None else float("inf")
        for edge in edges
    ]
    if sum(min_units) > total_units:
        raise ValidationError("Edge min constraints exceed available amount for parent.")

    allocations = list(min_units)
    remaining = total_units - sum(allocations)
    capacity = [
        (max_units[idx] - allocations[idx]) if max_units[idx] != float("inf") else float("inf")
        for idx in range(len(edges))
    ]
    weights = [_effective_weight(edge.weight, rng) for edge in edges]
    if any(weight <= Decimal("0") for weight in weights):
        raise ValidationError("Edge weight must be positive.")

    weights_sum = sum(weights)
    if weights_sum <= Decimal("0"):
        raise ValidationError("Edge weights sum must be positive.")

    for idx in range(len(edges) - 1):
        if remaining <= 0:
            break
        if capacity[idx] == 0:
            continue

        desired = int((Decimal(remaining) * weights[idx] / weights_sum).to_integral_value(rounding=ROUND_HALF_UP))
        desired = max(desired, 0)
        desired = min(desired, remaining)
        if capacity[idx] != float("inf"):
            desired = min(desired, int(capacity[idx]))
        allocations[idx] += desired
        remaining -= desired
        if capacity[idx] != float("inf"):
            capacity[idx] -= desired
        weights_sum -= weights[idx]
        if weights_sum <= Decimal("0"):
            break

    last_idx = len(edges) - 1
    if remaining > 0:
        if capacity[last_idx] != float("inf"):
            take = min(remaining, int(capacity[last_idx]))
            allocations[last_idx] += take
            remaining -= take
            capacity[last_idx] -= take
        else:
            allocations[last_idx] += remaining
            remaining = 0

    if remaining > 0:
        for idx in range(len(edges) - 2, -1, -1):
            if remaining <= 0:
                break
            if capacity[idx] in (0, float("inf")):
                continue
            take = min(remaining, int(capacity[idx]))
            allocations[idx] += take
            capacity[idx] -= take
            remaining -= take

    if remaining > 0:
        for idx in range(len(edges) - 2, -1, -1):
            if remaining <= 0:
                break
            if capacity[idx] != float("inf"):
                continue
            allocations[idx] += remaining
            remaining = 0

    if remaining > 0:
        raise ValidationError("Edge max constraints do not allow distributing full parent amount.")

    quantizer = Decimal(10) ** (-scale)
    result: list[tuple[DistributionEdge, Decimal]] = []
    for idx, edge in enumerate(edges):
        amount = (Decimal(allocations[idx]) / factor).quantize(quantizer, rounding=ROUND_HALF_UP)
        result.append((edge, amount))
    return result


def _effective_weight(weight: Decimal, rng: random.Random) -> Decimal:
    jitter = Decimal(str(1 + (rng.random() - 0.5) / 10_000))
    return Decimal(weight) * jitter


def _to_units(amount: Decimal | None, scale: int) -> int:
    if amount is None:
        return 0
    factor = Decimal(10) ** scale
    return int((Decimal(amount) * factor).to_integral_value(rounding=ROUND_HALF_UP))


def _topological_order(root_node_id: str, edge_pairs: list[tuple[str, str]]) -> list[str]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = defaultdict(int)
    nodes: set[str] = {root_node_id}

    for parent_id, child_id in edge_pairs:
        nodes.add(parent_id)
        nodes.add(child_id)
        adjacency[parent_id].append(child_id)
        in_degree[child_id] += 1
        in_degree.setdefault(parent_id, in_degree.get(parent_id, 0))

    queue: deque[str] = deque([root_node_id])
    seen: set[str] = set()
    order: list[str] = []

    while queue:
        node_id = queue.popleft()
        if node_id in seen:
            continue
        seen.add(node_id)
        order.append(node_id)

        for child_id in adjacency.get(node_id, []):
            in_degree[child_id] -= 1
            if in_degree[child_id] == 0:
                queue.append(child_id)

    if len(order) != len(nodes):
        raise ValidationError("Topological ordering failed because graph is not a DAG.")
    return order
