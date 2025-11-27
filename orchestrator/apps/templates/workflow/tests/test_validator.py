# orchestrator/apps/templates/workflow/tests/test_validator.py
"""
Unit tests for DAGValidator class.

Tests cover:
- Basic validation (empty DAG, single node, valid structures)
- Cycle detection (Kahn's algorithm correctness)
- Connectivity validation (BFS reachability)
- Node type validation
- Performance tests (large DAGs)
- Integration with WorkflowTemplate
"""

import pytest
from apps.templates.workflow.validator import (
    DAGValidator,
)
from apps.templates.workflow.models import (
    DAGStructure,
    WorkflowNode,
    WorkflowEdge,
    NodeConfig,
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


# ========== Connectivity Tests ==========

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


# ========== Node Type Validation Tests ==========

class TestNodeTypeValidation:
    """Tests for node type and configuration validation."""

    def test_valid_operation_node(self):
        """Test operation node with required template_id."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id="op", name="Operation", type="operation", template_id="required"),
            ],
            edges=[]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert result.is_valid

    def test_operation_node_missing_template_id(self):
        """Test that operation nodes without template_id are caught by Pydantic."""
        with pytest.raises(ValueError, match="template_id is required"):
            WorkflowNode(id="op", name="Operation", type="operation", template_id=None)

    def test_condition_node_validation(self):
        """Test condition node requires expression."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(
                    id="cond",
                    name="Condition",
                    type="condition",
                    config=NodeConfig(expression="{{ True }}")  # expression required
                ),
            ],
            edges=[]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert result.is_valid

    def test_parallel_node_requires_config(self):
        """Test parallel node requires parallel_config."""
        with pytest.raises(ValueError, match="parallel_config is required"):
            WorkflowNode(
                id="par",
                name="Parallel",
                type="parallel",
                config=NodeConfig(timeout_seconds=30)  # Missing parallel_config
            )

    def test_parallel_node_with_limit(self):
        """Test valid parallel node with parallel_config."""
        from apps.templates.workflow.models import ParallelConfig

        dag = DAGStructure(
            nodes=[
                WorkflowNode(
                    id="par",
                    name="Parallel",
                    type="parallel",
                    config=NodeConfig(timeout_seconds=30),
                    parallel_config=ParallelConfig(
                        parallel_nodes=["node1", "node2", "node3"],
                        wait_for="all",
                        timeout_seconds=30
                    )
                ),
            ],
            edges=[]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert result.is_valid

    def test_mixed_node_types(self):
        """Test DAG with different node types."""
        from apps.templates.workflow.models import ParallelConfig, LoopConfig

        dag = DAGStructure(
            nodes=[
                WorkflowNode(id="op", name="Op", type="operation", template_id="test"),
                WorkflowNode(
                    id="cond",
                    name="Cond",
                    type="condition",
                    config=NodeConfig(expression="{{ True }}")  # expression required
                ),
                WorkflowNode(
                    id="par",
                    name="Par",
                    type="parallel",
                    parallel_config=ParallelConfig(
                        parallel_nodes=["node1", "node2"],
                        wait_for="all"
                    )
                ),
                WorkflowNode(
                    id="loop",
                    name="Loop",
                    type="loop",
                    loop_config=LoopConfig(
                        mode="count",
                        count=5,
                        loop_node_id="op"
                    )
                ),
            ],
            edges=[
                WorkflowEdge(from_node="op", to_node="cond"),
                WorkflowEdge(from_node="cond", to_node="par"),
                WorkflowEdge(from_node="par", to_node="loop"),
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert result.is_valid


# ========== Performance Tests ==========

class TestPerformance:
    """Tests for DAGValidator performance on large DAGs."""

    def test_large_linear_dag_100_nodes(self):
        """Test performance on linear DAG with 100 nodes."""
        import time

        nodes = [
            WorkflowNode(id=f"n{i}", name=f"Node {i}", type="operation", template_id="op")
            for i in range(100)
        ]
        edges = [
            WorkflowEdge(from_node=f"n{i}", to_node=f"n{i+1}")
            for i in range(99)
        ]
        dag = DAGStructure(nodes=nodes, edges=edges)

        start = time.time()
        validator = DAGValidator(dag)
        result = validator.validate()
        duration = time.time() - start

        assert result.is_valid
        assert len(result.topological_order) == 100
        assert duration < 0.5  # Should complete in < 500ms

    def test_large_tree_dag_100_nodes(self):
        """Test performance on tree structure with 100 nodes."""
        import time

        # Binary tree structure
        nodes = [
            WorkflowNode(id=f"n{i}", name=f"Node {i}", type="operation", template_id="op")
            for i in range(100)
        ]
        edges = []
        for i in range(50):
            left = 2 * i + 1
            right = 2 * i + 2
            if left < 100:
                edges.append(WorkflowEdge(from_node=f"n{i}", to_node=f"n{left}"))
            if right < 100:
                edges.append(WorkflowEdge(from_node=f"n{i}", to_node=f"n{right}"))

        dag = DAGStructure(nodes=nodes, edges=edges)

        start = time.time()
        validator = DAGValidator(dag)
        result = validator.validate()
        duration = time.time() - start

        assert result.is_valid
        assert duration < 0.5  # O(V+E) should be fast

    def test_large_complex_dag_500_nodes(self):
        """Test performance on complex DAG with 500 nodes."""
        import time

        nodes = [
            WorkflowNode(id=f"n{i}", name=f"Node {i}", type="operation", template_id="op")
            for i in range(500)
        ]

        # Create complex structure (each node connects to next 3)
        edges = []
        for i in range(497):
            for j in range(1, 4):
                if i + j < 500:
                    edges.append(WorkflowEdge(from_node=f"n{i}", to_node=f"n{i+j}"))

        dag = DAGStructure(nodes=nodes, edges=edges)

        start = time.time()
        validator = DAGValidator(dag)
        result = validator.validate()
        duration = time.time() - start

        assert result.is_valid
        assert duration < 2.0  # Should handle 500 nodes in < 2s

    def test_deeply_nested_dag(self):
        """Test handling of deeply nested DAG (no stack overflow)."""
        # Create very deep linear chain
        depth = 1000
        nodes = [
            WorkflowNode(id=f"n{i}", name=f"Node {i}", type="operation", template_id="op")
            for i in range(depth)
        ]
        edges = [
            WorkflowEdge(from_node=f"n{i}", to_node=f"n{i+1}")
            for i in range(depth - 1)
        ]
        dag = DAGStructure(nodes=nodes, edges=edges)

        validator = DAGValidator(dag)
        result = validator.validate()

        # Should not crash with RecursionError
        assert result.is_valid
        assert len(result.topological_order) == depth


# ========== Integration Tests ==========

@pytest.mark.django_db
class TestDAGValidatorIntegration:
    """Integration tests with WorkflowTemplate model."""

    def test_workflow_template_uses_dag_validator(self, admin_user):
        """Test that WorkflowTemplate.validate() uses DAGValidator."""
        from apps.templates.workflow.models import WorkflowTemplate

        template = WorkflowTemplate.objects.create(
            name="Integration Test",
            dag_structure={
                "nodes": [
                    {"id": "a", "name": "A", "type": "operation", "template_id": "op"}
                ],
                "edges": []
            },
            created_by=admin_user
        )

        # Should not raise
        is_valid = template.validate()
        assert is_valid is True
        assert template.is_valid is True

    def test_workflow_template_validation_catches_cycle(self, admin_user):
        """Test WorkflowTemplate catches cycles via DAGValidator."""
        from apps.templates.workflow.models import WorkflowTemplate

        template = WorkflowTemplate.objects.create(
            name="Cyclic Workflow",
            dag_structure={
                "nodes": [
                    {"id": "a", "name": "A", "type": "operation", "template_id": "op"},
                    {"id": "b", "name": "B", "type": "operation", "template_id": "op"},
                ],
                "edges": [
                    {"from": "a", "to": "b"},
                    {"from": "b", "to": "a"},  # Cycle
                ]
            },
            created_by=admin_user
        )

        with pytest.raises(ValueError, match="validation failed"):
            template.validate()

        assert template.is_valid is False

    def test_validation_result_error_aggregation(self):
        """Test that ValidationResult aggregates multiple errors."""
        # Invalid edge reference + missing template_id handled by Pydantic
        # Create manually constructed invalid DAG
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id="a", name="A", type="operation", template_id="op"),
                WorkflowNode(id="b", name="B", type="operation", template_id="op"),
            ],
            edges=[
                WorkflowEdge(from_node="a", to_node="nonexistent"),  # Invalid ref
                WorkflowEdge(from_node="b", to_node="b"),  # Self-loop
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert not result.is_valid
        # Should have multiple errors
        assert len(result.errors) >= 2

    def test_validation_result_metadata(self):
        """Test that ValidationResult includes useful metadata."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id=f"n{i}", name=f"Node {i}", type="operation", template_id="op")
                for i in range(5)
            ],
            edges=[
                WorkflowEdge(from_node="n0", to_node="n1"),
                WorkflowEdge(from_node="n0", to_node="n2"),
                WorkflowEdge(from_node="n1", to_node="n3"),
                WorkflowEdge(from_node="n2", to_node="n4"),
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert "total_nodes" in result.metadata
        assert "total_edges" in result.metadata
        assert result.metadata["total_nodes"] == 5
        assert result.metadata["total_edges"] == 4


# ========== Edge Cases ==========

class TestEdgeCases:
    """Tests for edge cases and corner scenarios."""

    def test_no_start_nodes(self):
        """Test DAG where all nodes have incoming edges (cycle or invalid)."""
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
        # Should have cycle error

    def test_no_end_nodes(self):
        """Test DAG where all nodes have outgoing edges."""
        # This would require a cycle, so similar to above
        # Single node with self-loop
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id="a", name="A", type="operation", template_id="op"),
            ],
            edges=[
                WorkflowEdge(from_node="a", to_node="a"),  # Self-loop
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert not result.is_valid

    def test_very_wide_dag(self):
        """Test DAG with one node connecting to many (fan-out)."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id="start", name="Start", type="operation", template_id="op"),
                *[
                    WorkflowNode(id=f"end{i}", name=f"End {i}", type="operation", template_id="op")
                    for i in range(50)
                ]
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node=f"end{i}")
                for i in range(50)
            ]
        )
        validator = DAGValidator(dag)
        result = validator.validate()

        assert result.is_valid
        assert result.topological_order[0] == "start"

    def test_component_count(self):
        """Test that _count_components() returns correct count."""
        dag = DAGStructure(
            nodes=[
                # Component 1: a → b
                WorkflowNode(id="a", name="A", type="operation", template_id="op"),
                WorkflowNode(id="b", name="B", type="operation", template_id="op"),
                # Component 2: c → d
                WorkflowNode(id="c", name="C", type="operation", template_id="op"),
                WorkflowNode(id="d", name="D", type="operation", template_id="op"),
            ],
            edges=[
                WorkflowEdge(from_node="a", to_node="b"),
                WorkflowEdge(from_node="c", to_node="d"),
            ]
        )
        validator = DAGValidator(dag)
        component_count = validator._count_components()

        assert component_count == 2
