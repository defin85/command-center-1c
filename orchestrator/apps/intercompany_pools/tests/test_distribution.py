from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.intercompany_pools.distribution import DistributionEdge, distribute_top_down


def test_distribute_top_down_is_deterministic_for_same_seed() -> None:
    edges = [
        DistributionEdge(parent_id="root", child_id="a", weight=Decimal("1")),
        DistributionEdge(parent_id="root", child_id="b", weight=Decimal("1")),
        DistributionEdge(parent_id="root", child_id="c", weight=Decimal("1")),
    ]

    first = distribute_top_down(
        total_amount=Decimal("100.00"),
        root_node_id="root",
        edges=edges,
        seed=42,
    )
    second = distribute_top_down(
        total_amount=Decimal("100.00"),
        root_node_id="root",
        edges=edges,
        seed=42,
    )

    assert first.edge_allocations == second.edge_allocations


def test_distribute_top_down_respects_min_max_constraints() -> None:
    result = distribute_top_down(
        total_amount=Decimal("100.00"),
        root_node_id="root",
        edges=[
            DistributionEdge(
                parent_id="root",
                child_id="a",
                weight=Decimal("1"),
                min_amount=Decimal("40.00"),
                max_amount=Decimal("40.00"),
            ),
            DistributionEdge(
                parent_id="root",
                child_id="b",
                weight=Decimal("1"),
                min_amount=Decimal("10.00"),
            ),
        ],
        seed=1,
    )

    assert result.edge_allocations[("root", "a")] == Decimal("40.00")
    assert result.edge_allocations[("root", "b")] == Decimal("60.00")


def test_distribute_top_down_puts_rounding_remainder_to_last_child() -> None:
    result = distribute_top_down(
        total_amount=Decimal("100.00"),
        root_node_id="root",
        edges=[
            DistributionEdge(parent_id="root", child_id="a", weight=Decimal("1")),
            DistributionEdge(parent_id="root", child_id="b", weight=Decimal("1")),
            DistributionEdge(parent_id="root", child_id="c", weight=Decimal("1")),
        ],
        seed=999,
    )

    assert result.edge_allocations[("root", "a")] == Decimal("33.33")
    assert result.edge_allocations[("root", "b")] == Decimal("33.33")
    assert result.edge_allocations[("root", "c")] == Decimal("33.34")


def test_distribute_top_down_fails_when_max_constraints_insufficient() -> None:
    with pytest.raises(ValidationError, match="max constraints"):
        distribute_top_down(
            total_amount=Decimal("10.00"),
            root_node_id="root",
            edges=[
                DistributionEdge(
                    parent_id="root",
                    child_id="a",
                    weight=Decimal("1"),
                    max_amount=Decimal("3.00"),
                ),
                DistributionEdge(
                    parent_id="root",
                    child_id="b",
                    weight=Decimal("1"),
                    max_amount=Decimal("3.00"),
                ),
            ],
            seed=0,
        )
