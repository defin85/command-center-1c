"""Unit tests for RASBackend."""

from unittest.mock import MagicMock, patch

import pytest

from apps.templates.workflow.handlers.backends.ras import RASBackend
from apps.templates.workflow.handlers.backends.base import NodeExecutionMode


class TestRASBackendOperationTypeSupport:
    def test_supported_types_include_ras_ops(self):
        backend = RASBackend()
        assert backend.supports_operation_type('lock_scheduled_jobs') is True
        assert backend.supports_operation_type('unlock_scheduled_jobs') is True
        assert backend.supports_operation_type('terminate_sessions') is True
        assert backend.supports_operation_type('block_sessions') is True
        assert backend.supports_operation_type('unblock_sessions') is True

    def test_supported_types_exclude_odata(self):
        backend = RASBackend()
        assert backend.supports_operation_type('create') is False
        assert backend.supports_operation_type('query') is False


class TestRASBackendExecution:
    def test_execute_async_returns_queued(self, db, operation_template, workflow_execution):
        backend = RASBackend()
        operation = MagicMock()
        operation.id = 'op-1'
        operation.total_tasks = 2

        with patch('apps.templates.workflow.handlers.backends.ras.BatchOperationFactory.create', return_value=operation), \
             patch('apps.templates.workflow.handlers.backends.ras.OperationsService.enqueue_operation') as mock_enqueue:
            mock_enqueue.return_value = MagicMock(success=True, operation_id='op-1')

            result = backend.execute(
                template=operation_template,
                rendered_data={'db_user': 'u', 'db_password': 'p'},
                target_databases=['db-1', 'db-2'],
                context={'user_id': 'tester'},
                execution=workflow_execution,
                mode=NodeExecutionMode.ASYNC,
            )

        assert result.success is True
        assert result.output['status'] == 'queued'
        assert result.output['backend'] == 'ras'

    def test_execute_sync_waits_for_completion(self, db, operation_template, workflow_execution):
        backend = RASBackend()
        operation = MagicMock()
        operation.id = 'op-2'
        operation.total_tasks = 1

        with patch('apps.templates.workflow.handlers.backends.ras.BatchOperationFactory.create', return_value=operation), \
             patch('apps.templates.workflow.handlers.backends.ras.OperationsService.enqueue_operation') as mock_enqueue, \
             patch('apps.templates.workflow.handlers.backends.ras.ResultWaiter.wait') as mock_wait:
            mock_enqueue.return_value = MagicMock(success=True, operation_id='op-2')
            mock_wait.return_value = {'success': True, 'status': 'completed'}

            result = backend.execute(
                template=operation_template,
                rendered_data={'db_user': 'u', 'db_password': 'p'},
                target_databases=['db-1'],
                context={'user_id': 'tester', 'timeout_seconds': 1},
                execution=workflow_execution,
                mode=NodeExecutionMode.SYNC,
            )

        assert result.success is True
        assert result.output['backend'] == 'ras'
        assert result.output['status'] == 'completed'


@pytest.fixture
def operation_template(db):
    return MagicMock(id='tpl-1', name='RAS Op', operation_type='lock_scheduled_jobs')


@pytest.fixture
def workflow_execution(db):
    return MagicMock(id='wf-1')
