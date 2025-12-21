"""
IBCMD Backend for Workflow Engine.

Handles ibcmd-based operations via BatchOperationFactory and Go Worker.
Supports: ibcmd_backup, ibcmd_restore, ibcmd_replicate, ibcmd_create
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
            id='ibcmd_backup',
            name='IBCMD Backup Infobase',
            description='Create an infobase backup using ibcmd.',
            backend=BackendType.IBCMD,
            target_entity=TargetEntity.INFOBASE,
            required_parameters=[
                ParameterSchema('dbms', 'string', description='Database engine (PostgreSQL, MSSQLServer, etc.)'),
                ParameterSchema('db_server', 'string', description='Database server connection string'),
                ParameterSchema('db_name', 'string', description='Database name'),
                ParameterSchema('db_user', 'string', description='Database username'),
                ParameterSchema('db_password', 'string', description='Database password'),
            ],
            optional_parameters=[
                ParameterSchema('output_path', 'string', required=False, description='Backup output path'),
                ParameterSchema('output_name', 'string', required=False, description='Backup file name'),
                ParameterSchema('user', 'string', required=False, description='1C user override'),
                ParameterSchema('password', 'string', required=False, description='1C password override'),
                ParameterSchema('additional_args', 'json', required=False, description='Extra ibcmd arguments'),
            ],
            is_async=True,
            timeout_seconds=600,
            category='admin',
            tags=['ibcmd', 'backup'],
        ),
        OperationType(
            id='ibcmd_restore',
            name='IBCMD Restore Infobase',
            description='Restore an infobase backup using ibcmd.',
            backend=BackendType.IBCMD,
            target_entity=TargetEntity.INFOBASE,
            required_parameters=[
                ParameterSchema('dbms', 'string', description='Database engine (PostgreSQL, MSSQLServer, etc.)'),
                ParameterSchema('db_server', 'string', description='Database server connection string'),
                ParameterSchema('db_name', 'string', description='Database name'),
                ParameterSchema('db_user', 'string', description='Database username'),
                ParameterSchema('db_password', 'string', description='Database password'),
                ParameterSchema('input_path', 'string', description='Backup input path'),
            ],
            optional_parameters=[
                ParameterSchema('create_database', 'boolean', required=False, description='Create database if missing'),
                ParameterSchema('force', 'boolean', required=False, description='Force restore'),
                ParameterSchema('user', 'string', required=False, description='1C user override'),
                ParameterSchema('password', 'string', required=False, description='1C password override'),
                ParameterSchema('additional_args', 'json', required=False, description='Extra ibcmd arguments'),
            ],
            is_async=True,
            timeout_seconds=900,
            category='admin',
            tags=['ibcmd', 'restore'],
        ),
        OperationType(
            id='ibcmd_replicate',
            name='IBCMD Replicate Infobase',
            description='Replicate an infobase to another server using ibcmd.',
            backend=BackendType.IBCMD,
            target_entity=TargetEntity.INFOBASE,
            required_parameters=[
                ParameterSchema('dbms', 'string', description='Source database engine'),
                ParameterSchema('db_server', 'string', description='Source database server connection string'),
                ParameterSchema('db_name', 'string', description='Source database name'),
                ParameterSchema('db_user', 'string', description='Source database username'),
                ParameterSchema('db_password', 'string', description='Source database password'),
                ParameterSchema('target_dbms', 'string', description='Target database engine'),
                ParameterSchema('target_db_server', 'string', description='Target database server connection string'),
                ParameterSchema('target_db_name', 'string', description='Target database name'),
                ParameterSchema('target_db_user', 'string', description='Target database username'),
                ParameterSchema('target_db_password', 'string', description='Target database password'),
            ],
            optional_parameters=[
                ParameterSchema('jobs_count', 'integer', required=False, description='Source jobs count'),
                ParameterSchema('target_jobs_count', 'integer', required=False, description='Target jobs count'),
                ParameterSchema('user', 'string', required=False, description='1C user override'),
                ParameterSchema('password', 'string', required=False, description='1C password override'),
                ParameterSchema('additional_args', 'json', required=False, description='Extra ibcmd arguments'),
            ],
            is_async=True,
            timeout_seconds=1200,
            category='admin',
            tags=['ibcmd', 'replicate'],
        ),
        OperationType(
            id='ibcmd_create',
            name='IBCMD Create Infobase',
            description='Create a new infobase using ibcmd.',
            backend=BackendType.IBCMD,
            target_entity=TargetEntity.INFOBASE,
            required_parameters=[
                ParameterSchema('dbms', 'string', description='Database engine (PostgreSQL, MSSQLServer, etc.)'),
                ParameterSchema('db_server', 'string', description='Database server connection string'),
                ParameterSchema('db_name', 'string', description='Database name'),
                ParameterSchema('db_user', 'string', description='Database username'),
                ParameterSchema('db_password', 'string', description='Database password'),
            ],
            optional_parameters=[
                ParameterSchema('user', 'string', required=False, description='1C user override'),
                ParameterSchema('password', 'string', required=False, description='1C password override'),
                ParameterSchema('additional_args', 'json', required=False, description='Extra ibcmd arguments'),
            ],
            is_async=True,
            timeout_seconds=600,
            category='admin',
            tags=['ibcmd', 'create'],
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
        template: OperationTemplate,
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
                created_by=context.get('user_id', 'workflow'),
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
                    },
                    error=None,
                    mode=mode,
                    duration_seconds=time.time() - start_time,
                    operation_id=str(operation.id),
                    task_id=task_id,
                )

            timeout = context.get('timeout_seconds') or self.DEFAULT_TIMEOUT_SECONDS
            waiter = ResultWaiter(operation.id, timeout_seconds=timeout)

            try:
                result = waiter.wait()
            except OperationTimeoutError:
                logger.warning(
                    "IBCMD operation timed out",
                    extra={
                        'operation_id': operation.id,
                        'timeout_seconds': timeout,
                    },
                )
                raise

            return NodeExecutionResult(
                success=result.success,
                output=result.output,
                error=result.error,
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
