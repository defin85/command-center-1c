"""
ParallelHandler for Workflow Engine.

Executes multiple workflow nodes in parallel using Celery groups.
"""

import logging
import time
from typing import Any, Dict, List

from celery import group
from celery.result import GroupResult

from apps.templates.workflow.models import WorkflowExecution, WorkflowNode

from .base import BaseNodeHandler, NodeExecutionMode, NodeExecutionResult

logger = logging.getLogger(__name__)


class ParallelHandler(BaseNodeHandler):
    """
    Handler for Parallel nodes.

    Flow:
        1. Get parallel_config from node (parallel_nodes, wait_for, timeout_seconds)
        2. Create Celery group with execute_workflow_node tasks for each parallel node
        3. Execute group based on wait_for mode:
           - "all": Wait for all tasks to complete
           - "any": Wait for any task to complete, cancel others
           - "N": Wait for N tasks to complete, cancel others
        4. Handle timeout with partial results
        5. Return NodeExecutionResult with aggregated outputs

    Current Implementation (Week 8):
        - Uses placeholder execute_workflow_node task (Week 9)
        - SYNC mode only (wait for results before returning)

    Integration:
        - apps.templates.tasks.execute_workflow_node: Celery task (placeholder in Week 8)
    """

    def execute(
        self,
        node: WorkflowNode,
        context: Dict[str, Any],
        execution: WorkflowExecution,
        mode: NodeExecutionMode = NodeExecutionMode.SYNC
    ) -> NodeExecutionResult:
        """
        Execute parallel node by launching Celery group.

        Args:
            node: WorkflowNode with parallel_config
            context: Execution context with variables
            execution: WorkflowExecution for tracking
            mode: Execution mode (currently only SYNC supported)

        Returns:
            NodeExecutionResult with aggregated outputs or error
        """
        start_time = time.time()

        # Create step result for audit
        step_result = self._create_step_result(
            execution=execution,
            node=node,
            input_data={'context_keys': list(context.keys())}
        )

        try:
            # 1. Get parallel config
            if not node.parallel_config:
                raise ValueError(f"Parallel node {node.id} missing parallel_config")

            parallel_config = node.parallel_config
            parallel_nodes = parallel_config.parallel_nodes
            wait_for = parallel_config.wait_for
            timeout_seconds = parallel_config.timeout_seconds

            logger.info(
                f"Executing parallel node {node.id}",
                extra={
                    'node_id': node.id,
                    'parallel_nodes': parallel_nodes,
                    'wait_for': wait_for,
                    'timeout_seconds': timeout_seconds
                }
            )

            # 2. Import Celery task (placeholder in Week 8)
            try:
                from apps.templates.tasks import execute_workflow_node
            except ImportError:
                raise NotImplementedError(
                    "execute_workflow_node task not implemented yet (Week 9)"
                )

            # 3. Create Celery group
            tasks = [
                execute_workflow_node.s(str(execution.id), node_id, context)
                for node_id in parallel_nodes
            ]
            job = group(tasks)

            # 4. Execute group based on wait_for mode
            result_data = self._execute_parallel(
                job, wait_for, timeout_seconds, parallel_nodes
            )

            duration = time.time() - start_time

            # 5. Return success result
            result = NodeExecutionResult(
                success=True,
                output=result_data,
                error=None,
                mode=NodeExecutionMode.SYNC,
                duration_seconds=duration
            )

            self._update_step_result(step_result, result)

            logger.info(
                f"Parallel node {node.id} completed successfully",
                extra={
                    'node_id': node.id,
                    'duration_seconds': duration,
                    'completed_tasks': len(result_data.get('completed', []))
                }
            )

            return result

        except NotImplementedError as exc:
            # Expected error for Week 8 (Celery task not implemented yet)
            error_msg = f"Parallel execution not available: {str(exc)}"
            logger.warning(error_msg, extra={'node_id': node.id})

            result = NodeExecutionResult(
                success=False,
                output=None,
                error=error_msg,
                mode=NodeExecutionMode.SYNC,
                duration_seconds=time.time() - start_time
            )
            self._update_step_result(step_result, result)
            return result

        except Exception as exc:
            error_msg = f"Failed to execute parallel node: {str(exc)}"
            logger.error(
                error_msg,
                extra={'node_id': node.id},
                exc_info=True
            )

            result = NodeExecutionResult(
                success=False,
                output=None,
                error=error_msg,
                mode=NodeExecutionMode.SYNC,
                duration_seconds=time.time() - start_time
            )
            self._update_step_result(step_result, result)
            return result

    def _execute_parallel(
        self,
        job: group,
        wait_for: str,
        timeout_seconds: int,
        node_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Execute Celery group based on wait_for mode.

        Args:
            job: Celery group
            wait_for: Wait mode ("all", "any", or "N")
            timeout_seconds: Timeout in seconds
            node_ids: List of parallel node IDs

        Returns:
            Dict with completed/failed/partial results
        """
        group_result: GroupResult = job.apply_async()

        if wait_for == "all":
            return self._wait_for_all(group_result, timeout_seconds, node_ids)
        elif wait_for == "any":
            return self._wait_for_any(group_result, timeout_seconds, node_ids)
        else:
            # wait_for is a number "N"
            try:
                count = int(wait_for)
                return self._wait_for_count(group_result, timeout_seconds, count, node_ids)
            except ValueError:
                raise ValueError(f"Invalid wait_for value: {wait_for}")

    def _wait_for_all(
        self,
        group_result: GroupResult,
        timeout_seconds: int,
        node_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Wait for all tasks to complete.

        Args:
            group_result: Celery GroupResult
            timeout_seconds: Timeout in seconds
            node_ids: List of parallel node IDs

        Returns:
            Dict with all results
        """
        try:
            results = group_result.get(timeout=timeout_seconds)
            return {
                'mode': 'all',
                'completed': [
                    {'node_id': node_ids[i], 'result': results[i]}
                    for i in range(len(results))
                ],
                'failed': [],
                'timed_out': False
            }
        except Exception as exc:
            logger.warning(f"Timeout waiting for all tasks: {exc}")
            # Return partial results
            completed = []
            failed = []
            for i, async_result in enumerate(group_result.results):
                if async_result.ready():
                    if async_result.successful():
                        completed.append({'node_id': node_ids[i], 'result': async_result.result})
                    else:
                        failed.append({'node_id': node_ids[i], 'error': str(async_result.info)})

            return {
                'mode': 'all',
                'completed': completed,
                'failed': failed,
                'timed_out': True
            }

    def _wait_for_any(
        self,
        group_result: GroupResult,
        timeout_seconds: int,
        node_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Wait for any task to complete, then cancel others.

        Args:
            group_result: Celery GroupResult
            timeout_seconds: Timeout in seconds
            node_ids: List of parallel node IDs

        Returns:
            Dict with first completed result
        """
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            for i, async_result in enumerate(group_result.results):
                if async_result.ready() and async_result.successful():
                    # Cancel remaining tasks
                    self._cancel_tasks(group_result, exclude_index=i)

                    return {
                        'mode': 'any',
                        'completed': [{'node_id': node_ids[i], 'result': async_result.result}],
                        'cancelled': [node_ids[j] for j in range(len(node_ids)) if j != i],
                        'timed_out': False
                    }
            time.sleep(0.1)  # Poll every 100ms

        # Timeout - cancel all tasks
        self._cancel_tasks(group_result)
        return {
            'mode': 'any',
            'completed': [],
            'cancelled': node_ids,
            'timed_out': True
        }

    def _wait_for_count(
        self,
        group_result: GroupResult,
        timeout_seconds: int,
        count: int,
        node_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Wait for N tasks to complete, then cancel others.

        Args:
            group_result: Celery GroupResult
            timeout_seconds: Timeout in seconds
            count: Number of tasks to wait for
            node_ids: List of parallel node IDs

        Returns:
            Dict with N completed results
        """
        if count > len(node_ids):
            raise ValueError(f"wait_for count ({count}) exceeds parallel_nodes count ({len(node_ids)})")

        start_time = time.time()
        completed_indices = []

        while time.time() - start_time < timeout_seconds:
            for i, async_result in enumerate(group_result.results):
                if i not in completed_indices and async_result.ready() and async_result.successful():
                    completed_indices.append(i)

                    if len(completed_indices) >= count:
                        # Cancel remaining tasks
                        self._cancel_tasks(group_result, exclude_indices=completed_indices)

                        return {
                            'mode': f'count_{count}',
                            'completed': [
                                {'node_id': node_ids[i], 'result': group_result.results[i].result}
                                for i in completed_indices
                            ],
                            'cancelled': [
                                node_ids[j] for j in range(len(node_ids)) if j not in completed_indices
                            ],
                            'timed_out': False
                        }
            time.sleep(0.1)  # Poll every 100ms

        # Timeout - cancel all tasks
        self._cancel_tasks(group_result)
        return {
            'mode': f'count_{count}',
            'completed': [
                {'node_id': node_ids[i], 'result': group_result.results[i].result}
                for i in completed_indices
            ],
            'cancelled': [
                node_ids[j] for j in range(len(node_ids)) if j not in completed_indices
            ],
            'timed_out': True
        }

    def _cancel_tasks(
        self,
        group_result: GroupResult,
        exclude_index: int = None,
        exclude_indices: List[int] = None
    ) -> None:
        """
        Cancel tasks in GroupResult.

        Args:
            group_result: Celery GroupResult
            exclude_index: Single index to exclude from cancellation
            exclude_indices: Multiple indices to exclude from cancellation
        """
        exclude_set = set()
        if exclude_index is not None:
            exclude_set.add(exclude_index)
        if exclude_indices:
            exclude_set.update(exclude_indices)

        for i, async_result in enumerate(group_result.results):
            if i not in exclude_set:
                try:
                    async_result.revoke(terminate=True)
                except Exception as exc:
                    logger.warning(f"Failed to cancel task {i}: {exc}")
