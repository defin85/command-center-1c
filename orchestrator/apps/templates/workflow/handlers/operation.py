"""
OperationHandler for Workflow Engine.

Executes operation nodes by rendering templates and creating batch operations.
Phase 4 Week 17: Full integration with Worker via BatchOperationFactory.
"""

import logging
import time
from typing import Any, Dict, Optional

from apps.databases.models import Database
from apps.operations.factory import BatchOperationFactory
from apps.operations.models import BatchOperation
from apps.operations.tasks import enqueue_operation
from apps.operations.waiter import OperationTimeoutError, ResultWaiter
from apps.templates.engine.exceptions import TemplateRenderError, TemplateValidationError
from apps.templates.engine.renderer import TemplateRenderer
from apps.templates.models import OperationTemplate
from apps.templates.workflow.models import WorkflowExecution, WorkflowNode

from .base import BaseNodeHandler, NodeExecutionMode, NodeExecutionResult

logger = logging.getLogger(__name__)


class OperationHandler(BaseNodeHandler):
    """
    Handler for Operation nodes.

    Flow (Week 17 - Full Integration):
        1. Get OperationTemplate by node.template_id
        2. Render template via TemplateRenderer (Track 1 integration)
        3. Extract target_databases from context
        4. Create BatchOperation via BatchOperationFactory
        5. Enqueue to Worker via Celery task
        6. SYNC: Wait for completion / ASYNC: Return immediately

    Integration:
        - apps.templates.models.OperationTemplate: Template storage
        - apps.templates.engine.renderer.TemplateRenderer: Rendering
        - apps.operations.factory.BatchOperationFactory: Operation creation
        - apps.operations.tasks.enqueue_operation: Celery task
        - apps.operations.waiter.ResultWaiter: Sync waiting
    """

    # Default timeout for SYNC mode (seconds)
    DEFAULT_TIMEOUT_SECONDS = 300

    def __init__(self):
        """Initialize OperationHandler with TemplateRenderer."""
        self.renderer = TemplateRenderer()

    def execute(
        self,
        node: WorkflowNode,
        context: Dict[str, Any],
        execution: WorkflowExecution,
        mode: NodeExecutionMode = NodeExecutionMode.SYNC
    ) -> NodeExecutionResult:
        """
        Execute operation node by rendering template and creating batch operation.

        Args:
            node: WorkflowNode with template_id
            context: Execution context with variables.
                     Expected keys:
                     - target_databases: List[str] - UUIDs of target databases
                     - user_id: str - User who initiated the workflow
            execution: WorkflowExecution for tracking
            mode: Execution mode (SYNC waits for completion, ASYNC returns immediately)

        Returns:
            NodeExecutionResult with operation result or queued status
        """
        start_time = time.time()

        # Create step result for audit
        step_result = self._create_step_result(
            execution=execution,
            node=node,
            input_data={
                'context_keys': list(context.keys()),
                'mode': mode.value
            }
        )

        try:
            # 1. Get OperationTemplate
            if not node.template_id:
                raise ValueError(f"Operation node {node.id} missing template_id")

            template = OperationTemplate.objects.get(id=node.template_id)

            logger.info(
                f"Executing operation node {node.id}",
                extra={
                    'node_id': node.id,
                    'template_id': node.template_id,
                    'template_name': template.name,
                    'mode': mode.value
                }
            )

            # 2. Render template with validation
            rendered_data = self.renderer.render(
                template=template,
                context_data=context,
                validate=True
            )

            # 3. Extract target_databases from context
            target_databases = self._extract_target_databases(context, node)

            if not target_databases:
                # No target databases - return rendered data only (backwards compatibility)
                logger.warning(
                    f"No target_databases in context for node {node.id} - "
                    f"returning rendered data without execution",
                    extra={'node_id': node.id}
                )
                return self._return_rendered_only(
                    rendered_data=rendered_data,
                    step_result=step_result,
                    start_time=start_time
                )

            # 4. Create BatchOperation
            operation = BatchOperationFactory.create(
                template=template,
                rendered_data=rendered_data,
                target_databases=target_databases,
                workflow_execution_id=str(execution.id) if execution else None,
                node_id=str(node.id) if node else None,
                created_by=context.get('user_id', 'workflow')
            )

            logger.info(
                f"BatchOperation created for node {node.id}",
                extra={
                    'node_id': node.id,
                    'operation_id': operation.id,
                    'target_databases_count': len(target_databases)
                }
            )

            # 5. Enqueue to Worker via Celery
            celery_result = enqueue_operation.delay(operation.id)

            logger.info(
                f"Operation {operation.id} enqueued to Celery",
                extra={
                    'node_id': node.id,
                    'operation_id': operation.id,
                    'celery_task_id': celery_result.id
                }
            )

            # 6. SYNC vs ASYNC execution
            if mode == NodeExecutionMode.ASYNC:
                return self._return_async(
                    operation=operation,
                    celery_task_id=celery_result.id,
                    step_result=step_result,
                    start_time=start_time
                )
            else:
                return self._return_sync(
                    operation=operation,
                    celery_task_id=celery_result.id,
                    node=node,
                    step_result=step_result,
                    start_time=start_time
                )

        except OperationTemplate.DoesNotExist:
            error_msg = f"OperationTemplate not found: {node.template_id}"
            logger.error(error_msg, extra={'node_id': node.id, 'template_id': node.template_id})
            return self._return_error(error_msg, step_result, start_time)

        except (TemplateRenderError, TemplateValidationError) as exc:
            error_msg = f"Template rendering failed: {str(exc)}"
            logger.error(
                error_msg,
                extra={'node_id': node.id, 'template_id': node.template_id},
                exc_info=True
            )
            return self._return_error(error_msg, step_result, start_time)

        except OperationTimeoutError as exc:
            error_msg = f"Operation timed out: {str(exc)}"
            logger.error(
                error_msg,
                extra={'node_id': node.id, 'operation_id': exc.operation_id},
                exc_info=True
            )
            return self._return_error(
                error_msg,
                step_result,
                start_time,
                operation_id=exc.operation_id
            )

        except Database.DoesNotExist as exc:
            error_msg = f"Database not found: {str(exc)}"
            logger.error(error_msg, extra={'node_id': node.id}, exc_info=True)
            return self._return_error(error_msg, step_result, start_time)

        except ValueError as exc:
            error_msg = str(exc)
            logger.error(error_msg, extra={'node_id': node.id}, exc_info=True)
            return self._return_error(error_msg, step_result, start_time)

        except Exception as exc:
            error_msg = f"Unexpected error executing operation node: {str(exc)}"
            logger.error(
                error_msg,
                extra={'node_id': node.id},
                exc_info=True
            )
            return self._return_error(error_msg, step_result, start_time)

    def _extract_target_databases(
        self,
        context: Dict[str, Any],
        node: WorkflowNode
    ) -> list:
        """
        Extract target database IDs from context.

        Checks multiple sources:
        1. context['target_databases'] - explicit list
        2. node.config.get('target_databases') - node-level config
        3. context['database_id'] - single database (wrapped in list)

        Args:
            context: Execution context
            node: WorkflowNode with config

        Returns:
            List of database UUIDs (strings)
        """
        # 1. Explicit list in context
        target_dbs = context.get('target_databases')
        if target_dbs:
            # Ensure all are strings
            return [str(db) for db in target_dbs]

        # 2. Node-level config (NodeConfig is a Pydantic model, use getattr)
        if node.config:
            # NodeConfig is a Pydantic model - use model_dump() or getattr
            config_dict = node.config.model_dump() if hasattr(node.config, 'model_dump') else {}
            node_target_dbs = config_dict.get('target_databases')
            if node_target_dbs:
                return [str(db) for db in node_target_dbs]

        # 3. Single database fallback
        single_db = context.get('database_id')
        if single_db:
            return [str(single_db)]

        return []

    def _return_rendered_only(
        self,
        rendered_data: Dict[str, Any],
        step_result,
        start_time: float
    ) -> NodeExecutionResult:
        """Return result with rendered data only (no execution)."""
        duration = time.time() - start_time

        result = NodeExecutionResult(
            success=True,
            output={
                'rendered_data': rendered_data,
                'execution_skipped': True,
                'reason': 'No target databases specified'
            },
            error=None,
            mode=NodeExecutionMode.SYNC,
            duration_seconds=duration,
            operation_id=None,
            task_id=None
        )

        self._update_step_result(step_result, result)
        return result

    def _return_async(
        self,
        operation: BatchOperation,
        celery_task_id: str,
        step_result,
        start_time: float
    ) -> NodeExecutionResult:
        """Return async result immediately after enqueueing."""
        duration = time.time() - start_time

        result = NodeExecutionResult(
            success=True,
            output={
                'operation_id': operation.id,
                'status': 'queued',
                'celery_task_id': celery_task_id,
                'total_tasks': operation.total_tasks
            },
            error=None,
            mode=NodeExecutionMode.ASYNC,
            duration_seconds=duration,
            operation_id=operation.id,
            task_id=celery_task_id
        )

        self._update_step_result(step_result, result)

        logger.info(
            f"ASYNC operation {operation.id} queued successfully",
            extra={
                'operation_id': operation.id,
                'celery_task_id': celery_task_id,
                'duration_seconds': duration
            }
        )

        return result

    def _return_sync(
        self,
        operation: BatchOperation,
        celery_task_id: str,
        node: WorkflowNode,
        step_result,
        start_time: float
    ) -> NodeExecutionResult:
        """Wait for operation completion and return result."""
        # Get timeout from node config or use default (NodeConfig is Pydantic model)
        timeout = self.DEFAULT_TIMEOUT_SECONDS
        if node.config:
            timeout = getattr(node.config, 'timeout_seconds', self.DEFAULT_TIMEOUT_SECONDS)

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

        result = NodeExecutionResult(
            success=wait_result['success'],
            output=wait_result,
            error=wait_result.get('error'),
            mode=NodeExecutionMode.SYNC,
            duration_seconds=duration,
            operation_id=operation.id,
            task_id=celery_task_id
        )

        self._update_step_result(step_result, result)

        logger.info(
            f"SYNC operation {operation.id} completed",
            extra={
                'operation_id': operation.id,
                'success': wait_result['success'],
                'status': wait_result['status'],
                'duration_seconds': duration
            }
        )

        return result

    def _return_error(
        self,
        error_msg: str,
        step_result,
        start_time: float,
        operation_id: Optional[str] = None
    ) -> NodeExecutionResult:
        """Return error result."""
        result = NodeExecutionResult(
            success=False,
            output=None,
            error=error_msg,
            mode=NodeExecutionMode.SYNC,
            duration_seconds=time.time() - start_time,
            operation_id=operation_id,
            task_id=None
        )

        self._update_step_result(step_result, result)
        return result
