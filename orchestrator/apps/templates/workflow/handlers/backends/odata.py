"""
OData Backend for Workflow Engine.

Handles OData-based operations via BatchOperationFactory and Celery task queue.
Supports: create, update, delete, query, install_extension
"""

import logging
import time
from typing import Any, Dict, List, Set

from apps.operations.factory import BatchOperationFactory
from apps.operations.models import BatchOperation
from apps.operations.waiter import OperationTimeoutError, ResultWaiter
from apps.templates.models import OperationTemplate
from apps.templates.workflow.models import WorkflowExecution

# Import registry types
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


class ODataBackend(AbstractOperationBackend):
    """
    OData Backend for data manipulation operations.

    Executes operations via:
        1. BatchOperationFactory - creates BatchOperation with Tasks
        2. Celery task - enqueues to worker pool
        3. ResultWaiter - waits for completion (SYNC mode)

    Supported operation types:
        - create: Create records via OData POST
        - update: Update records via OData PATCH
        - delete: Delete records via OData DELETE
        - query: Query records via OData GET
        - install_extension: Install .cfe extension via worker direct CLI
    """

    # Operation type definitions with full metadata
    OPERATION_TYPES: List[OperationType] = [
        OperationType(
            id='create',
            name='Create Records',
            description='Create new records in 1C database via OData POST request.',
            backend=BackendType.ODATA,
            target_entity=TargetEntity.ENTITY,
            required_parameters=[
                ParameterSchema('entity_name', 'string', description='OData entity name (e.g., Catalog_Kontragenty)'),
                ParameterSchema('data', 'json', description='Record data to create'),
            ],
            optional_parameters=[],
            is_async=True,
            timeout_seconds=300,
            category='data',
            tags=['odata', 'crud'],
        ),
        OperationType(
            id='update',
            name='Update Records',
            description='Update existing records in 1C database via OData PATCH request.',
            backend=BackendType.ODATA,
            target_entity=TargetEntity.ENTITY,
            required_parameters=[
                ParameterSchema('entity_name', 'string', description='OData entity name'),
                ParameterSchema('key', 'string', description='Record key (GUID or composite key)'),
                ParameterSchema('data', 'json', description='Fields to update'),
            ],
            optional_parameters=[],
            is_async=True,
            timeout_seconds=300,
            category='data',
            tags=['odata', 'crud'],
        ),
        OperationType(
            id='delete',
            name='Delete Records',
            description='Delete records from 1C database via OData DELETE request.',
            backend=BackendType.ODATA,
            target_entity=TargetEntity.ENTITY,
            required_parameters=[
                ParameterSchema('entity_name', 'string', description='OData entity name'),
                ParameterSchema('key', 'string', description='Record key to delete'),
            ],
            optional_parameters=[],
            is_async=True,
            timeout_seconds=300,
            category='data',
            tags=['odata', 'crud'],
        ),
        OperationType(
            id='query',
            name='Query Records',
            description='Query records from 1C database via OData GET request.',
            backend=BackendType.ODATA,
            target_entity=TargetEntity.ENTITY,
            required_parameters=[
                ParameterSchema('entity_name', 'string', description='OData entity name'),
            ],
            optional_parameters=[
                ParameterSchema('filter', 'string', required=False,
                              description='OData $filter expression', default=''),
                ParameterSchema('select', 'string', required=False,
                              description='OData $select fields', default=''),
                ParameterSchema('top', 'integer', required=False,
                              description='Limit number of records', default=100),
            ],
            is_async=True,
            timeout_seconds=300,
            category='data',
            tags=['odata', 'query'],
        ),
        OperationType(
            id='install_extension',
            name='Install Extension',
            description='Install .cfe extension file to 1C database via worker direct CLI.',
            backend=BackendType.ODATA,
            target_entity=TargetEntity.INFOBASE,
            required_parameters=[
                ParameterSchema('extension_path', 'string', description='Path to .cfe file'),
            ],
            optional_parameters=[
                ParameterSchema('restart_after', 'boolean', required=False,
                              description='Restart database after installation', default=False),
            ],
            is_async=True,
            timeout_seconds=600,
            category='admin',
            tags=['extension', 'deployment'],
        ),
    ]

    # Computed from OPERATION_TYPES for backward compatibility
    SUPPORTED_TYPES: Set[str] = {op.id for op in OPERATION_TYPES}

    # Default timeout for SYNC mode (seconds)
    DEFAULT_TIMEOUT_SECONDS = 300

    @classmethod
    def register_operations(cls) -> None:
        """Register all OData operations in the global registry."""
        registry = get_registry()
        registry.register_many(cls.OPERATION_TYPES)

    def execute(
        self,
        template: OperationTemplate,
        rendered_data: Dict[str, Any],
        target_databases: List[str],
        context: Dict[str, Any],
        execution: WorkflowExecution,
        mode: NodeExecutionMode = NodeExecutionMode.SYNC
    ) -> NodeExecutionResult:
        """
        Execute OData operation via BatchOperationFactory.

        Args:
            template: OperationTemplate with operation metadata
            rendered_data: Rendered template data
            target_databases: List of database UUIDs
            context: Execution context
            execution: WorkflowExecution for tracking
            mode: Execution mode (SYNC/ASYNC)

        Returns:
            NodeExecutionResult with operation outcome
        """
        start_time = time.time()

        logger.info(
            "ODataBackend executing operation",
            extra={
                'template_id': template.id,
                'template_name': template.name,
                'operation_type': template.operation_type,
                'target_count': len(target_databases),
                'mode': mode.value
            }
        )

        try:
            # 1. Create BatchOperation via factory
            operation = BatchOperationFactory.create(
                template=template,
                rendered_data=rendered_data,
                target_databases=target_databases,
                workflow_execution_id=str(execution.id) if execution else None,
                node_id=context.get('node_id'),
                created_by=context.get('user_id', 'workflow')
            )

            logger.info(
                "BatchOperation created",
                extra={
                    'operation_id': operation.id,
                    'target_databases_count': len(target_databases)
                }
            )

            # 2. Enqueue to Go Worker
            from apps.operations.services import OperationsService

            enqueue_result = OperationsService.enqueue_operation(str(operation.id))
            task_id = enqueue_result.operation_id if enqueue_result.success else None

            if enqueue_result.success:
                logger.info(
                    f"Operation {operation.id} enqueued to Go Worker",
                    extra={
                        'operation_id': operation.id,
                        'status': enqueue_result.status
                    }
                )
            else:
                logger.warning(
                    f"Go Worker enqueue failed: {enqueue_result.error}, falling back to sync"
                )
                task_id = None

            # 3. SYNC vs ASYNC execution
            if mode == NodeExecutionMode.ASYNC:
                return self._return_async(
                    operation=operation,
                    task_id=task_id,
                    start_time=start_time
                )
            else:
                return self._return_sync(
                    operation=operation,
                    task_id=task_id,
                    context=context,
                    start_time=start_time
                )

        except OperationTimeoutError as exc:
            error_msg = f"OData operation timed out: {str(exc)}"
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
            error_msg = f"OData operation failed: {str(exc)}"
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

        logger.info(
            f"ASYNC operation {operation.id} queued successfully",
            extra={
                'operation_id': operation.id,
                'task_id': task_id,
                'duration_seconds': duration
            }
        )

        return NodeExecutionResult(
            success=True,
            output={
                'operation_id': operation.id,
                'status': 'queued',
                'task_id': task_id,
                'total_tasks': operation.total_tasks,
                'backend': 'odata'
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
        # Get timeout from context or use default
        timeout = context.get('timeout_seconds', self.DEFAULT_TIMEOUT_SECONDS)

        logger.info(
            f"SYNC waiting for operation {operation.id} (timeout: {timeout}s)",
            extra={
                'operation_id': operation.id,
                'timeout_seconds': timeout
            }
        )

        # Wait for completion
        wait_result = ResultWaiter.wait(
            operation_id=operation.id,
            timeout_seconds=timeout
        )

        duration = time.time() - start_time

        logger.info(
            f"SYNC operation {operation.id} completed",
            extra={
                'operation_id': operation.id,
                'success': wait_result['success'],
                'status': wait_result['status'],
                'duration_seconds': duration
            }
        )

        # Add backend info to result
        output = {**wait_result, 'backend': 'odata'}

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
        """Get set of all operation types supported by this backend."""
        return cls.SUPPORTED_TYPES.copy()
