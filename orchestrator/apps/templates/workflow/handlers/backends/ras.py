"""
RAS Backend for Workflow Engine.

Handles RAS-based cluster management operations via Go Worker:
- lock_scheduled_jobs: Block scheduled jobs (reglament tasks)
- unlock_scheduled_jobs: Enable scheduled jobs
- terminate_sessions: Terminate all sessions for infobase
- block_sessions: Block new user connections
- unblock_sessions: Allow new user connections
"""

import logging
import time
from typing import Any, Dict, List, Set

from apps.operations.factory import BatchOperationFactory
from apps.operations.models import BatchOperation
from apps.operations.waiter import OperationTimeoutError, ResultWaiter
from apps.templates.workflow.models import WorkflowExecution

from apps.templates.registry import (
    get_registry,
    OperationType,
    BackendType,
    TargetEntity,
    ParameterSchema,
)

from ..base import NodeExecutionMode, NodeExecutionResult
from .base import AbstractOperationBackend

logger = logging.getLogger(__name__)


class RASBackend(AbstractOperationBackend):
    """
    RAS Backend for cluster management operations.

    Executes operations via BatchOperationFactory and Go Worker.

    Supported operation types:
        - lock_scheduled_jobs: Disable scheduled jobs
        - unlock_scheduled_jobs: Enable scheduled jobs
        - terminate_sessions: Terminate all sessions
        - block_sessions: Block new connections
        - unblock_sessions: Allow new connections
    """

    OPERATION_TYPES: List[OperationType] = [
        OperationType(
            id='lock_scheduled_jobs',
            name='Lock Scheduled Jobs',
            description='Disable scheduled jobs (reglament tasks) for infobase. '
                       'Jobs will not run until unlocked.',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
            required_parameters=[
                ParameterSchema('db_user', 'string', description='Database administrator username'),
                ParameterSchema('db_password', 'string', description='Database administrator password'),
            ],
            optional_parameters=[],
            is_async=False,
            timeout_seconds=30,
            category='admin',
            tags=['cluster', 'jobs', 'maintenance'],
        ),
        OperationType(
            id='unlock_scheduled_jobs',
            name='Unlock Scheduled Jobs',
            description='Enable scheduled jobs (reglament tasks) for infobase. '
                       'Jobs will resume according to their schedule.',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
            required_parameters=[
                ParameterSchema('db_user', 'string', description='Database administrator username'),
                ParameterSchema('db_password', 'string', description='Database administrator password'),
            ],
            optional_parameters=[],
            is_async=False,
            timeout_seconds=30,
            category='admin',
            tags=['cluster', 'jobs', 'maintenance'],
        ),
        OperationType(
            id='terminate_sessions',
            name='Terminate Sessions',
            description='Terminate all active user sessions for infobase. '
                       'Users will be disconnected immediately.',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
            required_parameters=[],
            optional_parameters=[],
            is_async=False,
            timeout_seconds=60,
            category='admin',
            tags=['cluster', 'sessions', 'maintenance'],
        ),
        OperationType(
            id='block_sessions',
            name='Block Sessions',
            description='Block new user connections to infobase. '
                       'Existing sessions are not affected.',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
            required_parameters=[
                ParameterSchema('db_user', 'string', description='Database administrator username'),
                ParameterSchema('db_password', 'string', description='Database administrator password'),
            ],
            optional_parameters=[
                ParameterSchema('denied_message', 'string', required=False,
                              description='Message shown to users trying to connect', default=''),
                ParameterSchema('permission_code', 'string', required=False,
                              description='Permission code to bypass block', default=''),
            ],
            is_async=False,
            timeout_seconds=30,
            category='admin',
            tags=['cluster', 'sessions', 'access'],
        ),
        OperationType(
            id='unblock_sessions',
            name='Unblock Sessions',
            description='Allow new user connections to infobase. '
                       'Removes session blocking.',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
            required_parameters=[
                ParameterSchema('db_user', 'string', description='Database administrator username'),
                ParameterSchema('db_password', 'string', description='Database administrator password'),
            ],
            optional_parameters=[],
            is_async=False,
            timeout_seconds=30,
            category='admin',
            tags=['cluster', 'sessions', 'access'],
        ),
    ]

    SUPPORTED_TYPES: Set[str] = {op.id for op in OPERATION_TYPES}

    DEFAULT_TIMEOUT_SECONDS = 60

    @classmethod
    def register_operations(cls) -> None:
        """Register all RAS operations in the global registry."""
        registry = get_registry()
        registry.register_many(cls.OPERATION_TYPES)

    def execute(
        self,
        template: Any,
        rendered_data: Dict[str, Any],
        target_databases: List[str],
        context: Dict[str, Any],
        execution: WorkflowExecution,
        mode: NodeExecutionMode = NodeExecutionMode.SYNC
    ) -> NodeExecutionResult:
        """Execute RAS operation on target databases via Go Worker."""
        start_time = time.time()
        operation_type = template.operation_type

        logger.info(
            "RASBackend executing operation",
            extra={
                'template_id': template.id,
                'template_name': template.name,
                'operation_type': operation_type,
                'target_count': len(target_databases),
                'mode': mode.value
            }
        )

        try:
            operation = BatchOperationFactory.create(
                template=template,
                rendered_data=rendered_data,
                target_databases=target_databases,
                workflow_execution_id=str(execution.id) if execution else None,
                node_id=context.get('node_id'),
                created_by=(
                    context.get('executed_by')
                    or context.get('user_id', 'workflow')
                ),
            )

            from apps.operations.services import OperationsService

            enqueue_result = OperationsService.enqueue_operation(str(operation.id))
            task_id = enqueue_result.operation_id if enqueue_result.success else None

            if not enqueue_result.success:
                logger.warning(
                    "Go Worker enqueue failed for RAS operation, falling back to sync wait",
                    extra={'operation_id': operation.id, 'error': enqueue_result.error}
                )
                task_id = None

            if mode == NodeExecutionMode.ASYNC:
                return self._return_async(operation=operation, task_id=task_id, start_time=start_time)
            return self._return_sync(operation=operation, task_id=task_id, context=context, start_time=start_time)

        except OperationTimeoutError as exc:
            error_msg = f"RAS operation timed out: {str(exc)}"
            logger.error(error_msg, extra={'operation_id': exc.operation_id}, exc_info=True)
            return NodeExecutionResult(
                success=False,
                output=None,
                error=error_msg,
                mode=mode,
                duration_seconds=time.time() - start_time,
                operation_id=exc.operation_id,
                task_id=None
            )

        except Exception as exc:
            error_msg = f"RAS operation failed: {str(exc)}"
            logger.error(error_msg, exc_info=True)
            return NodeExecutionResult(
                success=False,
                output=None,
                error=error_msg,
                mode=mode,
                duration_seconds=time.time() - start_time,
                operation_id=None,
                task_id=None
            )

    def _return_async(
        self,
        operation: BatchOperation,
        task_id: str,
        start_time: float
    ) -> NodeExecutionResult:
        """Return async result immediately after enqueueing."""
        duration = time.time() - start_time
        return NodeExecutionResult(
            success=True,
            output={
                'operation_id': operation.id,
                'status': 'queued',
                'task_id': task_id,
                'total_tasks': operation.total_tasks,
                'backend': 'ras'
            },
            error=None,
            mode=NodeExecutionMode.ASYNC,
            duration_seconds=duration,
            operation_id=operation.id,
            task_id=task_id
        )

    def _return_sync(
        self,
        operation: BatchOperation,
        task_id: str,
        context: Dict[str, Any],
        start_time: float
    ) -> NodeExecutionResult:
        """Wait for operation completion and return result."""
        timeout = context.get('timeout_seconds', self.DEFAULT_TIMEOUT_SECONDS)
        wait_result = ResultWaiter.wait(operation_id=operation.id, timeout_seconds=timeout)
        duration = time.time() - start_time
        output = {**wait_result, 'backend': 'ras'}
        return NodeExecutionResult(
            success=wait_result['success'],
            output=output,
            error=wait_result.get('error'),
            mode=NodeExecutionMode.SYNC,
            duration_seconds=duration,
            operation_id=operation.id,
            task_id=task_id
        )

    def supports_operation_type(self, operation_type: str) -> bool:
        """Check if this backend supports the given operation type."""
        return operation_type in self.SUPPORTED_TYPES

    @classmethod
    def get_supported_types(cls) -> Set[str]:
        """Return supported operation types."""
        return cls.SUPPORTED_TYPES
