"""
Unit tests for DAGValidator class: node-type validation and performance checks.
"""

import pytest

from apps.templates.workflow.validator import DAGValidator
from apps.templates.workflow.models import DAGStructure, NodeConfig, WorkflowEdge, WorkflowNode


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
        """Test that operation nodes require template_id or operation_ref."""
        with pytest.raises(ValueError, match="template_id or operation_ref is required"):
            WorkflowNode(id="op", name="Operation", type="operation", template_id=None)

    def test_operation_node_template_id_synthesizes_operation_ref(self):
        """Test legacy template_id-only node gets deterministic operation_ref."""
        node = WorkflowNode(
            id="op",
            name="Operation",
            type="operation",
            template_id="tpl-legacy",
        )
        assert node.operation_ref is not None
        assert node.operation_ref.alias == "tpl-legacy"
        assert node.operation_ref.binding_mode == "alias_latest"

    def test_operation_node_accepts_operation_ref_alias_latest(self):
        """Test operation node may use operation_ref without explicit template_id."""
        node = WorkflowNode(
            id="op",
            name="Operation",
            type="operation",
            operation_ref={"alias": "tpl-test", "binding_mode": "alias_latest"},
        )
        # Runtime compatibility shim mirrors alias into legacy template_id.
        assert node.template_id == "tpl-test"
        assert node.operation_ref is not None
        assert node.operation_ref.binding_mode == "alias_latest"

    def test_operation_node_rejects_mismatched_template_and_operation_ref(self):
        """Test both bindings must reference the same alias."""
        with pytest.raises(ValueError, match="template_id must match operation_ref.alias"):
            WorkflowNode(
                id="op",
                name="Operation",
                type="operation",
                template_id="tpl-a",
                operation_ref={"alias": "tpl-b", "binding_mode": "alias_latest"},
            )

    def test_operation_ref_pinned_requires_exposure_fields(self):
        """Test pinned_exposure rejects incomplete operation_ref."""
        with pytest.raises(ValueError, match="template_exposure_id is required"):
            WorkflowNode(
                id="op",
                name="Operation",
                type="operation",
                operation_ref={"alias": "tpl-test", "binding_mode": "pinned_exposure"},
            )

    def test_non_operation_node_rejects_operation_ref(self):
        """Test operation_ref is forbidden for non-operation nodes."""
        with pytest.raises(ValueError, match="operation_ref must be None"):
            WorkflowNode(
                id="cond",
                name="Condition",
                type="condition",
                config=NodeConfig(expression="{{ True }}"),
                operation_ref={"alias": "tpl-test", "binding_mode": "alias_latest"},
            )

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


class TestPerformance:
    """Tests for DAGValidator performance on large DAGs."""

    def test_large_linear_dag_100_nodes(self):
        """Test performance on linear DAG with 100 nodes."""
        import time

        nodes = [
            WorkflowNode(id=f"n{i}", name=f"Node {i}", type="operation", template_id="op")
            for i in range(100)
        ]
        edges = [WorkflowEdge(from_node=f"n{i}", to_node=f"n{i+1}") for i in range(99)]
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
        edges = [WorkflowEdge(from_node=f"n{i}", to_node=f"n{i+1}") for i in range(depth - 1)]
        dag = DAGStructure(nodes=nodes, edges=edges)

        validator = DAGValidator(dag)
        result = validator.validate()

        # Should not crash with RecursionError
        assert result.is_valid
        assert len(result.topological_order) == depth
