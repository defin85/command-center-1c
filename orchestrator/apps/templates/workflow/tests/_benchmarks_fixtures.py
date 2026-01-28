import time
from typing import Any, Dict
from unittest.mock import patch

import pytest

from apps.templates.workflow.engine import WorkflowEngine
from apps.templates.workflow.models import (
    WorkflowTemplate,
    WorkflowExecution,
    WorkflowNode,
    WorkflowEdge,
    DAGStructure,
    NodeConfig,
)
from apps.templates.workflow.handlers import (
    NodeHandlerFactory,
    NodeExecutionMode,
    NodeExecutionResult,
    BaseNodeHandler,
)


class MockHandler(BaseNodeHandler):
    """Mock handler that simulates fast execution."""

    def __init__(self, delay: float = 0.001):
        """Initialize with configurable delay."""
        self.delay = delay

    def execute(
        self,
        node: WorkflowNode,
        context: Dict[str, Any],
        execution: WorkflowExecution,
        mode: NodeExecutionMode = NodeExecutionMode.SYNC,
    ) -> NodeExecutionResult:
        """Execute mock node with minimal delay."""
        # Simulate minimal processing time
        time.sleep(self.delay)
        return NodeExecutionResult(
            success=True,
            output={"node_id": node.id, "processed": True},
            error=None,
            mode=NodeExecutionMode.SYNC,
            duration_seconds=self.delay,
        )


@pytest.fixture
def mock_handler():
    """Create mock handler with minimal delay."""
    return MockHandler(delay=0.001)


@pytest.fixture
def mock_handler_factory(mock_handler):
    """Patch NodeHandlerFactory to return mock handler."""
    with patch.object(NodeHandlerFactory, 'get_handler', return_value=mock_handler):
        yield mock_handler


@pytest.fixture
def admin_user(db):
    """Create admin user for benchmarks."""
    from django.contrib.auth.models import User

    User.objects.filter(username='benchadmin').delete()
    return User.objects.create_user(
        username='benchadmin',
        email='bench@test.com',
        password='benchpass',
        is_staff=True
    )


@pytest.fixture
def simple_dag() -> DAGStructure:
    """Create simple 2-node sequential workflow DAG."""
    return DAGStructure(
        nodes=[
            WorkflowNode(
                id="start",
                name="Start Node",
                type="operation",
                template_id="mock_template",
                config=NodeConfig(timeout_seconds=30)
            ),
            WorkflowNode(
                id="end",
                name="End Node",
                type="operation",
                template_id="mock_template",
                config=NodeConfig(timeout_seconds=30)
            ),
        ],
        edges=[
            WorkflowEdge(from_node="start", to_node="end"),
        ]
    )


@pytest.fixture
def three_node_dag() -> DAGStructure:
    """Create 3-node sequential workflow DAG."""
    return DAGStructure(
        nodes=[
            WorkflowNode(
                id="step1",
                name="Step 1",
                type="operation",
                template_id="mock_template",
                config=NodeConfig(timeout_seconds=30)
            ),
            WorkflowNode(
                id="step2",
                name="Step 2",
                type="operation",
                template_id="mock_template",
                config=NodeConfig(timeout_seconds=30)
            ),
            WorkflowNode(
                id="step3",
                name="Step 3",
                type="operation",
                template_id="mock_template",
                config=NodeConfig(timeout_seconds=30)
            ),
        ],
        edges=[
            WorkflowEdge(from_node="step1", to_node="step2"),
            WorkflowEdge(from_node="step2", to_node="step3"),
        ]
    )


@pytest.fixture
def complex_dag() -> DAGStructure:
    """Create complex 12-node workflow with parallel branches and conditionals."""
    return DAGStructure(
        nodes=[
            # Start node
            WorkflowNode(
                id="start",
                name="Start",
                type="operation",
                template_id="mock_template",
                config=NodeConfig(timeout_seconds=30)
            ),
            # Condition node
            WorkflowNode(
                id="check",
                name="Check Condition",
                type="condition",
                config=NodeConfig(expression="{{ True }}")
            ),
            # Branch A (4 nodes)
            WorkflowNode(
                id="branch_a_1",
                name="Branch A Step 1",
                type="operation",
                template_id="mock_template",
                config=NodeConfig(timeout_seconds=30)
            ),
            WorkflowNode(
                id="branch_a_2",
                name="Branch A Step 2",
                type="operation",
                template_id="mock_template",
                config=NodeConfig(timeout_seconds=30)
            ),
            WorkflowNode(
                id="branch_a_3",
                name="Branch A Step 3",
                type="operation",
                template_id="mock_template",
                config=NodeConfig(timeout_seconds=30)
            ),
            WorkflowNode(
                id="branch_a_4",
                name="Branch A Step 4",
                type="operation",
                template_id="mock_template",
                config=NodeConfig(timeout_seconds=30)
            ),
            # Branch B (4 nodes)
            WorkflowNode(
                id="branch_b_1",
                name="Branch B Step 1",
                type="operation",
                template_id="mock_template",
                config=NodeConfig(timeout_seconds=30)
            ),
            WorkflowNode(
                id="branch_b_2",
                name="Branch B Step 2",
                type="operation",
                template_id="mock_template",
                config=NodeConfig(timeout_seconds=30)
            ),
            WorkflowNode(
                id="branch_b_3",
                name="Branch B Step 3",
                type="operation",
                template_id="mock_template",
                config=NodeConfig(timeout_seconds=30)
            ),
            WorkflowNode(
                id="branch_b_4",
                name="Branch B Step 4",
                type="operation",
                template_id="mock_template",
                config=NodeConfig(timeout_seconds=30)
            ),
            # Merge node
            WorkflowNode(
                id="merge",
                name="Merge Branches",
                type="operation",
                template_id="mock_template",
                config=NodeConfig(timeout_seconds=30)
            ),
            # End node
            WorkflowNode(
                id="end",
                name="End",
                type="operation",
                template_id="mock_template",
                config=NodeConfig(timeout_seconds=30)
            ),
        ],
        edges=[
            # Start -> Check
            WorkflowEdge(from_node="start", to_node="check"),
            # Check -> Branches (conditional)
            WorkflowEdge(from_node="check", to_node="branch_a_1", condition="{{ True }}"),
            WorkflowEdge(from_node="check", to_node="branch_b_1", condition="{{ True }}"),
            # Branch A chain
            WorkflowEdge(from_node="branch_a_1", to_node="branch_a_2"),
            WorkflowEdge(from_node="branch_a_2", to_node="branch_a_3"),
            WorkflowEdge(from_node="branch_a_3", to_node="branch_a_4"),
            # Branch B chain
            WorkflowEdge(from_node="branch_b_1", to_node="branch_b_2"),
            WorkflowEdge(from_node="branch_b_2", to_node="branch_b_3"),
            WorkflowEdge(from_node="branch_b_3", to_node="branch_b_4"),
            # Merge
            WorkflowEdge(from_node="branch_a_4", to_node="merge"),
            WorkflowEdge(from_node="branch_b_4", to_node="merge"),
            # End
            WorkflowEdge(from_node="merge", to_node="end"),
        ]
    )


@pytest.fixture
def parallel_10_dag() -> DAGStructure:
    """Create DAG with 10 parallel nodes for concurrent execution benchmark."""
    nodes = [
        WorkflowNode(
            id="start",
            name="Start",
            type="operation",
            template_id="mock_template",
            config=NodeConfig(timeout_seconds=30)
        ),
    ]

    # Add 10 parallel nodes
    for i in range(10):
        nodes.append(
            WorkflowNode(
                id=f"parallel_{i}",
                name=f"Parallel Node {i}",
                type="operation",
                template_id="mock_template",
                config=NodeConfig(timeout_seconds=30)
            )
        )

    # Add end node
    nodes.append(
        WorkflowNode(
            id="end",
            name="End",
            type="operation",
            template_id="mock_template",
            config=NodeConfig(timeout_seconds=30)
        )
    )

    # Build edges: start -> parallel_0..9 -> end
    edges = []
    for i in range(10):
        edges.append(WorkflowEdge(from_node="start", to_node=f"parallel_{i}"))
        edges.append(WorkflowEdge(from_node=f"parallel_{i}", to_node="end"))

    return DAGStructure(nodes=nodes, edges=edges)


@pytest.fixture
def simple_workflow_template(db, admin_user, simple_dag):
    """Create simple workflow template for benchmarks."""
    template = WorkflowTemplate.objects.create(
        name="Benchmark Simple Workflow",
        workflow_type="benchmark",
        dag_structure=simple_dag.model_dump(),
        created_by=admin_user,
        is_valid=True,
        is_active=True
    )
    return template


@pytest.fixture
def three_node_template(db, admin_user, three_node_dag):
    """Create 3-node workflow template for benchmarks."""
    template = WorkflowTemplate.objects.create(
        name="Benchmark 3-Node Workflow",
        workflow_type="benchmark",
        dag_structure=three_node_dag.model_dump(),
        created_by=admin_user,
        is_valid=True,
        is_active=True
    )
    return template


@pytest.fixture
def complex_workflow_template(db, admin_user, complex_dag):
    """Create complex workflow template for benchmarks."""
    template = WorkflowTemplate.objects.create(
        name="Benchmark Complex Workflow",
        workflow_type="benchmark",
        dag_structure=complex_dag.model_dump(),
        created_by=admin_user,
        is_valid=True,
        is_active=True
    )
    return template


@pytest.fixture
def parallel_workflow_template(db, admin_user, parallel_10_dag):
    """Create parallel workflow template for benchmarks."""
    template = WorkflowTemplate.objects.create(
        name="Benchmark Parallel Workflow",
        workflow_type="benchmark",
        dag_structure=parallel_10_dag.model_dump(),
        created_by=admin_user,
        is_valid=True,
        is_active=True
    )
    return template


@pytest.fixture(autouse=True)
def reset_engine():
    """Reset WorkflowEngine singleton before each test."""
    WorkflowEngine.reset_singleton()
    yield
    WorkflowEngine.reset_singleton()

