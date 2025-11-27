"""
Celery tasks for Template Engine and Workflow Engine.

Provides async task execution for:
- Single node execution (for parallel/loop handlers)
- Full workflow execution (async mode)
- Node result handling with retry logic
"""

import logging

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from django.db import OperationalError

logger = logging.getLogger(__name__)

# Recoverable exceptions that should trigger retry
# DO NOT include: ValueError, KeyError, TypeError (programming errors)
RECOVERABLE_EXCEPTIONS = (
    OperationalError,  # Database connection issues
    ConnectionError,   # Network issues
    TimeoutError,      # Timeouts
)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    autoretry_for=RECOVERABLE_EXCEPTIONS,
    retry_backoff=True,
    retry_backoff_max=60,
    acks_late=True,
)
def execute_workflow_node(
    self,
    execution_id: str,
    node_id: str,
    context_snapshot: dict
) -> dict:
    """
    Execute single workflow node asynchronously.

    Used by:
    - ParallelHandler (Celery group for parallel execution)
    - LoopHandler (sequential Celery tasks for iterations)
    - SubWorkflowHandler (nested workflow execution)

    Args:
        execution_id: WorkflowExecution UUID (as string)
        node_id: Node ID to execute
        context_snapshot: Execution context snapshot (dict)

    Returns:
        dict: Node execution result with output/error
            {
                'success': bool,
                'node_id': str,
                'output': Any,  # None if failed
                'error': str,   # None if success
                'duration_seconds': float
            }

    Raises:
        MaxRetriesExceededError: If all retry attempts exhausted
    """
    from apps.templates.workflow.context import ContextManager
    from apps.templates.workflow.handlers import NodeExecutionMode, NodeHandlerFactory
    from apps.templates.workflow.models import (
        DAGStructure,
        WorkflowExecution,
    )

    logger.info(
        f"Celery task: executing node {node_id} for execution {execution_id}",
        extra={
            'execution_id': execution_id,
            'node_id': node_id,
            'task_id': self.request.id,
            'retry_count': self.request.retries
        }
    )

    try:
        # Get execution instance
        execution = WorkflowExecution.objects.select_related(
            'workflow_template'
        ).get(id=execution_id)

        # Check execution is still running
        if execution.status != WorkflowExecution.STATUS_RUNNING:
            logger.warning(
                f"Execution {execution_id} is not running (status: {execution.status})",
                extra={'execution_id': execution_id, 'node_id': node_id}
            )
            return {
                'success': False,
                'node_id': node_id,
                'output': None,
                'error': f'Execution is not running (status: {execution.status})',
                'duration_seconds': 0
            }

        # Get DAG structure
        dag = execution.workflow_template.dag_structure
        if not isinstance(dag, DAGStructure):
            dag = DAGStructure(**dag)

        # Find node in DAG
        node = None
        for n in dag.nodes:
            if n.id == node_id:
                node = n
                break

        if not node:
            raise ValueError(f"Node {node_id} not found in DAG")

        # Create context manager
        context = ContextManager(context_snapshot)

        # Get handler
        handler = NodeHandlerFactory.get_handler(node.type)

        # Execute node
        result = handler.execute(
            node=node,
            context=context.to_dict(),
            execution=execution,
            mode=NodeExecutionMode.SYNC  # Execute synchronously within task
        )

        # Prepare return value
        return_data = {
            'success': result.success,
            'node_id': node_id,
            'output': result.output,
            'error': result.error,
            'duration_seconds': result.duration_seconds
        }

        logger.info(
            f"Celery task: node {node_id} completed (success={result.success})",
            extra={
                'execution_id': execution_id,
                'node_id': node_id,
                'success': result.success,
                'duration_seconds': result.duration_seconds
            }
        )

        return return_data

    except WorkflowExecution.DoesNotExist:
        error_msg = f"Execution {execution_id} not found"
        logger.error(error_msg)
        return {
            'success': False,
            'node_id': node_id,
            'output': None,
            'error': error_msg,
            'duration_seconds': 0
        }

    except MaxRetriesExceededError:
        error_msg = f"Max retries exceeded for node {node_id}"
        logger.error(
            error_msg,
            extra={
                'execution_id': execution_id,
                'node_id': node_id,
                'max_retries': self.max_retries
            }
        )
        return {
            'success': False,
            'node_id': node_id,
            'output': None,
            'error': error_msg,
            'duration_seconds': 0
        }

    except Exception as exc:
        logger.error(
            f"Celery task error for node {node_id}: {exc}",
            extra={
                'execution_id': execution_id,
                'node_id': node_id,
                'retry_count': self.request.retries
            },
            exc_info=True
        )

        # Let Celery handle retry if within limits
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        return {
            'success': False,
            'node_id': node_id,
            'output': None,
            'error': str(exc),
            'duration_seconds': 0
        }


@shared_task(
    bind=True,
    acks_late=True,
)
def execute_workflow_async(
    self,
    template_id: str,
    input_context: dict
) -> str:
    """
    Execute entire workflow asynchronously.

    Creates and executes a workflow from template in background.
    Returns immediately with execution_id for status polling.

    Args:
        template_id: WorkflowTemplate UUID (as string)
        input_context: Initial context data for the workflow

    Returns:
        str: execution_id (UUID as string) for status polling

    Example:
        # Start async workflow
        result = execute_workflow_async.delay(str(template.id), {'db_id': '123'})

        # Get execution_id from result
        execution_id = result.get(timeout=10)

        # Poll status
        from apps.templates.workflow.engine import get_workflow_engine
        status = get_workflow_engine().get_execution_status(execution_id)
    """
    from apps.templates.workflow.engine import WorkflowEngine, WorkflowEngineError
    from apps.templates.workflow.models import WorkflowTemplate

    logger.info(
        f"Celery task: starting async workflow for template {template_id}",
        extra={
            'template_id': template_id,
            'task_id': self.request.id,
            'input_keys': list(input_context.keys())
        }
    )

    try:
        # Get template
        template = WorkflowTemplate.objects.get(id=template_id)

        # Execute workflow
        engine = WorkflowEngine()
        execution = engine.execute_workflow(template, input_context)

        logger.info(
            f"Celery task: workflow completed (execution_id={execution.id})",
            extra={
                'template_id': template_id,
                'execution_id': str(execution.id),
                'status': execution.status
            }
        )

        return str(execution.id)

    except WorkflowTemplate.DoesNotExist:
        error_msg = f"Template {template_id} not found"
        logger.error(error_msg)
        raise ValueError(error_msg)

    except WorkflowEngineError as exc:
        logger.error(
            f"Workflow execution failed: {exc.message}",
            extra={
                'template_id': template_id,
                'execution_id': exc.execution_id
            }
        )
        raise

    except Exception as exc:
        logger.error(
            f"Unexpected error in async workflow: {exc}",
            extra={'template_id': template_id},
            exc_info=True
        )
        raise


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=10,
)
def execute_parallel_nodes(
    self,
    execution_id: str,
    node_ids: list,
    context_snapshot: dict,
    wait_for: str = "all"
) -> dict:
    """
    Execute multiple nodes in parallel using Celery group.

    Used by ParallelHandler to execute parallel node branches.

    Args:
        execution_id: WorkflowExecution UUID (as string)
        node_ids: List of node IDs to execute in parallel
        context_snapshot: Execution context snapshot (dict)
        wait_for: Wait strategy - "all", "any", or number (e.g., "2")

    Returns:
        dict: Aggregated results from all parallel nodes
            {
                'success': bool,  # True if wait_for condition satisfied
                'results': {node_id: result_dict, ...},
                'completed_count': int,
                'failed_count': int
            }
    """
    from celery import group

    logger.info(
        f"Celery task: executing {len(node_ids)} nodes in parallel",
        extra={
            'execution_id': execution_id,
            'node_ids': node_ids,
            'wait_for': wait_for,
            'task_id': self.request.id
        }
    )

    try:
        # Create group of tasks
        task_group = group(
            execute_workflow_node.s(execution_id, node_id, context_snapshot)
            for node_id in node_ids
        )

        # Execute group
        group_result = task_group.apply_async()

        # Wait for results based on wait_for strategy
        if wait_for == "any":
            # Return as soon as one completes successfully
            results = {}
            for async_result in group_result:
                try:
                    result = async_result.get(timeout=300)  # 5 min timeout per node
                    results[result['node_id']] = result
                    if result['success']:
                        break  # Found one successful result
                except Exception as exc:
                    logger.warning(f"Parallel node error: {exc}")
                    continue

        elif wait_for.isdigit():
            # Wait for N successful completions
            required_count = int(wait_for)
            results = {}
            success_count = 0

            for async_result in group_result:
                try:
                    result = async_result.get(timeout=300)
                    results[result['node_id']] = result
                    if result['success']:
                        success_count += 1
                        if success_count >= required_count:
                            break
                except Exception as exc:
                    logger.warning(f"Parallel node error: {exc}")
                    continue

        else:  # "all" (default)
            # Wait for all to complete
            all_results = group_result.get(timeout=1800)  # 30 min total timeout
            results = {r['node_id']: r for r in all_results}

        # Aggregate results
        completed_count = sum(1 for r in results.values() if r.get('success', False))
        failed_count = len(results) - completed_count

        # Determine overall success based on wait_for
        if wait_for == "all":
            overall_success = failed_count == 0
        elif wait_for == "any":
            overall_success = completed_count > 0
        elif wait_for.isdigit():
            overall_success = completed_count >= int(wait_for)
        else:
            overall_success = failed_count == 0

        return_data = {
            'success': overall_success,
            'results': results,
            'completed_count': completed_count,
            'failed_count': failed_count,
            'total_count': len(node_ids)
        }

        logger.info(
            f"Parallel execution completed: {completed_count}/{len(node_ids)} successful",
            extra={
                'execution_id': execution_id,
                'completed_count': completed_count,
                'failed_count': failed_count,
                'overall_success': overall_success
            }
        )

        return return_data

    except Exception as exc:
        logger.error(
            f"Parallel execution failed: {exc}",
            extra={
                'execution_id': execution_id,
                'node_ids': node_ids
            },
            exc_info=True
        )

        return {
            'success': False,
            'results': {},
            'completed_count': 0,
            'failed_count': len(node_ids),
            'total_count': len(node_ids),
            'error': str(exc)
        }


@shared_task(bind=True)
def cancel_workflow_async(self, execution_id: str) -> bool:
    """
    Cancel workflow execution asynchronously.

    Args:
        execution_id: WorkflowExecution UUID (as string)

    Returns:
        bool: True if cancelled successfully
    """
    from apps.templates.workflow.engine import WorkflowEngine

    logger.info(
        f"Celery task: cancelling workflow {execution_id}",
        extra={
            'execution_id': execution_id,
            'task_id': self.request.id
        }
    )

    engine = WorkflowEngine()
    return engine.cancel_workflow(execution_id)
