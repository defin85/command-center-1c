from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import date

from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import OrganizationPool


@dataclass(frozen=True)
class GraphValidationSnapshot:
    root_id: str
    node_ids: tuple[str, ...]
    edge_pairs: tuple[tuple[str, str], ...]


def validate_pool_graph_for_date(pool: OrganizationPool, target_date: date) -> GraphValidationSnapshot:
    nodes = (
        pool.node_versions.filter(effective_from__lte=target_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=target_date))
        .values_list("id", flat=True)
    )
    edges = (
        pool.edge_versions.filter(effective_from__lte=target_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=target_date))
        .values_list("parent_node_id", "child_node_id")
    )
    return validate_pool_graph(list(nodes), list(edges))


def validate_pool_graph(
    node_ids: list[str],
    edge_pairs: list[tuple[str, str]],
) -> GraphValidationSnapshot:
    normalized_nodes = [str(node_id) for node_id in node_ids]
    normalized_edges = [(str(parent_id), str(child_id)) for parent_id, child_id in edge_pairs]

    if not normalized_nodes:
        raise ValidationError("Pool graph must contain at least one active node.")

    node_set = set(normalized_nodes)
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_set}
    in_degree: dict[str, int] = {node_id: 0 for node_id in node_set}
    parents: dict[str, set[str]] = {node_id: set() for node_id in node_set}

    for parent_id, child_id in normalized_edges:
        if parent_id not in node_set or child_id not in node_set:
            raise ValidationError("Pool graph edge references unknown node version.")

        adjacency[parent_id].append(child_id)
        in_degree[child_id] += 1
        parents[child_id].add(parent_id)

    roots = [node_id for node_id, degree in in_degree.items() if degree == 0]
    if len(roots) != 1:
        raise ValidationError(f"Pool graph must have exactly one root node, got {len(roots)}.")
    root_id = roots[0]

    node_level = _compute_node_level(root_id, adjacency)
    for node_id, parent_ids in parents.items():
        if len(parent_ids) <= 1:
            continue

        if node_level.get(node_id, 99) > 1:
            raise ValidationError(
                "Multi-parent links are allowed only for top-level nodes directly under root."
            )

    visited_count = _kahn_topological_sort_count(in_degree, adjacency)
    if visited_count != len(node_set):
        raise ValidationError("Pool graph must be acyclic (DAG).")

    return GraphValidationSnapshot(
        root_id=root_id,
        node_ids=tuple(sorted(node_set)),
        edge_pairs=tuple(normalized_edges),
    )


def _compute_node_level(root_id: str, adjacency: dict[str, list[str]]) -> dict[str, int]:
    levels: dict[str, int] = {root_id: 0}
    queue: deque[str] = deque([root_id])

    while queue:
        node_id = queue.popleft()
        for child_id in adjacency.get(node_id, []):
            candidate_level = levels[node_id] + 1
            current_level = levels.get(child_id)
            if current_level is None or candidate_level < current_level:
                levels[child_id] = candidate_level
                queue.append(child_id)

    return levels


def _kahn_topological_sort_count(
    in_degree: dict[str, int],
    adjacency: dict[str, list[str]],
) -> int:
    degree = dict(in_degree)
    queue: deque[str] = deque(node_id for node_id, d in degree.items() if d == 0)
    visited = 0

    while queue:
        node_id = queue.popleft()
        visited += 1

        for child_id in adjacency.get(node_id, []):
            degree[child_id] -= 1
            if degree[child_id] == 0:
                queue.append(child_id)

    return visited
