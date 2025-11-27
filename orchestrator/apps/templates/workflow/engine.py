"""
WorkflowEngine for executing workflow templates.

High-level API for workflow execution with:
- Singleton pattern (thread-safe)
- Workflow lifecycle management (start, execute, cancel)
- FSM state transitions
- Error aggregation
- OpenTelemetry tracing integration (Week 12)
"""

import logging
import threading
from typing import Any, Dict, Optional

from django.db import transaction

from apps.templates.tracing import (
    add_span_event,
    get_current_trace_id,
    set_span_attribute,
    set_span_error,
    start_workflow_span,
)
from apps.templates.consumers import (
    sync_broadcast_execution_completed,
    sync_broadcast_workflow_update,
)
from apps.templates.workflow.context import ContextManager
from apps.templates.workflow.executor import DAGExecutor
from apps.templates.workflow.models import (
    DAGStructure,
    WorkflowExecution,
    WorkflowTemplate,
)

logger = logging.getLogger(__name__)


class WorkflowEngineError(Exception):
    """Exception raised by WorkflowEngine."""

    def __init__(self, message: str, execution_id: Optional[str] = None):
        """
        Initialize workflow engine error.

        Args:
            message: Error description
            execution_id: Related execution ID (optional)
        """
        self.message = message
        self.execution_id = execution_id
        super().__init__(self.message)


class WorkflowEngine:
    """
    High-level API for workflow execution.

    Features:
    - Singleton pattern (thread-safe with double-checked locking)
    - Workflow lifecycle management (start, execute, cancel)
    - FSM state transitions (pending -> running -> completed/failed/cancelled)
    - Error aggregation and reporting
    - OpenTelemetry tracing integration (Week 12)

    Usage:
        engine = WorkflowEngine()
        execution = engine.execute_workflow(template, {'database_id': '123'})
        print(execution.status)  # 'completed' or 'failed'
        print(execution.final_result)  # Result data
    """

    _instance: Optional["WorkflowEngine"] = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls) -> "WorkflowEngine":
        """
        Thread-safe singleton instantiation.

        Uses double-checked locking pattern for performance.
        """
        if cls._instance is None:
            with cls._lock:
                # Double-check inside lock
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize WorkflowEngine (called once due to singleton)."""
        # Prevent re-initialization
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            logger.info("Initializing WorkflowEngine singleton")
            self._initialized = True

    def execute_workflow(
        self,
        template: WorkflowTemplate,
        input_context: Dict[str, Any]
    ) -> WorkflowExecution:
        """
        Execute workflow template synchronously.

        Steps:
        1. Validate template (if not validated)
        2. Create WorkflowExecution (status=pending)
        3. Start execution (FSM transition pending->running)
        4. Execute DAG via DAGExecutor
        5. Complete/Fail execution (FSM transition)
        6. Return execution with final_result

        Args:
            template: WorkflowTemplate instance to execute
            input_context: Initial context data for the workflow

        Returns:
            WorkflowExecution: Completed execution with final_result

        Raises:
            WorkflowEngineError: If execution cannot be started
        """
        logger.info(
            f"Starting workflow execution for template '{template.name}'",
            extra={
                'template_id': str(template.id),
                'template_name': template.name,
                'input_keys': list(input_context.keys())
            }
        )

        # Step 1: Validate template if needed
        if not template.is_valid:
            try:
                template.validate()
                template.save(update_fields=['is_valid'])
            except ValueError as exc:
                raise WorkflowEngineError(
                    f"Template validation failed: {exc}"
                )

        # Check template is active
        if not template.is_active:
            raise WorkflowEngineError(
                f"Template '{template.name}' is not active"
            )

        # Step 2: Create WorkflowExecution
        execution = template.create_execution(input_context)

        logger.info(
            f"Created execution {execution.id}",
            extra={
                'execution_id': str(execution.id),
                'template_id': str(template.id)
            }
        )

        # Step 3: Start OpenTelemetry span for entire workflow
        with start_workflow_span(
            workflow_id=str(template.id),
            workflow_name=template.name,
            execution_id=str(execution.id),
            template_id=str(template.id)
        ) as span:
            # Store trace_id in execution for correlation
            trace_id = get_current_trace_id()
            if trace_id:
                execution.set_trace_id(trace_id)
                execution.save(update_fields=['trace_id'])

            try:
                # Step 4: Start execution (FSM transition)
                with transaction.atomic():
                    execution.start()
                    execution.save(update_fields=['status', 'started_at'])

                logger.info(
                    f"Execution {execution.id} started",
                    extra={'execution_id': str(execution.id)}
                )

                # Broadcast workflow started via WebSocket
                sync_broadcast_workflow_update(
                    execution_id=str(execution.id),
                    status='running',
                    progress=0.0,
                    trace_id=trace_id
                )

                if span:
                    add_span_event("workflow_started")

                # Step 5: Execute DAG
                success, result = self._execute_dag(template, execution, input_context)

                # Step 6: Complete or Fail execution
                with transaction.atomic():
                    if success:
                        execution.complete(result)
                        execution.save(update_fields=[
                            'status', 'final_result', 'completed_at'
                        ])

                        logger.info(
                            f"Execution {execution.id} completed successfully",
                            extra={
                                'execution_id': str(execution.id),
                                'duration_seconds': execution.duration
                            }
                        )

                        # Broadcast workflow completion via WebSocket
                        sync_broadcast_execution_completed(
                            execution_id=str(execution.id),
                            status='completed',
                            result=result,
                            duration_ms=int((execution.duration or 0) * 1000)
                        )

                        if span:
                            set_span_attribute("workflow.status", "completed")
                            set_span_attribute("workflow.duration_seconds", execution.duration)
                            add_span_event("workflow_completed")
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        error_node = result.get('node_id')

                        execution.fail(error_msg, error_node)
                        execution.save(update_fields=[
                            'status', 'error_message', 'error_node_id', 'completed_at'
                        ])

                        logger.error(
                            f"Execution {execution.id} failed: {error_msg}",
                            extra={
                                'execution_id': str(execution.id),
                                'error_node': error_node,
                                'duration_seconds': execution.duration
                            }
                        )

                        # Broadcast workflow failure via WebSocket
                        sync_broadcast_execution_completed(
                            execution_id=str(execution.id),
                            status='failed',
                            error_message=error_msg,
                            duration_ms=int((execution.duration or 0) * 1000)
                        )

                        if span:
                            set_span_attribute("workflow.status", "failed")
                            set_span_attribute("workflow.error", error_msg)
                            if error_node:
                                set_span_attribute("workflow.error_node_id", error_node)
                            add_span_event("workflow_failed", {"error": error_msg})

                return execution

            except Exception as exc:
                # Handle unexpected errors
                logger.error(
                    f"Unexpected error during execution {execution.id}: {exc}",
                    extra={'execution_id': str(execution.id)},
                    exc_info=True
                )

                # Record error in span
                if span:
                    set_span_error(exc)

                # Try to mark as failed
                try:
                    with transaction.atomic():
                        # Refresh to get current state
                        execution.refresh_from_db()

                        if execution.status == WorkflowExecution.STATUS_RUNNING:
                            execution.fail(str(exc))
                            execution.save(update_fields=[
                                'status', 'error_message', 'completed_at'
                            ])
                except Exception as save_exc:
                    logger.error(
                        f"Failed to save error state: {save_exc}",
                        extra={'execution_id': str(execution.id)}
                    )

                return execution

    def _execute_dag(
        self,
        template: WorkflowTemplate,
        execution: WorkflowExecution,
        input_context: Dict[str, Any]
    ) -> tuple:
        """
        Execute DAG using DAGExecutor.

        Args:
            template: WorkflowTemplate with DAG structure
            execution: WorkflowExecution for state tracking
            input_context: Initial context data

        Returns:
            Tuple[success, result_or_error]
        """
        # Get DAG structure (Pydantic object or dict)
        dag = template.dag_structure
        if not isinstance(dag, DAGStructure):
            dag = DAGStructure(**dag)

        # Create context manager
        context = ContextManager(input_context)

        # Create executor
        executor = DAGExecutor(dag, execution)

        # Execute
        return executor.execute(context)

    def cancel_workflow(self, execution_id: str) -> bool:
        """
        Cancel running workflow execution.

        Args:
            execution_id: UUID of execution to cancel (as string)

        Returns:
            True if cancelled successfully, False otherwise
        """
        try:
            execution = WorkflowExecution.objects.get(id=execution_id)

            # Check if can be cancelled (pending or running)
            if execution.status not in [
                WorkflowExecution.STATUS_PENDING,
                WorkflowExecution.STATUS_RUNNING
            ]:
                logger.warning(
                    f"Cannot cancel execution {execution_id}: status is {execution.status}",
                    extra={'execution_id': execution_id}
                )
                return False

            with transaction.atomic():
                execution.cancel()
                execution.save(update_fields=['status', 'completed_at'])

            logger.info(
                f"Execution {execution_id} cancelled",
                extra={'execution_id': execution_id}
            )

            # Broadcast cancellation via WebSocket
            sync_broadcast_execution_completed(
                execution_id=str(execution_id),
                status='cancelled'
            )

            return True

        except WorkflowExecution.DoesNotExist:
            logger.error(
                f"Execution not found: {execution_id}",
                extra={'execution_id': execution_id}
            )
            return False

        except Exception as exc:
            logger.error(
                f"Error cancelling execution {execution_id}: {exc}",
                extra={'execution_id': execution_id},
                exc_info=True
            )
            return False

    def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        """
        Get current execution status with progress.

        Args:
            execution_id: UUID of execution (as string)

        Returns:
            Dict with status, progress, and result/error information
        """
        try:
            execution = WorkflowExecution.objects.select_related(
                'workflow_template'
            ).get(id=execution_id)

            status_info = {
                'execution_id': str(execution.id),
                'template_name': execution.workflow_template.name,
                'status': execution.status,
                'progress_percent': float(execution.progress_percent),
                'current_node_id': execution.current_node_id,
                'completed_nodes': execution.completed_nodes,
                'failed_nodes': execution.failed_nodes,
                'started_at': execution.started_at.isoformat() if execution.started_at else None,
                'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
                'duration_seconds': execution.duration,
            }

            # Add result or error based on status
            if execution.status == WorkflowExecution.STATUS_COMPLETED:
                status_info['result'] = execution.final_result
            elif execution.status == WorkflowExecution.STATUS_FAILED:
                status_info['error'] = execution.error_message
                status_info['error_node_id'] = execution.error_node_id

            return status_info

        except WorkflowExecution.DoesNotExist:
            return {
                'execution_id': execution_id,
                'status': 'not_found',
                'error': f'Execution {execution_id} not found'
            }

        except Exception as exc:
            logger.error(
                f"Error getting execution status {execution_id}: {exc}",
                extra={'execution_id': execution_id},
                exc_info=True
            )
            return {
                'execution_id': execution_id,
                'status': 'error',
                'error': str(exc)
            }

    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """
        Get WorkflowExecution instance by ID.

        Args:
            execution_id: UUID of execution (as string)

        Returns:
            WorkflowExecution or None if not found
        """
        try:
            return WorkflowExecution.objects.select_related(
                'workflow_template'
            ).get(id=execution_id)
        except WorkflowExecution.DoesNotExist:
            return None

    @classmethod
    def reset_singleton(cls) -> None:
        """
        Reset singleton instance (for testing only).

        WARNING: This method is intended for testing purposes only.
        Do not use in production code.
        """
        with cls._lock:
            cls._instance = None
            cls._initialized = False

        logger.warning("WorkflowEngine singleton reset (testing only)")


# ============================================================================
# Convenience function for quick access
# ============================================================================


def get_workflow_engine() -> WorkflowEngine:
    """
    Get WorkflowEngine singleton instance.

    Convenience function for accessing the engine without
    explicit instantiation.

    Returns:
        WorkflowEngine: Singleton instance
    """
    return WorkflowEngine()
