"""
Unit tests for DAGValidator class: integration and edge cases.
"""

import pytest

from apps.templates.workflow.validator import DAGValidator
from apps.templates.workflow.models import DAGStructure, WorkflowEdge, WorkflowNode


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

