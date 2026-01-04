"""
Tests for DAGExecutor in Workflow Engine.

Covers:
- Linear DAG execution (A -> B -> C)
- Conditional edge evaluation
- Node skipping based on conditions
- Error handling
- Topological ordering
- Edge cases and error scenarios
"""

import asyncio
import pytest
from unittest.mock import Mock, patch

from apps.templates.workflow.context import ContextManager
from apps.templates.workflow.executor import DAGExecutor
from apps.templates.workflow.handlers import NodeExecutionResult
from apps.templates.workflow.models import (
    DAGStructure,
    WorkflowNode,
    WorkflowEdge,
    WorkflowStepResult,
    WorkflowTemplate,
    WorkflowType,
)

pytestmark = pytest.mark.django_db(transaction=True)


class TestDAGExecutorInit:
    """Tests for DAGExecutor initialization."""

    @pytest.fixture
    def simple_dag(self):
        """Create simple linear DAG: A -> B."""
        return DAGStructure(
            nodes=[
                WorkflowNode(id='A', name='Node A', type='operation', template_id='op1'),
                WorkflowNode(id='B', name='Node B', type='operation', template_id='op2'),
            ],
            edges=[
                WorkflowEdge(from_node='A', to_node='B'),
            ]
        )

    @pytest.fixture
    def execution(self, simple_workflow_template):
        """Create workflow execution."""
        return simple_workflow_template.create_execution({'test': 'data'})

    def test_init_creates_executor(self, simple_dag, execution):
        """Test DAGExecutor initialization."""
        executor = DAGExecutor(simple_dag, execution)

        assert executor.dag == simple_dag
        assert executor.execution == execution
        assert len(executor.node_map) == 2

    def test_init_builds_node_map(self, simple_dag, execution):
        """Test that initialization builds node lookup map."""
        executor = DAGExecutor(simple_dag, execution)

        assert 'A' in executor.node_map
        assert 'B' in executor.node_map
        assert executor.node_map['A'].name == 'Node A'
        assert executor.node_map['B'].name == 'Node B'

    def test_init_builds_edge_maps(self, simple_dag, execution):
        """Test that initialization builds incoming/outgoing edge maps."""
        executor = DAGExecutor(simple_dag, execution)

        # A has outgoing edge to B
        assert 'A' in executor.outgoing_edges
        assert len(executor.outgoing_edges['A']) == 1

        # B has incoming edge from A
        assert 'B' in executor.incoming_edges
        assert len(executor.incoming_edges['B']) == 1

    def test_init_validates_dag(self, execution):
        """Test that initialization validates DAG."""
        # Create invalid DAG (cycle)
        invalid_dag = DAGStructure(
            nodes=[
                WorkflowNode(id='A', name='Node A', type='operation', template_id='op1'),
                WorkflowNode(id='B', name='Node B', type='operation', template_id='op2'),
            ],
            edges=[
                WorkflowEdge(from_node='A', to_node='B'),
                WorkflowEdge(from_node='B', to_node='A'),  # Cycle!
            ]
        )

        with pytest.raises(ValueError, match="DAG validation failed"):
            DAGExecutor(invalid_dag, execution)

    def test_init_computes_topological_order(self, simple_dag, execution):
        """Test that topological order is computed."""
        executor = DAGExecutor(simple_dag, execution)

        assert executor.topological_order == ['A', 'B']


class TestDAGExecutorLinearExecution:
    """Tests for linear DAG execution (A -> B -> C)."""

    @pytest.fixture
    def linear_dag(self):
        """Create linear DAG: A -> B -> C."""
        return DAGStructure(
            nodes=[
                WorkflowNode(id='A', name='Node A', type='operation', template_id='op1'),
                WorkflowNode(id='B', name='Node B', type='operation', template_id='op2'),
                WorkflowNode(id='C', name='Node C', type='operation', template_id='op3'),
            ],
            edges=[
                WorkflowEdge(from_node='A', to_node='B'),
                WorkflowEdge(from_node='B', to_node='C'),
            ]
        )

    @pytest.fixture
    def execution(self, simple_workflow_template):
        """Create workflow execution."""
        return simple_workflow_template.create_execution({'input': 'value'})

    def test_linear_execution_success(self, linear_dag, execution):
        """Test successful execution of linear DAG."""
        executor = DAGExecutor(linear_dag, execution)

        # Mock node handler
        with patch('apps.templates.workflow.executor.NodeHandlerFactory') as mock_factory:
            mock_handler = Mock()
            mock_factory.get_handler.return_value = mock_handler

            # Mock successful execution for each node
            def mock_execute(node, context, execution, mode):
                return NodeExecutionResult(
                    success=True,
                    output={'status': 'completed', 'node_id': node.id},
                    error=None,
                    mode=mode,
                    duration_seconds=0.1
                )

            mock_handler.execute = mock_execute

            # Execute
            context = ContextManager({'input': 'value'})
            success, result = asyncio.run(executor.execute(context))

            assert success is True
            assert isinstance(result, dict)
            assert 'nodes' in result

    def test_linear_execution_correct_order(self, linear_dag, execution):
        """Test that nodes are executed in topological order."""
        executor = DAGExecutor(linear_dag, execution)
        execution_order = []

        with patch('apps.templates.workflow.executor.NodeHandlerFactory') as mock_factory:
            mock_handler = Mock()
            mock_factory.get_handler.return_value = mock_handler

            def mock_execute(node, context, execution, mode):
                execution_order.append(node.id)
                return NodeExecutionResult(
                    success=True,
                    output={},
                    error=None,
                    mode=mode,
                    duration_seconds=0.1
                )

            mock_handler.execute = mock_execute

            context = ContextManager({})
            asyncio.run(executor.execute(context))

            assert execution_order == ['A', 'B', 'C']

    def test_linear_execution_node_failure(self, linear_dag, execution):
        """Test execution stops when node fails."""
        executor = DAGExecutor(linear_dag, execution)
        execution_order = []

        with patch('apps.templates.workflow.executor.NodeHandlerFactory') as mock_factory:
            mock_handler = Mock()
            mock_factory.get_handler.return_value = mock_handler

            def mock_execute(node, context, execution, mode):
                execution_order.append(node.id)
                if node.id == 'B':
                    return NodeExecutionResult(
                        success=False,
                        output=None,
                        error='Node B failed',
                        mode=mode,
                        duration_seconds=0.1
                    )
                return NodeExecutionResult(
                    success=True,
                    output={},
                    error=None,
                    mode=mode,
                    duration_seconds=0.1
                )

            mock_handler.execute = mock_execute

            context = ContextManager({})
            success, result = asyncio.run(executor.execute(context))

            assert success is False
            assert result['error'] == 'Node B failed'
            assert result['node_id'] == 'B'
            assert execution_order == ['A', 'B']  # C not executed

    def test_linear_execution_propagates_context(self, linear_dag, execution):
        """Test that context is propagated through execution."""
        executor = DAGExecutor(linear_dag, execution)

        with patch('apps.templates.workflow.executor.NodeHandlerFactory') as mock_factory:
            mock_handler = Mock()
            mock_factory.get_handler.return_value = mock_handler

            def mock_execute(node, context, execution, mode):
                # Each node receives context with previous results
                return NodeExecutionResult(
                    success=True,
                    output={'node_output': f'result_{node.id}'},
                    error=None,
                    mode=mode,
                    duration_seconds=0.1
                )

            mock_handler.execute = mock_execute

            context = ContextManager({'initial': 'data'})
            success, result = asyncio.run(executor.execute(context))

            assert success is True
            # Result should contain node results
            assert 'nodes' in result
            assert 'A' in result['nodes']
            assert 'B' in result['nodes']
            assert 'C' in result['nodes']


class TestDAGExecutorConditionalExecution:
    """Tests for conditional edge execution."""

    @pytest.fixture
    def conditional_dag(self):
        """Create DAG with conditional edges."""
        return DAGStructure(
            nodes=[
                WorkflowNode(id='A', name='Node A', type='operation', template_id='op1'),
                WorkflowNode(id='B', name='Node B (if true)', type='operation', template_id='op2'),
                WorkflowNode(id='C', name='Node C (if false)', type='operation', template_id='op3'),
                WorkflowNode(id='D', name='Node D', type='operation', template_id='op4'),
            ],
            edges=[
                WorkflowEdge(from_node='A', to_node='B', condition='{{ condition == "true" }}'),
                WorkflowEdge(from_node='A', to_node='C', condition='{{ condition == "false" }}'),
                WorkflowEdge(from_node='B', to_node='D'),
                WorkflowEdge(from_node='C', to_node='D'),
            ]
        )

    @pytest.fixture
    def execution(self, simple_workflow_template):
        """Create workflow execution."""
        return simple_workflow_template.create_execution({})

    def test_conditional_true_branch(self, conditional_dag, execution):
        """Test execution of true branch when condition is true."""
        executor = DAGExecutor(conditional_dag, execution)
        execution_order = []

        with patch('apps.templates.workflow.executor.NodeHandlerFactory') as mock_factory:
            mock_handler = Mock()
            mock_factory.get_handler.return_value = mock_handler

            def mock_execute(node, context, execution, mode):
                execution_order.append(node.id)
                return NodeExecutionResult(
                    success=True,
                    output={},
                    error=None,
                    mode=mode,
                    duration_seconds=0.1
                )

            mock_handler.execute = mock_execute

            context = ContextManager({'condition': 'true'})
            success, result = asyncio.run(executor.execute(context))

            assert success is True
            # Should execute A -> B -> D, skip C
            assert 'A' in execution_order
            assert 'B' in execution_order
            assert 'D' in execution_order
            assert 'C' not in execution_order

    def test_conditional_false_branch(self, conditional_dag, execution):
        """Test execution of false branch when condition is false."""
        executor = DAGExecutor(conditional_dag, execution)
        execution_order = []

        with patch('apps.templates.workflow.executor.NodeHandlerFactory') as mock_factory:
            mock_handler = Mock()
            mock_factory.get_handler.return_value = mock_handler

            def mock_execute(node, context, execution, mode):
                execution_order.append(node.id)
                return NodeExecutionResult(
                    success=True,
                    output={},
                    error=None,
                    mode=mode,
                    duration_seconds=0.1
                )

            mock_handler.execute = mock_execute

            context = ContextManager({'condition': 'false'})
            success, result = asyncio.run(executor.execute(context))

            assert success is True
            # Should execute A -> C -> D, skip B
            assert 'A' in execution_order
            assert 'C' in execution_order
            assert 'D' in execution_order
            assert 'B' not in execution_order

    def test_conditional_edge_evaluation_with_node_result(self, execution):
        """Test condition evaluation using node results."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id='check', name='Check', type='operation', template_id='op1'),
                WorkflowNode(id='success', name='Success', type='operation', template_id='op2'),
                WorkflowNode(id='failure', name='Failure', type='operation', template_id='op3'),
            ],
            edges=[
                WorkflowEdge(from_node='check', to_node='success', condition='{{ nodes.check.success }}'),
                WorkflowEdge(from_node='check', to_node='failure', condition='{{ not nodes.check.success }}'),
            ]
        )

        executor = DAGExecutor(dag, execution)
        execution_order = []

        with patch('apps.templates.workflow.executor.NodeHandlerFactory') as mock_factory:
            mock_handler = Mock()
            mock_factory.get_handler.return_value = mock_handler

            def mock_execute(node, context, execution, mode):
                execution_order.append(node.id)
                return NodeExecutionResult(
                    success=True,
                    output={'success': True},
                    error=None,
                    mode=mode,
                    duration_seconds=0.1
                )

            mock_handler.execute = mock_execute

            context = ContextManager({})
            success, result = asyncio.run(executor.execute(context))

            assert success is True
            assert 'check' in execution_order
            assert 'success' in execution_order
            assert 'failure' not in execution_order

    def test_no_condition_always_executes(self, execution):
        """Test that edge without condition always executes."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id='A', name='Node A', type='operation', template_id='op1'),
                WorkflowNode(id='B', name='Node B', type='operation', template_id='op2'),
            ],
            edges=[
                WorkflowEdge(from_node='A', to_node='B'),  # No condition
            ]
        )

        executor = DAGExecutor(dag, execution)

        with patch('apps.templates.workflow.executor.NodeHandlerFactory') as mock_factory:
            mock_handler = Mock()
            mock_factory.get_handler.return_value = mock_handler

            def mock_execute(node, context, execution, mode):
                return NodeExecutionResult(
                    success=True,
                    output={},
                    error=None,
                    mode=mode,
                    duration_seconds=0.1
                )

            mock_handler.execute = mock_execute

            context = ContextManager({})
            success, result = asyncio.run(executor.execute(context))

            assert success is True


class TestDAGExecutorErrorHandling:
    """Tests for error handling."""

    @pytest.fixture
    def simple_dag(self):
        """Create simple DAG."""
        return DAGStructure(
            nodes=[
                WorkflowNode(id='A', name='Node A', type='operation', template_id='op1'),
                WorkflowNode(id='B', name='Node B', type='operation', template_id='op2'),
            ],
            edges=[
                WorkflowEdge(from_node='A', to_node='B'),
            ]
        )

    @pytest.fixture
    def execution(self, simple_workflow_template):
        """Create workflow execution."""
        return simple_workflow_template.create_execution({})

    def test_handler_not_found_error(self, simple_dag, execution):
        """Test handling when handler is not found."""
        executor = DAGExecutor(simple_dag, execution)

        with patch('apps.templates.workflow.executor.NodeHandlerFactory') as mock_factory:
            mock_factory.get_handler.side_effect = ValueError("No handler for type 'unknown'")

            context = ContextManager({})
            success, result = asyncio.run(executor.execute(context))

            assert success is False
            assert 'error' in result
            assert 'Handler error' in result['error']

    def test_node_execution_exception(self, simple_dag, execution):
        """Test handling of unexpected exception during execution."""
        executor = DAGExecutor(simple_dag, execution)

        with patch('apps.templates.workflow.executor.NodeHandlerFactory') as mock_factory:
            mock_handler = Mock()
            mock_factory.get_handler.return_value = mock_handler
            mock_handler.execute.side_effect = Exception("Unexpected error")

            context = ContextManager({})
            success, result = asyncio.run(executor.execute(context))

            assert success is False
            assert 'error' in result

    def test_condition_evaluation_error_treats_as_false(self, execution):
        """Test that condition evaluation error treats edge as false."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id='A', name='Node A', type='operation', template_id='op1'),
                WorkflowNode(id='B', name='Node B', type='operation', template_id='op2'),
                WorkflowNode(id='C', name='Node C', type='operation', template_id='op3'),
            ],
            edges=[
                WorkflowEdge(from_node='A', to_node='B', condition='{{ invalid syntax }}'),
                WorkflowEdge(from_node='A', to_node='C'),
            ]
        )

        executor = DAGExecutor(dag, execution)
        execution_order = []

        with patch('apps.templates.workflow.executor.NodeHandlerFactory') as mock_factory:
            mock_handler = Mock()
            mock_factory.get_handler.return_value = mock_handler

            def mock_execute(node, context, execution, mode):
                execution_order.append(node.id)
                return NodeExecutionResult(
                    success=True,
                    output={},
                    error=None,
                    mode=mode,
                    duration_seconds=0.1
                )

            mock_handler.execute = mock_execute

            context = ContextManager({})
            success, result = asyncio.run(executor.execute(context))

            # Should execute A -> C, skip B (condition error = false)
            assert 'A' in execution_order
            assert 'C' in execution_order
            assert 'B' not in execution_order


class TestDAGExecutorEdgeCases:
    """Tests for edge cases."""

    @pytest.fixture
    def execution(self, simple_workflow_template):
        """Create workflow execution."""
        return simple_workflow_template.create_execution({})

    def test_single_node_dag(self, execution):
        """Test execution of DAG with single node."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id='A', name='Node A', type='operation', template_id='op1'),
            ],
            edges=[]
        )

        executor = DAGExecutor(dag, execution)

        with patch('apps.templates.workflow.executor.NodeHandlerFactory') as mock_factory:
            mock_handler = Mock()
            mock_factory.get_handler.return_value = mock_handler

            def mock_execute(node, context, execution, mode):
                return NodeExecutionResult(
                    success=True,
                    output={'result': 'value'},
                    error=None,
                    mode=mode,
                    duration_seconds=0.1
                )

            mock_handler.execute = mock_execute

            context = ContextManager({})
            success, result = asyncio.run(executor.execute(context))

            assert success is True

    def test_multiple_edges_between_nodes(self, execution):
        """Test DAG with multiple edges to same node."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id='A', name='Node A', type='operation', template_id='op1'),
                WorkflowNode(id='B', name='Node B', type='operation', template_id='op2'),
                WorkflowNode(id='C', name='Node C', type='operation', template_id='op3'),
            ],
            edges=[
                WorkflowEdge(from_node='A', to_node='C', condition='{{ a_path }}'),
                WorkflowEdge(from_node='B', to_node='C', condition='{{ b_path }}'),
            ]
        )

        executor = DAGExecutor(dag, execution)
        execution_order = []

        with patch('apps.templates.workflow.executor.NodeHandlerFactory') as mock_factory:
            mock_handler = Mock()
            mock_factory.get_handler.return_value = mock_handler

            def mock_execute(node, context, execution, mode):
                execution_order.append(node.id)
                return NodeExecutionResult(
                    success=True,
                    output={},
                    error=None,
                    mode=mode,
                    duration_seconds=0.1
                )

            mock_handler.execute = mock_execute

            context = ContextManager({'a_path': 'true', 'b_path': 'false'})
            success, result = asyncio.run(executor.execute(context))

            assert success is True
            # Both A and B are start nodes, C has multiple incoming edges
            assert 'C' in execution_order

    def test_get_next_nodes(self, execution):
        """Test get_next_nodes() method."""
        dag = DAGStructure(
            nodes=[
                WorkflowNode(id='A', name='Node A', type='operation', template_id='op1'),
                WorkflowNode(id='B', name='Node B', type='operation', template_id='op2'),
                WorkflowNode(id='C', name='Node C', type='operation', template_id='op3'),
            ],
            edges=[
                WorkflowEdge(from_node='A', to_node='B', condition='{{ cond1 }}'),
                WorkflowEdge(from_node='A', to_node='C', condition='{{ cond2 }}'),
            ]
        )

        executor = DAGExecutor(dag, execution)
        context = ContextManager({'cond1': 'true', 'cond2': 'false'})

        next_nodes = executor.get_next_nodes('A', context)
        assert 'B' in next_nodes
        assert 'C' not in next_nodes


class TestDAGExecutorStepResults:
    """Regression tests for WorkflowStepResult behavior in DAGExecutor."""

    def test_executor_does_not_create_duplicate_terminal_step_results(self, db, admin_user):
        template = WorkflowTemplate.objects.create(
            name="Condition Workflow",
            description="",
            workflow_type=WorkflowType.CONDITIONAL,
            dag_structure={
                "nodes": [
                    {
                        "id": "cond1",
                        "name": "Condition 1",
                        "type": "condition",
                        "config": {"expression": "true"},
                    },
                ],
                "edges": [],
            },
            created_by=admin_user,
            is_valid=True,
            is_active=True,
        )

        execution = template.create_execution({})
        executor = DAGExecutor(template.dag_structure, execution)

        success, _result = asyncio.run(executor.execute(ContextManager({})))
        assert success is True

        terminal_steps = WorkflowStepResult.objects.filter(
            workflow_execution=execution,
            node_id="cond1",
            status__in=[
                WorkflowStepResult.STATUS_COMPLETED,
                WorkflowStepResult.STATUS_FAILED,
                WorkflowStepResult.STATUS_SKIPPED,
            ],
        )
        assert terminal_steps.count() == 1
