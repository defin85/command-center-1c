"""
CLI Backend for Workflow Engine.

Handles designer CLI operations via BatchOperationFactory and Go Worker.
Supports: designer_cli
"""

import logging
import time
from typing import Any, Dict, List, Set

from apps.operations.factory import BatchOperationFactory
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


class CLIBackend(AbstractOperationBackend):
    """
    CLI Backend for direct DESIGNER batch commands.

    Executes operations via:
        1. BatchOperationFactory - creates BatchOperation with Tasks
        2. Go Worker - executes designer_cli
        3. ResultWaiter - waits for completion (SYNC mode)
    """

    OPERATION_TYPES: List[OperationType] = [
        OperationType(
            id='designer_cli',
            name='Designer CLI',
            description='Execute 1C DESIGNER batch command via worker CLI.',
            backend=BackendType.CLI,
            target_entity=TargetEntity.INFOBASE,
            required_parameters=[
                ParameterSchema('command', 'string', description='DESIGNER command name (e.g., LoadCfg, UpdateDBCfg)'),
            ],
            optional_parameters=[
                ParameterSchema('args', 'json', required=False, description='Command arguments array'),
                ParameterSchema('options', 'json', required=False, description='CLI options (disable_startup_messages, disable_startup_dialogs)'),
            ],
            is_async=True,
            timeout_seconds=900,
            category='admin',
            tags=['cli', 'designer'],
        ),
    ]

    SUPPORTED_TYPES: Set[str] = {op.id for op in OPERATION_TYPES}

    DEFAULT_TIMEOUT_SECONDS = 900

    @classmethod
    def register_operations(cls) -> None:
        registry = get_registry()
        registry.register_many(cls.OPERATION_TYPES)

    def execute(
        self,
        template: Any,
        rendered_data: Dict[str, Any],
        target_databases: List[str],
        context: Dict[str, Any],
        execution: WorkflowExecution,
        mode: NodeExecutionMode = NodeExecutionMode.SYNC,
    ) -> NodeExecutionResult:
        start_time = time.time()

        logger.info(
            "CLIBackend executing operation",
            extra={
                'template_id': template.id,
                'template_name': template.name,
                'operation_type': template.operation_type,
                'target_count': len(target_databases),
                'mode': mode.value,
            },
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

            if enqueue_result.success:
                logger.info(
                    "CLI operation enqueued to Go Worker",
                    extra={
                        'operation_id': operation.id,
                        'target_databases_count': len(target_databases),
                        'mode': mode.value,
                    },
                )
            else:
                logger.warning(
                    "Go Worker enqueue failed for CLI operation",
                    extra={
                        'operation_id': operation.id,
                        'status': enqueue_result.status,
                        'error': enqueue_result.error,
                        'mode': mode.value,
                    },
                )

            if mode == NodeExecutionMode.ASYNC:
                if not enqueue_result.success:
                    return NodeExecutionResult(
                        success=False,
                        output=None,
                        error=enqueue_result.error or 'Failed to enqueue operation',
                        mode=NodeExecutionMode.ASYNC,
                        duration_seconds=time.time() - start_time,
                        operation_id=str(operation.id),
                        task_id=None,
                    )
                return self._return_async(operation=operation, task_id=task_id, start_time=start_time)

            if not enqueue_result.success and enqueue_result.status != 'duplicate':
                return NodeExecutionResult(
                    success=False,
                    output=None,
                    error=enqueue_result.error or 'Failed to enqueue operation',
                    mode=NodeExecutionMode.SYNC,
                    duration_seconds=time.time() - start_time,
                    operation_id=str(operation.id),
                    task_id=None,
                )

            return self._return_sync(operation=operation, task_id=task_id, context=context, start_time=start_time)

        except OperationTimeoutError as exc:
            error_msg = f"CLI operation timed out: {str(exc)}"
            logger.error(
                "CLI operation timed out",
                extra={'error': str(exc), 'template_id': template.id, 'operation_id': exc.operation_id},
            )
            return NodeExecutionResult(
                success=False,
                output=None,
                error=error_msg,
                mode=mode,
                duration_seconds=time.time() - start_time,
                operation_id=exc.operation_id,
                task_id=None,
            )
        except Exception as exc:  # noqa: BLE001
            error_msg = f"CLI operation failed: {str(exc)}"
            logger.exception(
                "CLI operation execution failed",
                extra={'error': str(exc), 'template_id': template.id},
            )
            return NodeExecutionResult(
                success=False,
                output=None,
                error=error_msg,
                mode=mode,
                duration_seconds=time.time() - start_time,
                operation_id=None,
                task_id=None,
            )
        finally:
            duration = time.time() - start_time
            logger.info(
                "CLIBackend operation completed",
                extra={
                    'template_id': template.id,
                    'duration': duration,
                    'status': 'done',
                },
            )

    def _return_async(
        self,
        operation,
        task_id: str,
        start_time: float,
    ) -> NodeExecutionResult:
        duration = time.time() - start_time
        return NodeExecutionResult(
            success=True,
            output={
                'operation_id': str(operation.id),
                'status': 'queued',
                'task_id': task_id,
                'total_tasks': operation.total_tasks,
                'backend': 'cli',
            },
            error=None,
            mode=NodeExecutionMode.ASYNC,
            duration_seconds=duration,
            operation_id=str(operation.id),
            task_id=task_id,
        )

    def _return_sync(
        self,
        operation,
        task_id: str,
        context: Dict[str, Any],
        start_time: float,
    ) -> NodeExecutionResult:
        timeout_seconds = context.get('timeout_seconds', self.DEFAULT_TIMEOUT_SECONDS)
        wait_result = ResultWaiter.wait(
            operation_id=operation.id,
            timeout_seconds=timeout_seconds,
        )
        duration = time.time() - start_time
        output = {**wait_result, 'backend': 'cli'}
        return NodeExecutionResult(
            success=wait_result['success'],
            output=output,
            error=wait_result.get('error'),
            mode=NodeExecutionMode.SYNC,
            duration_seconds=duration,
            operation_id=str(operation.id),
            task_id=task_id,
        )

    def supports_operation_type(self, operation_type: str) -> bool:
        return operation_type in self.SUPPORTED_TYPES

    @classmethod
    def get_supported_types(cls) -> Set[str]:
        return cls.SUPPORTED_TYPES
