"""
WorkflowEngine for executing workflow templates.

High-level API for workflow execution with:
- Singleton pattern (thread-safe)
- Workflow lifecycle management (start, execute, cancel)
- FSM state transitions
- Error aggregation
- OpenTelemetry tracing integration (Week 12)
"""

import asyncio
import logging
import threading
from typing import Any, Dict, Optional

from asgiref.sync import async_to_sync, sync_to_async
from django.db import transaction

from apps.templates.tracing import (
    add_span_event,
    get_current_trace_id,
    set_span_attribute,
    set_span_error,
    start_workflow_span,
)
from apps.templates.consumers import (
    broadcast_execution_completed,
    broadcast_workflow_update,
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
        execution = await engine.execute_workflow(template, {'database_id': '123'})
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

    async def execute_workflow(
        self,
        template: WorkflowTemplate,
        input_context: Dict[str, Any]
    ) -> WorkflowExecution:
        """
        Execute workflow template asynchronously.

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
        # Step 1: Validate template if needed
        if not template.is_valid:
            try:
                await sync_to_async(template.validate, thread_sensitive=True)()
                await sync_to_async(
                    template.save,
                    thread_sensitive=True
                )(update_fields=['is_valid'])
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
        execution = await sync_to_async(
            template.create_execution,
            thread_sensitive=True
        )(input_context)

        logger.info(
            f"Created execution {execution.id}",
            extra={
                'execution_id': str(execution.id),
                'template_id': str(template.id)
            }
        )

        return await self.execute(execution)

    async def execute(self, execution: WorkflowExecution) -> WorkflowExecution:
        """
        Execute an existing workflow execution asynchronously.

        Args:
            execution: Existing WorkflowExecution instance

        Returns:
            WorkflowExecution: Updated execution with final_result/status
        """
        template = await sync_to_async(
            WorkflowTemplate.objects.get,
            thread_sensitive=True
        )(id=execution.workflow_template_id)
        input_context = execution.input_context or {}

        logger.info(
            f"Starting workflow execution for template '{template.name}'",
            extra={
                'template_id': str(template.id),
                'template_name': template.name,
                'input_keys': list(input_context.keys())
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
                await sync_to_async(
                    execution.save,
                    thread_sensitive=True
                )(update_fields=['trace_id'])

            try:
                # Step 4: Start execution (FSM transition)
                def _start_execution():
                    with transaction.atomic():
                        execution.start()
                        execution.save(update_fields=['status', 'started_at'])

                await sync_to_async(_start_execution, thread_sensitive=True)()

                logger.info(
                    f"Execution {execution.id} started",
                    extra={'execution_id': str(execution.id)}
                )

                # Broadcast workflow started via WebSocket
                await broadcast_workflow_update(
                    execution_id=str(execution.id),
                    status='running',
                    progress=0.0,
                    trace_id=trace_id
                )

                if span:
                    add_span_event("workflow_started")

                # Step 5: Execute DAG
                success, result = await self._execute_dag(template, execution, input_context)

                # Step 6: Complete or Fail execution
                def _complete_execution():
                    with transaction.atomic():
                        execution.complete(result)
                        execution.save(update_fields=[
                            'status', 'final_result', 'completed_at'
                        ])

                def _fail_execution(error_msg: str, error_node: Optional[str]):
                    with transaction.atomic():
                        execution.fail(error_msg, error_node)
                        execution.save(update_fields=[
                            'status', 'error_message', 'error_node_id', 'completed_at'
                        ])

                if success:
                    await sync_to_async(_complete_execution, thread_sensitive=True)()

                    logger.info(
                        f"Execution {execution.id} completed successfully",
                        extra={
                            'execution_id': str(execution.id),
                            'duration_seconds': execution.duration
                        }
                    )

                    # Broadcast workflow completion via WebSocket
                    await broadcast_execution_completed(
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

                    await sync_to_async(
                        _fail_execution,
                        thread_sensitive=True
                    )(error_msg, error_node)

                    logger.error(
                        f"Execution {execution.id} failed: {error_msg}",
                        extra={
                            'execution_id': str(execution.id),
                            'error_node': error_node,
                            'duration_seconds': execution.duration
                        }
                    )

                    # Broadcast workflow failure via WebSocket
                    await broadcast_execution_completed(
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
                error_message = str(exc)
                logger.error(
                    f"Unexpected error during execution {execution.id}: {error_message}",
                    extra={'execution_id': str(execution.id)},
                    exc_info=True
                )

                # Record error in span
                if span:
                    set_span_error(exc)

                # Try to mark as failed
                def _mark_failed():
                    with transaction.atomic():
                        # Refresh to get current state
                        execution.refresh_from_db()

                        if execution.status == WorkflowExecution.STATUS_RUNNING:
                            execution.fail(error_message)
                            execution.save(update_fields=[
                                'status', 'error_message', 'completed_at'
                            ])

                try:
                    await sync_to_async(_mark_failed, thread_sensitive=True)()
                except Exception as save_exc:
                    logger.error(
                        f"Failed to save error state: {save_exc}",
                        extra={'execution_id': str(execution.id)}
                    )

                return execution

    async def _execute_dag(
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
        return await executor.execute(context)

    async def cancel_workflow(self, execution_id: str) -> bool:
        """
        Cancel running workflow execution.

        Args:
            execution_id: UUID of execution to cancel (as string)

        Returns:
            True if cancelled successfully, False otherwise
        """
        try:
            execution = await sync_to_async(
                WorkflowExecution.objects.get,
                thread_sensitive=True
            )(id=execution_id)

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

            def _cancel_execution():
                with transaction.atomic():
                    execution.cancel()
                    execution.save(update_fields=['status', 'completed_at'])

            await sync_to_async(_cancel_execution, thread_sensitive=True)()

            logger.info(
                f"Execution {execution_id} cancelled",
                extra={'execution_id': execution_id}
            )

            # Broadcast cancellation via WebSocket
            await broadcast_execution_completed(
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

    async def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        """
        Get current execution status with progress.

        Args:
            execution_id: UUID of execution (as string)

        Returns:
            Dict with status, progress, and result/error information
        """
        try:
            execution = await sync_to_async(
                WorkflowExecution.objects.select_related(
                    'workflow_template'
                ).get,
                thread_sensitive=True
            )(id=execution_id)

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

    async def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """
        Get WorkflowExecution instance by ID.

        Args:
            execution_id: UUID of execution (as string)

        Returns:
            WorkflowExecution or None if not found
        """
        try:
            return await sync_to_async(
                WorkflowExecution.objects.select_related(
                    'workflow_template'
                ).get,
                thread_sensitive=True
            )(id=execution_id)
        except WorkflowExecution.DoesNotExist:
            return None

    @staticmethod
    def _run_async(coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            async def runner():
                return await coro

            return async_to_sync(runner)()
        raise RuntimeError("Cannot call sync wrapper from async context")

    def execute_workflow_sync(
        self,
        template: WorkflowTemplate,
        input_context: Dict[str, Any]
    ) -> WorkflowExecution:
        return self._run_async(self.execute_workflow(template, input_context))

    def execute_sync(self, execution: WorkflowExecution) -> WorkflowExecution:
        return self._run_async(self.execute(execution))

    def cancel_workflow_sync(self, execution_id: str) -> bool:
        return self._run_async(self.cancel_workflow(execution_id))

    def get_execution_status_sync(self, execution_id: str) -> Dict[str, Any]:
        return self._run_async(self.get_execution_status(execution_id))

    def get_execution_sync(self, execution_id: str) -> Optional[WorkflowExecution]:
        return self._run_async(self.get_execution(execution_id))

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
