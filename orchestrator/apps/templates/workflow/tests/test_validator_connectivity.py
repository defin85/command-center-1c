"""
Unit tests for DAGValidator class: connectivity validation.
"""

import pytest

from apps.templates.workflow.validator import DAGValidator
from apps.templates.workflow.models import DAGStructure, WorkflowEdge, WorkflowNode


class TestConnectivity:
    """Tests for connectivity validation using BFS."""

    def test_fully_connected_dag(self):
        """Test DAG where all nodes are reachable from start."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id=f"n{i}", name=f"Node {i}", type="operation", template_id="op")
                for i in range(4)
            ],
            edges=[
                WorkflowEdge(from_node="n0", to_node="n1"),
                WorkflowEdge(from_node="n1", to_node="n2"),
                WorkflowEdge(from_node="n2", to_node="n3"),
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert result.is_valid
        assert len(result.errors) == 0

    def test_unreachable_nodes_detected(self):
        """Test detection of unreachable nodes."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id="start", name="Start", type="operation", template_id="op"),
                WorkflowNode(id="end", name="End", type="operation", template_id="op"),
                WorkflowNode(id="orphan", name="Orphan", type="operation", template_id="op"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="end"),
                # orphan has no incoming edges - will be isolated
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert not result.is_valid  # Isolated node is ERROR
        assert any("isolated" in e.message.lower() for e in result.errors)
        assert "orphan" in [node_id for error in result.errors for node_id in error.node_ids]

    def test_multiple_start_nodes(self):
        """Test DAG with multiple start nodes."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id="start1", name="Start 1", type="operation", template_id="op"),
                WorkflowNode(id="start2", name="Start 2", type="operation", template_id="op"),
                WorkflowNode(id="end", name="End", type="operation", template_id="op"),
            ],
            edges=[
                WorkflowEdge(from_node="start1", to_node="end"),
                WorkflowEdge(from_node="start2", to_node="end"),
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert result.is_valid  # Multiple starts is valid
        # Should have info/warning about multiple starts
        assert len(result.warnings) > 0 or len(result.info) > 0

    def test_multiple_end_nodes(self):
        """Test DAG with multiple end nodes."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id="start", name="Start", type="operation", template_id="op"),
                WorkflowNode(id="end1", name="End 1", type="operation", template_id="op"),
                WorkflowNode(id="end2", name="End 2", type="operation", template_id="op"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="end1"),
                WorkflowEdge(from_node="start", to_node="end2"),
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert result.is_valid  # Multiple ends is valid
        # Should have info/warning about multiple ends
        assert len(result.warnings) > 0 or len(result.info) > 0

    def test_isolated_node_detected(self):
        """Test detection of completely isolated node (0 in-degree, 0 out-degree)."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id="connected1", name="C1", type="operation", template_id="op"),
                WorkflowNode(id="connected2", name="C2", type="operation", template_id="op"),
                WorkflowNode(id="isolated", name="Isolated", type="operation", template_id="op"),
            ],
            edges=[
                WorkflowEdge(from_node="connected1", to_node="connected2"),
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert not result.is_valid
        assert any("isolated" in e.message.lower() for e in result.errors)

    def test_disconnected_components(self):
        """Test detection of disconnected components."""
        dag = DAGStructure(
            nodes=[
                # Component 1
                WorkflowNode(id="a1", name="A1", type="operation", template_id="op"),
                WorkflowNode(id="a2", name="A2", type="operation", template_id="op"),
                # Component 2
                WorkflowNode(id="b1", name="B1", type="operation", template_id="op"),
                WorkflowNode(id="b2", name="B2", type="operation", template_id="op"),
            ],
            edges=[
                # Component 1
                WorkflowEdge(from_node="a1", to_node="a2"),
                # Component 2
                WorkflowEdge(from_node="b1", to_node="b2"),
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        # Should detect unreachable nodes or disconnected components
        assert not result.is_valid or len(result.warnings) > 0

