from unittest.mock import patch
from uuid import uuid4

import pytest

from apps.operations.factory import BatchOperationFactory
from apps.operations.models import BatchOperation
from apps.operations.services import EnqueueResult
from apps.templates.models import OperationTemplate


@pytest.mark.django_db
class TestOperationHandlerTargetDatabases:
    def test_handler_creates_batch_operation(self, operation_template, test_database, workflow_execution):
        from apps.templates.workflow.handlers import NodeExecutionMode, OperationHandler
        from apps.templates.workflow.models import WorkflowNode

        node = WorkflowNode(
            id="op_node_1",
            name="Operation Node",
            type="operation",
            template_id=operation_template.id,
        )

        context = {"target_databases": [str(test_database.id)], "user_id": "test_user"}
        handler = OperationHandler()

        with patch.object(handler.renderer, "render") as mock_render:
            mock_render.return_value = {"result": "test_data"}
            with patch("apps.operations.services.OperationsService.enqueue_operation") as mock_enqueue:
                mock_enqueue.side_effect = lambda operation_id: EnqueueResult(
                    success=True,
                    operation_id=str(operation_id),
                    status="queued",
                )

                result = handler.execute(
                    node=node,
                    context=context,
                    execution=workflow_execution,
                    mode=NodeExecutionMode.ASYNC,
                )

        assert result.operation_id is not None
        operation = BatchOperation.objects.get(id=result.operation_id)
        assert operation.target_databases.count() == 1
        assert operation.total_tasks == 1

    def test_handler_async_mode_returns_immediately(
        self, operation_template, test_database, workflow_execution
    ):
        from apps.templates.workflow.handlers import NodeExecutionMode, OperationHandler
        from apps.templates.workflow.models import WorkflowNode

        node = WorkflowNode(
            id="async_node",
            name="Async Operation",
            type="operation",
            template_id=operation_template.id,
        )

        context = {"target_databases": [str(test_database.id)]}
        handler = OperationHandler()

        with patch.object(handler.renderer, "render") as mock_render:
            mock_render.return_value = {"data": "test"}
            with patch("apps.operations.services.OperationsService.enqueue_operation") as mock_enqueue:
                mock_enqueue.side_effect = lambda operation_id: EnqueueResult(
                    success=True,
                    operation_id=str(operation_id),
                    status="queued",
                )

                result = handler.execute(
                    node=node,
                    context=context,
                    execution=workflow_execution,
                    mode=NodeExecutionMode.ASYNC,
                )

        assert result.success is True
        assert result.mode == NodeExecutionMode.ASYNC
        assert result.output["status"] == "queued"
        assert result.operation_id is not None
        assert result.task_id == result.operation_id

    def test_handler_sync_mode_waits_for_completion(
        self, operation_template, test_database, workflow_execution
    ):
        from apps.templates.workflow.handlers import NodeExecutionMode, OperationHandler
        from apps.templates.workflow.models import WorkflowNode

        node = WorkflowNode(
            id="sync_node",
            name="Sync Operation",
            type="operation",
            template_id=operation_template.id,
        )
        context = {"target_databases": [str(test_database.id)]}

        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={"test": "data"},
            target_databases=[str(test_database.id)],
        )
        operation.status = BatchOperation.STATUS_COMPLETED
        operation.progress = 100
        operation.completed_tasks = 1
        operation.save()

        handler = OperationHandler()
        with patch.object(handler.renderer, "render") as mock_render:
            mock_render.return_value = {"test": "data"}

            with patch("apps.operations.services.OperationsService.enqueue_operation") as mock_enqueue:
                mock_enqueue.side_effect = lambda operation_id: EnqueueResult(
                    success=True,
                    operation_id=str(operation_id),
                    status="queued",
                )

                with patch(
                    "apps.templates.workflow.handlers.backends.odata.BatchOperationFactory.create"
                ) as mock_factory:
                    mock_factory.return_value = operation
                    result = handler.execute(
                        node=node,
                        context=context,
                        execution=workflow_execution,
                        mode=NodeExecutionMode.SYNC,
                    )

        assert result.success is True
        assert result.mode == NodeExecutionMode.SYNC
        assert result.operation_id == operation.id

    def test_handler_no_target_databases_skips_execution(self, operation_template, workflow_execution):
        from apps.templates.workflow.handlers import NodeExecutionMode, OperationHandler
        from apps.templates.workflow.models import WorkflowNode

        node = WorkflowNode(
            id="skip_node",
            name="Skip Execution",
            type="operation",
            template_id=operation_template.id,
        )

        handler = OperationHandler()
        with patch.object(handler.renderer, "render") as mock_render:
            mock_render.return_value = {"data": "rendered"}
            result = handler.execute(
                node=node,
                context={"dry_run": True},
                execution=workflow_execution,
                mode=NodeExecutionMode.SYNC,
            )

        assert result.success is True
        assert result.output["execution_skipped"] is True
        assert result.operation_id is None
        assert BatchOperation.objects.count() == 0

    def test_handler_allows_global_scope_without_target_databases(self, workflow_execution):
        from apps.templates.workflow.handlers import NodeExecutionMode, OperationHandler
        from apps.templates.workflow.models import WorkflowNode

        template = OperationTemplate.objects.create(
            id="tpl_global_cli_" + str(uuid4())[:8],
            name="Global CLI Template",
            operation_type="designer_cli",
            target_entity="Infobase",
            template_data={},
        )

        node = WorkflowNode(
            id="global_cli_node",
            name="Global CLI Node",
            type="operation",
            template_id=template.id,
        )

        handler = OperationHandler()
        with patch.object(handler.renderer, "render") as mock_render:
            mock_render.return_value = {
                "command": "Any",
                "args": [],
                "options": {"target_scope": "global"},
            }

            with patch("apps.operations.services.OperationsService.enqueue_operation") as mock_enqueue:
                mock_enqueue.side_effect = lambda operation_id: EnqueueResult(
                    success=True,
                    operation_id=str(operation_id),
                    status="queued",
                )

                result = handler.execute(
                    node=node,
                    context={"user_id": "test_user"},
                    execution=workflow_execution,
                    mode=NodeExecutionMode.ASYNC,
                )

        assert result.success is True
        assert result.operation_id is not None

        operation = BatchOperation.objects.get(id=result.operation_id)
        assert operation.target_databases.count() == 0
        assert operation.total_tasks == 1
        task = operation.tasks.get()
        assert task.database_id is None
