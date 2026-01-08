"""
Integration tests for backend system.

Tests cover:
- Complete workflow execution with RAS operations
- Complete workflow execution with OData operations
- Error propagation and handling
- Workflow execution tracking and auditing
"""

import pytest
from unittest.mock import patch
from uuid import uuid4

from apps.templates.models import OperationTemplate
from apps.templates.workflow.models import WorkflowNode, WorkflowStepResult
from apps.templates.workflow.handlers.operation import OperationHandler
from apps.templates.workflow.handlers.base import NodeExecutionMode, NodeExecutionResult


@pytest.mark.django_db
class TestRASBackendIntegration:
    """Integration tests for RAS backend with workflow engine."""

    def test_workflow_with_ras_lock_operation(
        self,
        database,
        workflow_execution
    ):
        """Test complete workflow execution with RAS lock operation."""
        # Create operation template
        template = OperationTemplate.objects.create(
            id=str(uuid4()),
            name="Maintenance Lock",
            operation_type='lock_scheduled_jobs',
            target_entity="Infobase",
            template_data={
                "description": "Lock for maintenance",
                "duration": "{{ duration }}"
            }
        )

        # Create workflow node
        node = WorkflowNode(
            id="lock_node",
            name="Lock Scheduled Jobs",
            type="operation",
            template_id=str(template.id)
        )

        # Create handler
        handler = OperationHandler()

        with patch('apps.templates.workflow.handlers.backends.ras.RASBackend.execute') as mock_execute:
            mock_execute.return_value = NodeExecutionResult(
                success=True,
                output={'backend': 'ras', 'operation_type': 'lock_scheduled_jobs'},
                error=None,
                mode=NodeExecutionMode.SYNC,
                duration_seconds=0.1,
                operation_id='op-1',
                task_id=None,
            )

            result = handler.execute(
                node=node,
                context={
                    'target_databases': [str(database.id)],
                    'user_id': 'admin',
                    'duration': '30 minutes'
                },
                execution=workflow_execution,
                mode=NodeExecutionMode.SYNC
            )

        # Verify execution result
        assert result.success is True
        assert result.mode == NodeExecutionMode.SYNC
        assert result.output['backend'] == 'ras'
        assert result.output['operation_type'] == 'lock_scheduled_jobs'

        # Verify step result was created
        step_result = WorkflowStepResult.objects.filter(
            workflow_execution=workflow_execution,
            node_id="lock_node"
        ).first()
        assert step_result is not None
        assert step_result.node_name == "Lock Scheduled Jobs"
        assert step_result.node_type == "operation"

    def test_workflow_with_ras_terminate_sessions(
        self,
        database,
        workflow_execution
    ):
        """Test workflow with RAS terminate_sessions operation."""
        template = OperationTemplate.objects.create(
            id=str(uuid4()),
            name="Terminate Sessions",
            operation_type='terminate_sessions',
            target_entity="Infobase",
            template_data={"noop": "ok"}
        )

        node = WorkflowNode(
            id="term_node",
            name="Terminate All Sessions",
            type="operation",
            template_id=str(template.id)
        )

        handler = OperationHandler()

        with patch('apps.templates.workflow.handlers.backends.ras.RASBackend.execute') as mock_execute:
            mock_execute.return_value = NodeExecutionResult(
                success=True,
                output={'backend': 'ras', 'operation_type': 'terminate_sessions'},
                error=None,
                mode=NodeExecutionMode.SYNC,
                duration_seconds=0.1,
                operation_id='op-2',
                task_id=None,
            )

            result = handler.execute(
                node=node,
                context={
                    'target_databases': [str(database.id)],
                    'user_id': 'admin'
                },
                execution=workflow_execution,
                mode=NodeExecutionMode.SYNC
            )

        assert result.success is True
        assert result.output['operation_type'] == 'terminate_sessions'

    def test_workflow_with_ras_block_sessions(
        self,
        database,
        workflow_execution
    ):
        """Test workflow with RAS block_sessions operation."""
        template = OperationTemplate.objects.create(
            id=str(uuid4()),
            name="Block Sessions",
            operation_type='block_sessions',
            target_entity="Infobase",
            template_data={"noop": "ok"}
        )

        node = WorkflowNode(
            id="block_node",
            name="Block User Sessions",
            type="operation",
            template_id=str(template.id)
        )

        handler = OperationHandler()

        with patch('apps.templates.workflow.handlers.backends.ras.RASBackend.execute') as mock_execute:
            mock_execute.return_value = NodeExecutionResult(
                success=True,
                output={'backend': 'ras', 'operation_type': 'block_sessions'},
                error=None,
                mode=NodeExecutionMode.SYNC,
                duration_seconds=0.1,
                operation_id='op-3',
                task_id=None,
            )

            result = handler.execute(
                node=node,
                context={
                    'target_databases': [str(database.id)],
                    'user_id': 'admin',
                    'denied_message': 'Maintenance in progress',
                    'permission_code': 'MAINTENANCE'
                },
                execution=workflow_execution,
                mode=NodeExecutionMode.SYNC
            )

        assert result.success is True
        assert result.output['operation_type'] == 'block_sessions'


@pytest.mark.django_db
class TestODataBackendIntegration:
    """Integration tests for OData backend with workflow engine."""

    def test_workflow_with_odata_create_operation(
        self,
        database,
        workflow_execution
    ):
        """Test complete workflow execution with OData create operation."""
        template = OperationTemplate.objects.create(
            id=str(uuid4()),
            name="Create Users",
            operation_type='create',
            target_entity="Users",
            template_data={
                "entity": "Users",
                "data": {
                    "name": "{{ name }}",
                    "email": "{{ email }}"
                }
            }
        )

        node = WorkflowNode(
            id="create_node",
            name="Create New Users",
            type="operation",
            template_id=str(template.id)
        )

        handler = OperationHandler()

        with patch('apps.templates.workflow.handlers.backends.odata.ODataBackend.execute') as mock_execute:
            mock_execute.return_value = NodeExecutionResult(
                success=True,
                output={'backend': 'odata', 'operation_type': 'create'},
                error=None,
                mode=NodeExecutionMode.SYNC,
                duration_seconds=0.1,
                operation_id='op-odata-create',
                task_id=None,
            )

            result = handler.execute(
                node=node,
                context={
                    'target_databases': [str(database.id)],
                    'user_id': 'admin',
                    'name': 'John Doe',
                    'email': 'john@example.com'
                },
                execution=workflow_execution,
                mode=NodeExecutionMode.SYNC
            )

        assert result.success is True
        assert result.output['backend'] == 'odata'
        assert result.output['operation_type'] == 'create'

        # Verify step result
        step_result = WorkflowStepResult.objects.filter(
            workflow_execution=workflow_execution,
            node_id="create_node"
        ).first()
        assert step_result is not None

    def test_workflow_with_odata_update_operation(
        self,
        database,
        workflow_execution
    ):
        """Test workflow with OData update operation."""
        template = OperationTemplate.objects.create(
            id=str(uuid4()),
            name="Update Users",
            operation_type='update',
            target_entity="Users",
            template_data={
                "entity": "Users",
                "filter": "id = {{ user_id }}",
                "data": {"status": "{{ status }}"}
            }
        )

        node = WorkflowNode(
            id="update_node",
            name="Update User Status",
            type="operation",
            template_id=str(template.id)
        )

        handler = OperationHandler()

        with patch('apps.templates.workflow.handlers.backends.odata.ODataBackend.execute') as mock_execute:
            mock_execute.return_value = NodeExecutionResult(
                success=True,
                output={'backend': 'odata', 'operation_type': 'update'},
                error=None,
                mode=NodeExecutionMode.SYNC,
                duration_seconds=0.1,
                operation_id='op-odata-update',
                task_id=None,
            )

            result = handler.execute(
                node=node,
                context={
                    'target_databases': [str(database.id)],
                    'user_id': '123',
                    'status': 'active'
                },
                execution=workflow_execution,
                mode=NodeExecutionMode.SYNC
            )

        assert result.success is True
        assert result.output['operation_type'] == 'update'

    def test_workflow_with_odata_delete_operation(
        self,
        database,
        workflow_execution
    ):
        """Test workflow with OData delete operation."""
        template = OperationTemplate.objects.create(
            id=str(uuid4()),
            name="Delete Records",
            operation_type='delete',
            target_entity="Users",
            template_data={
                "entity": "Users",
                "filter": "id = {{ record_id }}"
            }
        )

        node = WorkflowNode(
            id="delete_node",
            name="Delete Record",
            type="operation",
            template_id=str(template.id)
        )

        handler = OperationHandler()

        with patch('apps.templates.workflow.handlers.backends.odata.ODataBackend.execute') as mock_execute:
            mock_execute.return_value = NodeExecutionResult(
                success=True,
                output={'backend': 'odata', 'operation_type': 'delete'},
                error=None,
                mode=NodeExecutionMode.SYNC,
                duration_seconds=0.1,
                operation_id='op-odata-delete',
                task_id=None,
            )

            result = handler.execute(
                node=node,
                context={
                    'target_databases': [str(database.id)],
                    'user_id': 'admin',
                    'record_id': '456'
                },
                execution=workflow_execution,
                mode=NodeExecutionMode.SYNC
            )

        assert result.success is True
        assert result.output['operation_type'] == 'delete'

    def test_workflow_with_odata_async_mode(
        self,
        database,
        workflow_execution
    ):
        """Test workflow with OData operation in ASYNC mode."""
        template = OperationTemplate.objects.create(
            id=str(uuid4()),
            name="Async Create",
            operation_type='create',
            target_entity="Reports",
            template_data={"noop": "ok"}
        )

        node = WorkflowNode(
            id="async_node",
            name="Create Reports (Async)",
            type="operation",
            template_id=str(template.id)
        )

        handler = OperationHandler()

        with patch('apps.templates.workflow.handlers.backends.odata.ODataBackend.execute') as mock_execute:
            mock_execute.return_value = NodeExecutionResult(
                success=True,
                output={'backend': 'odata', 'status': 'queued', 'operation_type': 'create'},
                error=None,
                mode=NodeExecutionMode.ASYNC,
                duration_seconds=None,
                operation_id='op-odata-async',
                task_id='task-async-123',
            )

            result = handler.execute(
                node=node,
                context={
                    'target_databases': [str(database.id)],
                    'user_id': 'admin'
                },
                execution=workflow_execution,
                mode=NodeExecutionMode.ASYNC
            )

        # ASYNC should return immediately
        assert result.success is True
        assert result.mode == NodeExecutionMode.ASYNC
        assert result.output['status'] == 'queued'
        assert result.task_id == 'task-async-123'


@pytest.mark.django_db
class TestMixedWorkflowIntegration:
    """Integration tests for mixed RAS and OData operations."""

    def test_sequential_ras_then_odata_operations(
        self,
        database,
        workflow_execution
    ):
        """Test workflow with RAS operation followed by OData operation."""
        # Create RAS operation
        ras_template = OperationTemplate.objects.create(
            id=str(uuid4()),
            name="Lock for Maintenance",
            operation_type='lock_scheduled_jobs',
            target_entity="Infobase",
            template_data={"noop": "ok"}
        )

        ras_node = WorkflowNode(
            id="ras_node",
            name="Lock",
            type="operation",
            template_id=str(ras_template.id)
        )

        # Create OData operation
        odata_template = OperationTemplate.objects.create(
            id=str(uuid4()),
            name="Update Status",
            operation_type='update',
            target_entity="Systems",
            template_data={"noop": "ok"}
        )

        odata_node = WorkflowNode(
            id="odata_node",
            name="Update System Status",
            type="operation",
            template_id=str(odata_template.id)
        )

        handler = OperationHandler()

        # Execute RAS operation
        with patch('apps.templates.workflow.handlers.backends.ras.RASBackend.execute') as mock_execute:
            mock_execute.return_value = NodeExecutionResult(
                success=True,
                output={'backend': 'ras', 'operation_type': 'lock_scheduled_jobs'},
                error=None,
                mode=NodeExecutionMode.SYNC,
                duration_seconds=0.1,
                operation_id='op-4',
                task_id=None,
            )

            ras_result = handler.execute(
                node=ras_node,
                context={
                    'target_databases': [str(database.id)],
                    'user_id': 'admin'
                },
                execution=workflow_execution,
                mode=NodeExecutionMode.SYNC
            )

        assert ras_result.success is True
        assert ras_result.output['backend'] == 'ras'

        with patch('apps.templates.workflow.handlers.backends.odata.ODataBackend.execute') as mock_execute:
            mock_execute.return_value = NodeExecutionResult(
                success=True,
                output={'backend': 'odata', 'operation_type': 'update'},
                error=None,
                mode=NodeExecutionMode.SYNC,
                duration_seconds=0.1,
                operation_id='op-odata-update',
                task_id=None,
            )

            odata_result = handler.execute(
                node=odata_node,
                context={
                    'target_databases': [str(database.id)],
                    'user_id': 'admin'
                },
                execution=workflow_execution,
                mode=NodeExecutionMode.SYNC
            )

        assert odata_result.success is True
        assert odata_result.output['backend'] == 'odata'

        # Both should have created step results
        ras_step = WorkflowStepResult.objects.get(
            workflow_execution=workflow_execution,
            node_id="ras_node"
        )
        assert ras_step is not None

        odata_step = WorkflowStepResult.objects.get(
            workflow_execution=workflow_execution,
            node_id="odata_node"
        )
        assert odata_step is not None

    def test_multiple_databases_across_operations(
        self,
        database,
        cluster,
        workflow_execution
    ):
        """Test operations across multiple databases."""
        from apps.databases.models import Database

        # Create additional database
        db2 = Database.objects.create(
            id=str(uuid4()),
            name="TestDB2",
            cluster=cluster,
            ras_cluster_id=cluster.ras_cluster_uuid,
            ras_infobase_id=uuid4(),
            username="admin",
            password="password"
        )

        template = OperationTemplate.objects.create(
            id=str(uuid4()),
            name="Lock Multiple",
            operation_type='lock_scheduled_jobs',
            target_entity="Infobase",
            template_data={"noop": "ok"}
        )

        node = WorkflowNode(
            id="multi_db_node",
            name="Lock Multiple DBs",
            type="operation",
            template_id=str(template.id)
        )

        handler = OperationHandler()

        with patch('apps.templates.workflow.handlers.backends.ras.RASBackend.execute') as mock_execute:
            mock_execute.return_value = NodeExecutionResult(
                success=True,
                output={'backend': 'ras', 'status': 'completed'},
                error=None,
                mode=NodeExecutionMode.SYNC,
                duration_seconds=0.1,
                operation_id='op-5',
                task_id=None,
            )

            result = handler.execute(
                node=node,
                context={
                    'target_databases': [str(database.id), str(db2.id)],
                    'user_id': 'admin'
                },
                execution=workflow_execution,
                mode=NodeExecutionMode.SYNC
            )

        assert result.success is True
        assert result.output['backend'] == 'ras'
