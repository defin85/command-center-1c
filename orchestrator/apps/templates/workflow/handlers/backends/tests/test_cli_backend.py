"""Unit tests for CLIBackend."""

from unittest.mock import MagicMock, patch

import pytest

from apps.templates.workflow.handlers.backends.cli import CLIBackend
from apps.templates.workflow.handlers.base import NodeExecutionMode


@pytest.mark.django_db
class TestCLIBackendExecution:
    def test_execute_sync_waits_for_completion(self, db, workflow_execution):
        backend = CLIBackend()

        operation = MagicMock()
        operation.id = 'op-1'
        operation.total_tasks = 1

        template = MagicMock(id='tpl-1', name='CLI Op', operation_type='designer_cli')

        with (
            patch(
                'apps.templates.workflow.handlers.backends.cli.BatchOperationFactory.create',
                return_value=operation,
            ),
            patch('apps.operations.services.OperationsService.enqueue_operation') as mock_enqueue,
            patch('apps.templates.workflow.handlers.backends.cli.ResultWaiter.wait') as mock_wait,
        ):
            mock_enqueue.return_value = MagicMock(success=True, operation_id='op-1', status='queued', error=None)
            mock_wait.return_value = {'success': True, 'status': 'completed'}

            result = backend.execute(
                template=template,
                rendered_data={'command': 'LoadCfg'},
                target_databases=['db-1'],
                context={'user_id': 'tester', 'timeout_seconds': 1},
                execution=workflow_execution,
                mode=NodeExecutionMode.SYNC,
            )

        assert result.success is True
        assert result.mode == NodeExecutionMode.SYNC
        assert result.output['backend'] == 'cli'
        assert result.output['status'] == 'completed'

