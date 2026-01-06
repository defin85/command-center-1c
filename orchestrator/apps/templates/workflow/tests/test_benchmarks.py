"""
Performance benchmarks for Workflow Engine.
Uses pytest-benchmark for measuring execution time.

Run with:
    pytest apps/templates/workflow/tests/test_benchmarks.py -v --benchmark-only
    pytest apps/templates/workflow/tests/test_benchmarks.py -v --benchmark-json=benchmark_results.json
    pytest apps/templates/workflow/tests/test_benchmarks.py -v --benchmark-compare

Benchmark Requirements (Week 11):
- Simple workflow (2-3 nodes): P95 < 100ms
- Complex workflow (10+ nodes): P95 < 500ms
- Parallel execution (10 nodes): P95 < 200ms
- Throughput: > 100 workflows/min
"""

import asyncio
import pytest
import time
from unittest.mock import patch
from typing import Any, Dict

from apps.templates.workflow.engine import WorkflowEngine
from apps.templates.workflow.executor import DAGExecutor
from apps.templates.workflow.context import ContextManager
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


# ============================================================================
# Test Fixtures
# ============================================================================


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
        mode: NodeExecutionMode = NodeExecutionMode.SYNC
    ) -> NodeExecutionResult:
        """Execute mock node with minimal delay."""
        # Simulate minimal processing time
        time.sleep(self.delay)
        return NodeExecutionResult(
            success=True,
            output={"node_id": node.id, "processed": True},
            error=None,
            mode=NodeExecutionMode.SYNC,
            duration_seconds=self.delay
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


# ============================================================================
# Benchmark: Simple Workflow (2-3 nodes)
# ============================================================================


@pytest.mark.benchmark(group="simple_workflow")
class TestSimpleWorkflowBenchmarks:
    """Benchmarks for simple 2-3 node sequential workflows."""

    @pytest.mark.django_db(transaction=True)
    def test_simple_2node_workflow_execution(
        self, benchmark, simple_workflow_template, mock_handler_factory
    ):
        """Benchmark simple 2-node workflow execution time."""
        engine = WorkflowEngine()
        input_context = {"benchmark": True}

        def execute():
            return engine.execute_workflow_sync(simple_workflow_template, input_context)

        result = benchmark(execute)

        assert result is not None
        assert result.status == WorkflowExecution.STATUS_COMPLETED

    @pytest.mark.django_db(transaction=True)
    def test_simple_3node_workflow_execution(
        self, benchmark, three_node_template, mock_handler_factory
    ):
        """Benchmark simple 3-node workflow execution time."""
        engine = WorkflowEngine()
        input_context = {"benchmark": True}

        def execute():
            return engine.execute_workflow_sync(three_node_template, input_context)

        result = benchmark(execute)

        assert result is not None
        assert result.status == WorkflowExecution.STATUS_COMPLETED

    @pytest.mark.django_db(transaction=True)
    def test_single_node_execution_overhead(
        self, benchmark, simple_dag, mock_handler_factory, simple_workflow_template
    ):
        """Benchmark single node execution overhead."""
        execution = simple_workflow_template.create_execution({"test": True})
        execution.start()
        execution.save()

        executor = DAGExecutor(simple_dag, execution)
        context = ContextManager({"benchmark": True})

        def execute_single():
            return WorkflowEngine._run_async(
                executor._execute_node(
                    "start",
                    simple_dag.nodes[0],
                    context
                )
            )

        result = benchmark(execute_single)
        success, _ = result
        assert success is True

    @pytest.mark.django_db(transaction=True)
    def test_context_manager_operations(self, benchmark):
        """Benchmark ContextManager operations."""

        def context_ops():
            ctx = ContextManager({"input": "data", "count": 100})
            ctx = ctx.set("result.status", "ok")
            ctx = ctx.add_node_result("node_1", {"output": "data"})
            _ = ctx.get("nodes.node_1.output")
            _ = ctx.resolve_template("{{ input }}-{{ count }}")
            return ctx.snapshot()

        result = benchmark(context_ops)
        assert result is not None


# ============================================================================
# Benchmark: Complex Workflow (10+ nodes)
# ============================================================================


@pytest.mark.benchmark(group="complex_workflow")
class TestComplexWorkflowBenchmarks:
    """Benchmarks for complex workflows (10+ nodes, parallel branches, conditionals)."""

    @pytest.mark.django_db(transaction=True)
    def test_complex_12node_workflow_execution(
        self, benchmark, complex_workflow_template, mock_handler_factory
    ):
        """Benchmark complex workflow with 12 nodes and branching."""
        engine = WorkflowEngine()
        input_context = {"benchmark": True, "branch_selector": "both"}

        def execute():
            return engine.execute_workflow_sync(complex_workflow_template, input_context)

        result = benchmark(execute)

        assert result is not None
        assert result.status == WorkflowExecution.STATUS_COMPLETED

    @pytest.mark.django_db(transaction=True)
    def test_dag_validation_complex(self, benchmark, complex_dag):
        """Benchmark DAG validation for complex workflow."""
        from apps.templates.workflow.validator import DAGValidator

        def validate():
            validator = DAGValidator(complex_dag)
            return validator.validate()

        result = benchmark(validate)
        assert result.is_valid is True

    @pytest.mark.django_db(transaction=True)
    def test_topological_order_calculation(self, benchmark, complex_dag):
        """Benchmark topological order calculation for complex DAG."""
        from apps.templates.workflow.validator import DAGValidator

        def calculate_order():
            validator = DAGValidator(complex_dag)
            result = validator.validate()
            return result.topological_order

        order = benchmark(calculate_order)
        assert order is not None
        assert len(order) == 12  # 12 nodes in complex DAG

    @pytest.mark.django_db(transaction=True)
    def test_workflow_with_conditions(
        self, benchmark, admin_user, mock_handler_factory
    ):
        """Benchmark workflow with condition evaluations."""
        # Create workflow with multiple conditions
        dag = DAGStructure(
            nodes=[
                WorkflowNode(
                    id="start",
                    name="Start",
                    type="operation",
                    template_id="mock_template",
                    config=NodeConfig(timeout_seconds=30)
                ),
                WorkflowNode(
                    id="cond1",
                    name="Condition 1",
                    type="condition",
                    config=NodeConfig(expression="{{ count > 5 }}")
                ),
                WorkflowNode(
                    id="cond2",
                    name="Condition 2",
                    type="condition",
                    config=NodeConfig(expression="{{ status == 'active' }}")
                ),
                WorkflowNode(
                    id="end",
                    name="End",
                    type="operation",
                    template_id="mock_template",
                    config=NodeConfig(timeout_seconds=30)
                ),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="cond1"),
                WorkflowEdge(from_node="cond1", to_node="cond2", condition="{{ True }}"),
                WorkflowEdge(from_node="cond2", to_node="end", condition="{{ True }}"),
            ]
        )

        template = WorkflowTemplate.objects.create(
            name="Benchmark Conditional Workflow",
            workflow_type="benchmark",
            dag_structure=dag.model_dump(),
            created_by=admin_user,
            is_valid=True,
            is_active=True
        )

        engine = WorkflowEngine()
        input_context = {"count": 10, "status": "active"}

        def execute():
            return engine.execute_workflow_sync(template, input_context)

        result = benchmark(execute)
        assert result.status == WorkflowExecution.STATUS_COMPLETED


# ============================================================================
# Benchmark: Parallel Execution (10 nodes concurrently)
# ============================================================================


@pytest.mark.benchmark(group="parallel_execution")
class TestParallelExecutionBenchmarks:
    """Benchmarks for parallel node execution."""

    @pytest.mark.django_db(transaction=True)
    def test_parallel_10_nodes_sequential(
        self, benchmark, parallel_workflow_template, mock_handler_factory
    ):
        """
        Benchmark executing 10 parallel nodes (sequentially in DAG order).

        Note: Current implementation executes in topological order.
        Real parallel execution will be benchmarked with Celery (Week 9).
        """
        engine = WorkflowEngine()
        input_context = {"benchmark": True, "parallel_count": 10}

        def execute():
            return engine.execute_workflow_sync(parallel_workflow_template, input_context)

        result = benchmark(execute)

        assert result is not None
        assert result.status == WorkflowExecution.STATUS_COMPLETED

    @pytest.mark.django_db(transaction=True)
    def test_dag_executor_parallel_structure(
        self, benchmark, parallel_10_dag, parallel_workflow_template
    ):
        """Benchmark DAGExecutor with parallel structure."""
        execution = parallel_workflow_template.create_execution({"test": True})
        execution.start()
        execution.save()

        handler = MockHandler(delay=0.001)

        with patch.object(NodeHandlerFactory, 'get_handler', return_value=handler):
            def execute():
                executor = DAGExecutor(parallel_10_dag, execution)
                context = ContextManager({"benchmark": True})
                return asyncio.run(executor.execute(context))

            result = benchmark(execute)
            success, _ = result
            assert success is True

    @pytest.mark.django_db(transaction=True)
    def test_concurrent_context_snapshots(self, benchmark):
        """Benchmark creating concurrent context snapshots for parallel execution."""
        base_context = ContextManager({
            "input": "data",
            "database_id": "123",
            "users": list(range(100)),
            "config": {"nested": {"deep": {"value": True}}}
        })

        # Add some node results
        for i in range(5):
            base_context = base_context.add_node_result(
                f"node_{i}",
                {"output": f"result_{i}", "data": list(range(10))}
            )

        def create_snapshots():
            """Create 10 concurrent snapshots (simulating parallel execution)."""
            snapshots = []
            for i in range(10):
                snapshot = base_context.snapshot()
                snapshot = snapshot.set(f"parallel_branch_{i}", True)
                snapshots.append(snapshot)
            return snapshots

        result = benchmark(create_snapshots)
        assert len(result) == 10


# ============================================================================
# Benchmark: Throughput (workflows/min)
# ============================================================================


@pytest.mark.benchmark(group="throughput")
class TestThroughputBenchmarks:
    """Measure workflows per minute throughput."""

    @pytest.mark.django_db(transaction=True)
    def test_workflow_throughput_simple(
        self, benchmark, simple_workflow_template, mock_handler_factory
    ):
        """
        Measure how many simple workflows can be executed per minute.

        Target: > 100 workflows/min (1.67 workflows/sec)
        """
        engine = WorkflowEngine()
        workflows_per_batch = 10

        def execute_batch():
            results = []
            for i in range(workflows_per_batch):
                result = engine.execute_workflow_sync(
                    simple_workflow_template,
                    {"iteration": i}
                )
                results.append(result)
            return results

        benchmark.pedantic(
            execute_batch,
            iterations=5,
            rounds=3,
            warmup_rounds=1
        )

        # Manual throughput calculation will be in benchmark stats

    @pytest.mark.django_db(transaction=True)
    def test_workflow_throughput_with_context(
        self, benchmark, three_node_template, mock_handler_factory
    ):
        """Measure throughput with more realistic context data."""
        engine = WorkflowEngine()
        workflows_per_batch = 10

        def execute_batch():
            results = []
            for i in range(workflows_per_batch):
                context = {
                    "database_id": f"db_{i}",
                    "user_id": f"user_{i}",
                    "operation": "benchmark_test",
                    "parameters": {
                        "timeout": 30,
                        "retries": 3,
                        "filters": ["active", "verified"]
                    }
                }
                result = engine.execute_workflow_sync(three_node_template, context)
                results.append(result)
            return results

        benchmark.pedantic(
            execute_batch,
            iterations=5,
            rounds=3,
            warmup_rounds=1
        )

    @pytest.mark.django_db(transaction=True)
    def test_execution_creation_throughput(self, benchmark, simple_workflow_template):
        """Benchmark WorkflowExecution creation throughput."""
        executions_per_batch = 20

        def create_executions():
            executions = []
            for i in range(executions_per_batch):
                execution = simple_workflow_template.create_execution(
                    {"iteration": i}
                )
                executions.append(execution)
            return executions

        result = benchmark(create_executions)
        assert len(result) == executions_per_batch


# ============================================================================
# Benchmark: Latency Measurements
# ============================================================================


@pytest.mark.benchmark(group="latency")
class TestLatencyBenchmarks:
    """Measure latency (P50, P95, P99) for various operations."""

    @pytest.mark.django_db(transaction=True)
    def test_engine_instantiation_latency(self, benchmark):
        """Benchmark WorkflowEngine singleton instantiation."""
        WorkflowEngine.reset_singleton()

        def create_engine():
            return WorkflowEngine()

        engine = benchmark(create_engine)
        assert engine is not None

    @pytest.mark.django_db(transaction=True)
    def test_dag_structure_parsing_latency(self, benchmark, complex_dag):
        """Benchmark DAGStructure parsing from dict."""
        dag_dict = complex_dag.model_dump()

        def parse_dag():
            return DAGStructure(**dag_dict)

        result = benchmark(parse_dag)
        assert len(result.nodes) == 12

    @pytest.mark.django_db(transaction=True)
    def test_condition_evaluation_latency(self, benchmark):
        """Benchmark Jinja2 condition evaluation latency."""
        context = ContextManager({
            "count": 150,
            "status": "approved",
            "users": list(range(100)),
            "config": {"enabled": True, "level": 5}
        })

        conditions = [
            "{{ count > 100 }}",
            "{{ status == 'approved' }}",
            "{{ users|length > 50 }}",
            "{{ config.enabled and config.level > 3 }}"
        ]

        def evaluate_conditions():
            results = []
            for cond in conditions:
                result = context.evaluate_condition(cond)
                results.append(result)
            return results

        result = benchmark(evaluate_conditions)
        assert all(result)

    @pytest.mark.django_db(transaction=True)
    def test_template_resolution_latency(self, benchmark):
        """Benchmark Jinja2 template resolution latency."""
        context = ContextManager({
            "database": {"id": "db_123", "name": "Production"},
            "user": {"id": "user_456", "role": "admin"},
            "operation": {"type": "backup", "priority": "high"}
        })

        templates = [
            "Database: {{ database.name }} ({{ database.id }})",
            "User: {{ user.id }} - {{ user.role }}",
            "Operation: {{ operation.type }} [{{ operation.priority }}]",
            "Full: {{ database.name }}/{{ user.role }}/{{ operation.type }}"
        ]

        def resolve_templates():
            results = []
            for tmpl in templates:
                result = context.resolve_template(tmpl)
                results.append(result)
            return results

        result = benchmark(resolve_templates)
        assert len(result) == 4


# ============================================================================
# Benchmark: Memory and Resource Usage
# ============================================================================


@pytest.mark.benchmark(group="resources")
class TestResourceBenchmarks:
    """Benchmark memory and resource usage patterns."""

    @pytest.mark.django_db(transaction=True)
    def test_large_context_handling(self, benchmark):
        """Benchmark handling of large context data."""

        def create_large_context():
            # Create context with significant data
            initial = {
                "databases": [{"id": f"db_{i}", "name": f"Database {i}"} for i in range(100)],
                "users": [{"id": f"user_{i}", "name": f"User {i}"} for i in range(1000)],
                "operations": [{"id": f"op_{i}", "type": "query"} for i in range(500)],
                "metadata": {
                    "nested": {
                        "deep": {
                            "value": list(range(100))
                        }
                    }
                }
            }
            ctx = ContextManager(initial)

            # Add multiple node results
            for i in range(10):
                ctx = ctx.add_node_result(
                    f"node_{i}",
                    {"results": list(range(50)), "status": "completed"}
                )

            return ctx.to_dict()

        result = benchmark(create_large_context)
        assert "databases" in result
        assert "nodes" in result

    @pytest.mark.django_db(transaction=True)
    def test_dag_with_many_edges(self, benchmark, admin_user):
        """Benchmark DAG with dense edge connections."""
        # Create DAG with many edges (star topology)
        nodes = [
            WorkflowNode(
                id="hub",
                name="Hub",
                type="operation",
                template_id="mock_template",
                config=NodeConfig(timeout_seconds=30)
            )
        ]

        edges = []
        for i in range(20):
            nodes.append(
                WorkflowNode(
                    id=f"spoke_{i}",
                    name=f"Spoke {i}",
                    type="operation",
                    template_id="mock_template",
                    config=NodeConfig(timeout_seconds=30)
                )
            )
            edges.append(WorkflowEdge(from_node="hub", to_node=f"spoke_{i}"))

        dag = DAGStructure(nodes=nodes, edges=edges)

        from apps.templates.workflow.validator import DAGValidator

        def validate_dense_dag():
            validator = DAGValidator(dag)
            return validator.validate()

        result = benchmark(validate_dense_dag)
        assert result.is_valid is True

    @pytest.mark.django_db(transaction=True)
    def test_repeated_handler_access(self, benchmark, mock_handler_factory):
        """Benchmark repeated handler factory access (singleton pattern)."""

        def access_handlers():
            handlers = []
            for _ in range(100):
                h = NodeHandlerFactory.get_handler("operation")
                handlers.append(h)
            return handlers

        result = benchmark(access_handlers)
        # All should be same instance (singleton)
        assert len(set(id(h) for h in result)) == 1


# ============================================================================
# Benchmark: Comparison Tests
# ============================================================================


@pytest.mark.benchmark(group="comparison")
class TestComparisonBenchmarks:
    """Compare different execution strategies."""

    @pytest.mark.django_db(transaction=True)
    def test_sequential_vs_parallel_preparation(
        self, benchmark, parallel_10_dag, parallel_workflow_template
    ):
        """Compare preparation overhead for sequential vs parallel execution."""
        execution = parallel_workflow_template.create_execution({"test": True})
        execution.start()
        execution.save()

        def prepare_sequential():
            """Prepare context for sequential execution."""
            contexts = []
            base_context = ContextManager({"benchmark": True})
            for i, node in enumerate(parallel_10_dag.nodes):
                ctx = base_context.set(f"node_{i}_prepared", True)
                contexts.append(ctx)
            return contexts

        result = benchmark(prepare_sequential)
        assert len(result) == len(parallel_10_dag.nodes)

    @pytest.mark.django_db(transaction=True)
    def test_shallow_vs_deep_context_copy(self, benchmark):
        """Compare shallow vs deep context operations."""
        base_data = {
            "level1": {
                "level2": {
                    "level3": {
                        "data": list(range(100))
                    }
                }
            }
        }

        def deep_context_operations():
            ctx = ContextManager(base_data)
            # Multiple deep operations
            ctx = ctx.set("level1.level2.level3.new_key", "value")
            ctx = ctx.add_node_result("node_1", {"nested": {"data": [1, 2, 3]}})
            _ = ctx.get("level1.level2.level3.data")
            return ctx.snapshot()

        result = benchmark(deep_context_operations)
        assert result is not None
