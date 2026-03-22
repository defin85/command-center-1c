from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from django.core.exceptions import ValidationError

from .validators import validate_pool_graph

TOPOLOGY_TEMPLATE_REVISION_CONTRACT_VERSION = "topology_template_revision.v1"
POOL_TOPOLOGY_TEMPLATE_INSTANTIATION_METADATA_KEY = "topology_template_instantiation"


def normalize_topology_template_revision_payload(
    *,
    nodes: Any,
    edges: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(nodes, list) or not nodes:
        raise ValidationError("Topology template revision must contain at least one node.")
    if edges is None:
        edges = []
    if not isinstance(edges, list):
        raise ValidationError("Topology template revision edges must be a list.")

    normalized_nodes: list[dict[str, Any]] = []
    slot_keys: set[str] = set()
    root_slot_key: str | None = None
    for index, raw_node in enumerate(nodes):
        if not isinstance(raw_node, Mapping):
            raise ValidationError(f"Topology template node #{index + 1} must be an object.")
        slot_key = _normalize_slot_key(
            raw_node.get("slot_key"),
            field_name=f"nodes[{index}].slot_key",
        )
        if slot_key in slot_keys:
            raise ValidationError(f"Duplicate topology template slot_key '{slot_key}'.")
        slot_keys.add(slot_key)
        label = _normalize_optional_string(raw_node.get("label"))
        metadata = _normalize_metadata(raw_node.get("metadata"), field_name=f"nodes[{index}].metadata")
        is_root = bool(raw_node.get("is_root", False))
        if is_root:
            if root_slot_key is not None:
                raise ValidationError("Topology template revision must contain exactly one root node.")
            root_slot_key = slot_key
        normalized_nodes.append(
            {
                "slot_key": slot_key,
                "label": label,
                "is_root": is_root,
                "metadata": metadata,
            }
        )

    if root_slot_key is None:
        raise ValidationError("Topology template revision must contain exactly one root node.")

    normalized_edges: list[dict[str, Any]] = []
    edge_pairs: list[tuple[str, str]] = []
    seen_edges: set[tuple[str, str]] = set()
    for index, raw_edge in enumerate(edges):
        if not isinstance(raw_edge, Mapping):
            raise ValidationError(f"Topology template edge #{index + 1} must be an object.")
        parent_slot_key = _normalize_slot_key(
            raw_edge.get("parent_slot_key"),
            field_name=f"edges[{index}].parent_slot_key",
        )
        child_slot_key = _normalize_slot_key(
            raw_edge.get("child_slot_key"),
            field_name=f"edges[{index}].child_slot_key",
        )
        if parent_slot_key not in slot_keys or child_slot_key not in slot_keys:
            raise ValidationError(
                f"Topology template edge {parent_slot_key}->{child_slot_key} must reference declared slot_key values."
            )
        edge_pair = (parent_slot_key, child_slot_key)
        if edge_pair in seen_edges:
            raise ValidationError(
                f"Duplicate topology template edge '{parent_slot_key}->{child_slot_key}'."
            )
        seen_edges.add(edge_pair)
        edge_pairs.append(edge_pair)
        weight = _normalize_decimal_string(raw_edge.get("weight"), default="1")
        min_amount = _normalize_optional_decimal_string(raw_edge.get("min_amount"))
        max_amount = _normalize_optional_decimal_string(raw_edge.get("max_amount"))
        if min_amount is not None and max_amount is not None and Decimal(max_amount) < Decimal(min_amount):
            raise ValidationError(
                f"Topology template edge {parent_slot_key}->{child_slot_key} has max_amount below min_amount."
            )
        metadata = _normalize_metadata(raw_edge.get("metadata"), field_name=f"edges[{index}].metadata")
        default_document_policy_key = _normalize_optional_string(raw_edge.get("document_policy_key"))
        normalized_edges.append(
            {
                "parent_slot_key": parent_slot_key,
                "child_slot_key": child_slot_key,
                "weight": weight,
                "min_amount": min_amount,
                "max_amount": max_amount,
                "document_policy_key": default_document_policy_key,
                "metadata": metadata,
            }
        )

    graph_snapshot = validate_pool_graph(
        node_ids=[node["slot_key"] for node in normalized_nodes],
        edge_pairs=edge_pairs,
    )
    if graph_snapshot.root_id != root_slot_key:
        raise ValidationError(
            "Topology template root node must match the graph root derived from edge topology."
        )

    return normalized_nodes, normalized_edges


def normalize_topology_template_slot_assignments(
    *,
    slot_assignments: Any,
    expected_slot_keys: list[str],
) -> list[dict[str, str]]:
    if not isinstance(slot_assignments, list) or not slot_assignments:
        raise ValidationError("slot_assignments must contain one organization mapping per template slot.")

    expected_set = set(expected_slot_keys)
    normalized: list[dict[str, str]] = []
    seen_slot_keys: set[str] = set()
    seen_organization_ids: set[str] = set()
    for index, raw_assignment in enumerate(slot_assignments):
        if not isinstance(raw_assignment, Mapping):
            raise ValidationError(f"slot_assignments[{index}] must be an object.")
        slot_key = _normalize_slot_key(
            raw_assignment.get("slot_key"),
            field_name=f"slot_assignments[{index}].slot_key",
        )
        organization_id = _normalize_required_string(
            raw_assignment.get("organization_id"),
            field_name=f"slot_assignments[{index}].organization_id",
        )
        if slot_key not in expected_set:
            raise ValidationError(f"Unknown topology template slot_key '{slot_key}' in slot_assignments.")
        if slot_key in seen_slot_keys:
            raise ValidationError(f"Duplicate slot assignment for slot_key '{slot_key}'.")
        if organization_id in seen_organization_ids:
            raise ValidationError("slot_assignments must reference distinct organization_id values.")
        seen_slot_keys.add(slot_key)
        seen_organization_ids.add(organization_id)
        normalized.append(
            {
                "slot_key": slot_key,
                "organization_id": organization_id,
            }
        )

    missing = [slot_key for slot_key in expected_slot_keys if slot_key not in seen_slot_keys]
    if missing:
        raise ValidationError(
            f"slot_assignments must cover every template slot. Missing: {', '.join(missing)}."
        )
    return normalized


def normalize_topology_template_edge_selector_overrides(
    *,
    edge_selector_overrides: Any,
    expected_edges: list[tuple[str, str]],
) -> list[dict[str, str]]:
    if edge_selector_overrides is None:
        edge_selector_overrides = []
    if not isinstance(edge_selector_overrides, list):
        raise ValidationError("edge_selector_overrides must be a list.")

    expected_set = set(expected_edges)
    normalized: list[dict[str, str]] = []
    seen_edges: set[tuple[str, str]] = set()
    for index, raw_override in enumerate(edge_selector_overrides):
        if not isinstance(raw_override, Mapping):
            raise ValidationError(f"edge_selector_overrides[{index}] must be an object.")
        parent_slot_key = _normalize_slot_key(
            raw_override.get("parent_slot_key"),
            field_name=f"edge_selector_overrides[{index}].parent_slot_key",
        )
        child_slot_key = _normalize_slot_key(
            raw_override.get("child_slot_key"),
            field_name=f"edge_selector_overrides[{index}].child_slot_key",
        )
        edge_ref = (parent_slot_key, child_slot_key)
        if edge_ref not in expected_set:
            raise ValidationError(
                f"Unknown topology template edge '{parent_slot_key}->{child_slot_key}' in edge_selector_overrides."
            )
        if edge_ref in seen_edges:
            raise ValidationError(
                f"Duplicate selector override for edge '{parent_slot_key}->{child_slot_key}'."
            )
        seen_edges.add(edge_ref)
        normalized.append(
            {
                "parent_slot_key": parent_slot_key,
                "child_slot_key": child_slot_key,
                "document_policy_key": _normalize_required_string(
                    raw_override.get("document_policy_key"),
                    field_name=f"edge_selector_overrides[{index}].document_policy_key",
                ),
            }
        )
    return normalized


def _normalize_slot_key(value: Any, *, field_name: str) -> str:
    slot_key = _normalize_required_string(value, field_name=field_name).lower()
    if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for character in slot_key):
        raise ValidationError(f"{field_name} must contain only lowercase letters, digits, '_' or '-'.")
    return slot_key


def _normalize_required_string(value: Any, *, field_name: str) -> str:
    normalized = _normalize_optional_string(value)
    if not normalized:
        raise ValidationError(f"{field_name} is required.")
    return normalized


def _normalize_optional_string(value: Any) -> str | None:
    token = str(value or "").strip()
    return token or None


def _normalize_metadata(value: Any, *, field_name: str) -> dict[str, Any]:
    if value is None or value == "":
        return {}
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field_name} must be an object.")
    return dict(value)


def _normalize_decimal_string(value: Any, *, default: str) -> str:
    candidate = default if value in {None, ""} else str(value).strip()
    try:
        normalized = Decimal(candidate)
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("Topology template edge decimal fields must be valid numbers.") from exc
    if normalized <= 0:
        raise ValidationError("Topology template edge weight must be greater than zero.")
    return format(normalized, "f")


def _normalize_optional_decimal_string(value: Any) -> str | None:
    if value in {None, ""}:
        return None
    try:
        normalized = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("Topology template edge amount bounds must be valid numbers.") from exc
    return format(normalized, "f")
