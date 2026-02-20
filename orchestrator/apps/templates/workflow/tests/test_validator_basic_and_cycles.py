"""
Unit tests for DAGValidator class: basic validation and cycle detection.
"""

import pytest

from apps.templates.workflow.validator import DAGValidator
from apps.templates.workflow.models import (
    DAGStructure,
    WorkflowNode,
    WorkflowEdge,
)


# ========== Basic Validation Tests ==========


class TestBasicValidation:
    """Tests for basic DAG validation scenarios."""

    def test_empty_dag(self):
        """Test validation of empty DAG (caught by Pydantic min_length=1)."""
        # Pydantic validation prevents empty nodes list at schema level
        with pytest.raises(ValueError, match="at least 1 item"):
            DAGStructure(nodes=[], edges=[])

    def test_single_node_dag(self):
        """Test validation of DAG with single node."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id="only", name="Only Node", type="operation", template_id="test")
            ],
            edges=[]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert result.is_valid
        assert len(result.errors) == 0
        assert result.topological_order == ["only"]

    def test_valid_linear_dag(self):
        """Test validation of simple linear DAG (A → B → C)."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id="a", name="Node A", type="operation", template_id="op_a"),
                WorkflowNode(id="b", name="Node B", type="operation", template_id="op_b"),
                WorkflowNode(id="c", name="Node C", type="operation", template_id="op_c"),
            ],
            edges=[
                WorkflowEdge(from_node="a", to_node="b"),
                WorkflowEdge(from_node="b", to_node="c"),
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert result.is_valid
        assert len(result.errors) == 0
        assert result.topological_order == ["a", "b", "c"]
        assert result.metadata["total_nodes"] == 3
        assert result.metadata["total_edges"] == 2

    def test_valid_tree_structure(self):
        """Test validation of tree structure (A → B, A → C)."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id="root", name="Root", type="operation", template_id="root"),
                WorkflowNode(id="left", name="Left", type="operation", template_id="left"),
                WorkflowNode(id="right", name="Right", type="operation", template_id="right"),
            ],
            edges=[
                WorkflowEdge(from_node="root", to_node="left"),
                WorkflowEdge(from_node="root", to_node="right"),
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert result.is_valid
        assert result.topological_order[0] == "root"
        assert set(result.topological_order[1:]) == {"left", "right"}

    def test_valid_diamond_dag(self):
        """Test validation of diamond pattern (A → B, A → C, B → D, C → D)."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id="a", name="A", type="operation", template_id="a"),
                WorkflowNode(id="b", name="B", type="operation", template_id="b"),
                WorkflowNode(id="c", name="C", type="operation", template_id="c"),
                WorkflowNode(id="d", name="D", type="operation", template_id="d"),
            ],
            edges=[
                WorkflowEdge(from_node="a", to_node="b"),
                WorkflowEdge(from_node="a", to_node="c"),
                WorkflowEdge(from_node="b", to_node="d"),
                WorkflowEdge(from_node="c", to_node="d"),
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert result.is_valid
        assert result.topological_order[0] == "a"
        assert result.topological_order[-1] == "d"

    def test_duplicate_node_ids_detected(self):
        """Test that duplicate node IDs are caught by Pydantic."""
        # Pydantic validation happens at DAGStructure creation
        with pytest.raises(ValueError, match="unique"):
            DAGStructure(
                nodes=[
                    WorkflowNode(id="dup", name="First", type="operation", template_id="op1"),
                    WorkflowNode(id="dup", name="Second", type="operation", template_id="op2"),
                ],
                edges=[]
            )

    def test_invalid_edge_reference(self):
        """Test detection of edges referencing non-existent nodes."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id="a", name="Node A", type="operation", template_id="op_a"),
            ],
            edges=[
                WorkflowEdge(from_node="a", to_node="nonexistent"),
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert not result.is_valid
        assert any("non-existent" in e.message.lower() for e in result.errors)

    def test_self_loop_detected(self):
        """Test detection of self-referencing edges."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id="a", name="Node A", type="operation", template_id="op_a"),
            ],
            edges=[
                WorkflowEdge(from_node="a", to_node="a"),  # Self-loop
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert not result.is_valid
        assert any("self-loop" in e.message.lower() for e in result.errors)


# ========== Cycle Detection Tests ==========


class TestCycleDetection:
    """Tests for cycle detection using Kahn's algorithm."""

    def test_simple_cycle_two_nodes(self):
        """Test detection of simple cycle (A → B → A)."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id="a", name="A", type="operation", template_id="op"),
                WorkflowNode(id="b", name="B", type="operation", template_id="op"),
            ],
            edges=[
                WorkflowEdge(from_node="a", to_node="b"),
                WorkflowEdge(from_node="b", to_node="a"),  # Cycle
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert not result.is_valid
        assert any("cycle" in e.message.lower() for e in result.errors)
        assert result.topological_order is None

    def test_complex_cycle_three_nodes(self):
        """Test detection of cycle in 3-node DAG (A → B → C → A)."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id="a", name="A", type="operation", template_id="op"),
                WorkflowNode(id="b", name="B", type="operation", template_id="op"),
                WorkflowNode(id="c", name="C", type="operation", template_id="op"),
            ],
            edges=[
                WorkflowEdge(from_node="a", to_node="b"),
                WorkflowEdge(from_node="b", to_node="c"),
                WorkflowEdge(from_node="c", to_node="a"),  # Cycle
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert not result.is_valid
        assert any("cycle" in e.message.lower() for e in result.errors)

    def test_cycle_in_subgraph(self):
        """Test detection of cycle in part of larger DAG."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id="start", name="Start", type="operation", template_id="op"),
                WorkflowNode(id="a", name="A", type="operation", template_id="op"),
                WorkflowNode(id="b", name="B", type="operation", template_id="op"),
                WorkflowNode(id="c", name="C", type="operation", template_id="op"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="a"),
                WorkflowEdge(from_node="a", to_node="b"),
                WorkflowEdge(from_node="b", to_node="c"),
                WorkflowEdge(from_node="c", to_node="a"),  # Cycle: a → b → c → a
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert not result.is_valid
        assert any("cycle" in e.message.lower() for e in result.errors)

    def test_no_cycle_in_diamond(self):
        """Test that diamond pattern is correctly identified as acyclic."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id="a", name="A", type="operation", template_id="op"),
                WorkflowNode(id="b", name="B", type="operation", template_id="op"),
                WorkflowNode(id="c", name="C", type="operation", template_id="op"),
                WorkflowNode(id="d", name="D", type="operation", template_id="op"),
            ],
            edges=[
                WorkflowEdge(from_node="a", to_node="b"),
                WorkflowEdge(from_node="a", to_node="c"),
                WorkflowEdge(from_node="b", to_node="d"),
                WorkflowEdge(from_node="c", to_node="d"),
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert result.is_valid
        assert result.topological_order is not None
        assert result.topological_order[0] == "a"
        assert result.topological_order[-1] == "d"

    def test_no_cycle_in_fork_join(self):
        """Test fork-join pattern (A → B, A → C, B → D, C → D, D → E)."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id=f"n{i}", name=f"Node {i}", type="operation", template_id="op")
                for i in range(5)
            ],
            edges=[
                WorkflowEdge(from_node="n0", to_node="n1"),
                WorkflowEdge(from_node="n0", to_node="n2"),
                WorkflowEdge(from_node="n1", to_node="n3"),
                WorkflowEdge(from_node="n2", to_node="n3"),
                WorkflowEdge(from_node="n3", to_node="n4"),
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert result.is_valid
        assert len(result.topological_order) == 5

    def test_multiple_cycles(self):
        """Test detection when multiple cycles exist."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id=f"n{i}", name=f"Node {i}", type="operation", template_id="op")
                for i in range(6)
            ],
            edges=[
                # Cycle 1: n0 → n1 → n0
                WorkflowEdge(from_node="n0", to_node="n1"),
                WorkflowEdge(from_node="n1", to_node="n0"),
                # Cycle 2: n2 → n3 → n4 → n2
                WorkflowEdge(from_node="n2", to_node="n3"),
                WorkflowEdge(from_node="n3", to_node="n4"),
                WorkflowEdge(from_node="n4", to_node="n2"),
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert not result.is_valid
        assert any("cycle" in e.message.lower() for e in result.errors)

    def test_topological_order_correctness(self):
        """Test that topological order respects dependencies."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id=f"step{i}", name=f"Step {i}", type="operation", template_id="op")
                for i in range(1, 6)
            ],
            edges=[
                WorkflowEdge(from_node="step1", to_node="step2"),
                WorkflowEdge(from_node="step2", to_node="step3"),
                WorkflowEdge(from_node="step1", to_node="step4"),
                WorkflowEdge(from_node="step4", to_node="step5"),
                WorkflowEdge(from_node="step3", to_node="step5"),
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert result.is_valid
        order = result.topological_order

        # Check dependencies are respected
        assert order.index("step1") < order.index("step2")
        assert order.index("step2") < order.index("step3")
        assert order.index("step1") < order.index("step4")
        assert order.index("step3") < order.index("step5")
        assert order.index("step4") < order.index("step5")

