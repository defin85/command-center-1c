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
from apps.templates.models import OperationTemplate
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
        template: OperationTemplate,
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
                created_by=context.get('user_id', 'workflow'),
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
                    },
                )

                if mode == NodeExecutionMode.ASYNC:
                    return NodeExecutionResult(
                        success=True,
                        status='queued',
                        data={
                            'operation_id': str(operation.id),
                            'task_id': task_id,
                        },
                    )

                timeout_seconds = getattr(template, 'timeout_seconds', None) or self.DEFAULT_TIMEOUT_SECONDS
                waiter = ResultWaiter(str(operation.id), timeout_seconds=timeout_seconds)
                result = waiter.wait()

                return NodeExecutionResult(
                    success=result.get('success', False),
                    status=result.get('status', 'unknown'),
                    data=result,
                    error=result.get('error'),
                )

            logger.error(
                "Failed to enqueue CLI operation to Go Worker",
                extra={'operation_id': operation.id, 'error': enqueue_result.error},
            )

            return NodeExecutionResult(
                success=False,
                status='failed',
                error=enqueue_result.error or 'Failed to enqueue operation',
            )

        except OperationTimeoutError as exc:
            logger.error(
                "CLI operation timed out",
                extra={'error': str(exc), 'template_id': template.id},
            )
            return NodeExecutionResult(
                success=False,
                status='timeout',
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "CLI operation execution failed",
                extra={'error': str(exc), 'template_id': template.id},
            )
            return NodeExecutionResult(
                success=False,
                status='failed',
                error=str(exc),
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

    def supports_operation_type(self, operation_type: str) -> bool:
        return operation_type in self.SUPPORTED_TYPES

    @classmethod
    def get_supported_types(cls) -> Set[str]:
        return cls.SUPPORTED_TYPES
