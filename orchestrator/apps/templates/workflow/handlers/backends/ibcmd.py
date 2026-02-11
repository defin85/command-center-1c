"""
IBCMD CLI Backend for Workflow Engine.

Handles schema-driven ibcmd_cli operations via BatchOperationFactory and Go Worker.
"""

import logging
import time
from typing import Any, Dict, List, Set

from apps.operations.factory import BatchOperationFactory
from apps.operations.waiter import ResultWaiter
from apps.templates.workflow.models import WorkflowExecution

from apps.templates.registry import (
    get_registry,
    OperationType,
    BackendType,
    TargetEntity,
)

from ..base import NodeExecutionMode, NodeExecutionResult
from .base import AbstractOperationBackend

logger = logging.getLogger(__name__)


class IBCMDBackend(AbstractOperationBackend):
    """
    IBCMD Backend for infobase administration operations.

    Executes operations via:
        1. BatchOperationFactory - creates BatchOperation with Tasks
        2. Go Worker - executes ibcmd operations
        3. ResultWaiter - waits for completion (SYNC mode)
    """

    OPERATION_TYPES: List[OperationType] = [
        OperationType(
            id='ibcmd_cli',
            name='IBCMD CLI',
            description='Schema-driven IBCMD command execution.',
            backend=BackendType.IBCMD,
            target_entity=TargetEntity.INFOBASE,
            is_async=True,
            timeout_seconds=900,
            category='admin',
            tags=['ibcmd', 'cli'],
        ),
    ]

    SUPPORTED_TYPES: Set[str] = {op.id for op in OPERATION_TYPES}

    DEFAULT_TIMEOUT_SECONDS = 600

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
            "IBCMDBackend executing operation",
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
                    "IBCMD operation enqueued to Go Worker",
                    extra={
                        'operation_id': operation.id,
                        'target_databases_count': len(target_databases),
                    },
                )
            else:
                logger.warning(
                    "Failed to enqueue IBCMD operation",
                    extra={
                        'operation_id': operation.id,
                        'error': enqueue_result.error,
                    },
                )

            if mode == NodeExecutionMode.ASYNC:
                return NodeExecutionResult(
                    success=True,
                    output={
                        'operation_id': str(operation.id),
                        'queued': enqueue_result.success,
                        'status': operation.status,
                        'backend': 'ibcmd',
                    },
                    error=None,
                    mode=mode,
                    duration_seconds=time.time() - start_time,
                    operation_id=str(operation.id),
                    task_id=task_id,
                )

            timeout_seconds = context.get('timeout_seconds', self.DEFAULT_TIMEOUT_SECONDS)
            wait_result = ResultWaiter.wait(
                operation_id=operation.id,
                timeout_seconds=timeout_seconds,
            )
            output = {**wait_result, 'backend': 'ibcmd'}
            return NodeExecutionResult(
                success=wait_result['success'],
                output=output,
                error=wait_result.get('error'),
                mode=mode,
                duration_seconds=time.time() - start_time,
                operation_id=str(operation.id),
                task_id=task_id,
            )

        except Exception as exc:
            logger.error(
                "IBCMD operation execution failed",
                extra={
                    'template_id': template.id,
                    'operation_type': template.operation_type,
                    'error': str(exc),
                },
                exc_info=True,
            )
            return NodeExecutionResult(
                success=False,
                output=None,
                error=str(exc),
                mode=mode,
                duration_seconds=time.time() - start_time,
                operation_id=None,
                task_id=None,
            )

    def supports_operation_type(self, operation_type: str) -> bool:
        """Check if this backend supports the given operation type."""
        return operation_type in self.SUPPORTED_TYPES

    @classmethod
    def get_supported_types(cls) -> Set[str]:
        """Get set of all operation types supported by this backend."""
        return set(cls.SUPPORTED_TYPES)
