"""
ParallelHandler for Workflow Engine.

Executes multiple workflow nodes in parallel using ThreadPoolExecutor.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from typing import Any, Dict, List

from apps.templates.workflow.models import WorkflowExecution, WorkflowNode

from .base import BaseNodeHandler, NodeExecutionMode, NodeExecutionResult

logger = logging.getLogger(__name__)


class ParallelHandler(BaseNodeHandler):
    """
    Handler for Parallel nodes.

    Flow:
        1. Get parallel_config from node (parallel_nodes, wait_for, timeout_seconds)
        2. Execute nodes in parallel using ThreadPoolExecutor
        3. Execute based on wait_for mode:
           - "all": Wait for all tasks to complete
           - "any": Wait for any task to complete
           - "N": Wait for N tasks to complete
        4. Handle timeout with partial results
        5. Return NodeExecutionResult with aggregated outputs

    Current Implementation:
        - Uses ThreadPoolExecutor for parallel execution (replaces Celery groups)
        - SYNC mode only (wait for results before returning)
    """

    # Default max workers for parallel execution
    DEFAULT_MAX_WORKERS = 10

    def execute(
        self,
        node: WorkflowNode,
        context: Dict[str, Any],
        execution: WorkflowExecution,
        mode: NodeExecutionMode = NodeExecutionMode.SYNC
    ) -> NodeExecutionResult:
        """
        Execute parallel node using ThreadPoolExecutor.

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

            # 2. Execute nodes in parallel using ThreadPoolExecutor
            result_data = self._execute_parallel(
                execution=execution,
                parallel_nodes=parallel_nodes,
                context=context,
                wait_for=wait_for,
                timeout_seconds=timeout_seconds
            )

            duration = time.time() - start_time

            # 3. Return success result
            success, error = self._evaluate_result(
                wait_for=wait_for,
                total_nodes=len(parallel_nodes),
                result_data=result_data,
            )
            result = NodeExecutionResult(
                success=success,
                output=result_data,
                error=error,
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

    @staticmethod
    def _evaluate_result(wait_for: str, total_nodes: int, result_data: Dict[str, Any]) -> tuple[bool, str | None]:
        timed_out = bool(result_data.get('timed_out'))
        failed = result_data.get('failed') or []
        completed = result_data.get('completed') or []

        if timed_out:
            return False, "Parallel execution timed out"

        if failed:
            return False, f"{len(failed)} parallel nodes failed"

        if wait_for == "all":
            if len(completed) != total_nodes:
                return False, "Not all parallel nodes completed"
            return True, None

        if wait_for == "any":
            if len(completed) == 0:
                return False, "No parallel nodes completed"
            return True, None

        try:
            expected = int(wait_for)
        except ValueError:
            return False, f"Invalid wait_for value: {wait_for}"

        if len(completed) < expected:
            return False, f"Only {len(completed)}/{expected} parallel nodes completed"
        return True, None

    def _execute_parallel(
        self,
        execution: WorkflowExecution,
        parallel_nodes: List[str],
        context: Dict[str, Any],
        wait_for: str,
        timeout_seconds: int
    ) -> Dict[str, Any]:
        """
        Execute nodes in parallel using ThreadPoolExecutor.

        Args:
            execution: WorkflowExecution instance
            parallel_nodes: List of node IDs to execute in parallel
            context: Execution context
            wait_for: Wait mode ("all", "any", or "N")
            timeout_seconds: Timeout in seconds

        Returns:
            Dict with completed/failed/partial results
        """
        max_workers = min(len(parallel_nodes), self.DEFAULT_MAX_WORKERS)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_node: Dict[Future, str] = {}
            for node_id in parallel_nodes:
                future = executor.submit(
                    self._execute_node_sync,
                    str(execution.id),
                    node_id,
                    context.copy()  # Copy context for each node
                )
                future_to_node[future] = node_id

            # Execute based on wait_for mode
            if wait_for == "all":
                return self._wait_for_all(future_to_node, timeout_seconds, parallel_nodes)
            elif wait_for == "any":
                return self._wait_for_any(future_to_node, timeout_seconds, parallel_nodes)
            else:
                # wait_for is a number "N"
                try:
                    count = int(wait_for)
                    return self._wait_for_count(future_to_node, timeout_seconds, count, parallel_nodes)
                except ValueError:
                    raise ValueError(f"Invalid wait_for value: {wait_for}")

    @staticmethod
    def _cancel_tasks(future_to_node: Dict[Future, str], exclude_node_ids: set[str] | None = None) -> List[str]:
        cancelled: List[str] = []
        excluded = exclude_node_ids or set()
        for future, node_id in future_to_node.items():
            if node_id in excluded:
                continue
            if future.done():
                continue
            if future.cancel():
                cancelled.append(node_id)
        return cancelled

    def _wait_for_all(
        self,
        future_to_node: Dict[Future, str],
        timeout_seconds: int,
        node_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Wait for all tasks to complete.

        Args:
            future_to_node: Dict mapping futures to node IDs
            timeout_seconds: Timeout in seconds
            node_ids: List of parallel node IDs

        Returns:
            Dict with all results
        """
        completed = []
        failed = []
        timed_out = False
        processed_futures: set[Future] = set()

        try:
            for future in as_completed(future_to_node.keys(), timeout=timeout_seconds):
                processed_futures.add(future)
                node_id = future_to_node[future]
                try:
                    result = future.result()
                    if result.get('success', False):
                        completed.append({'node_id': node_id, 'result': result})
                    else:
                        failed.append({'node_id': node_id, 'error': result.get('error', 'Unknown error')})
                except Exception as exc:
                    failed.append({'node_id': node_id, 'error': str(exc)})

        except TimeoutError:
            logger.warning("Timeout waiting for all parallel tasks")
            timed_out = True
            # Check which futures completed
            for future, node_id in future_to_node.items():
                if future in processed_futures:
                    continue
                if future.done():
                    try:
                        result = future.result(timeout=0)
                        if result.get('success', False):
                            completed.append({'node_id': node_id, 'result': result})
                        else:
                            failed.append({'node_id': node_id, 'error': result.get('error', 'Unknown error')})
                    except Exception as exc:
                        failed.append({'node_id': node_id, 'error': str(exc)})
                else:
                    future.cancel()

        return {
            'mode': 'all',
            'completed': completed,
            'failed': failed,
            'timed_out': timed_out
        }

    def _wait_for_any(
        self,
        future_to_node: Dict[Future, str],
        timeout_seconds: int,
        node_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Wait for any task to complete, then cancel others.

        Args:
            future_to_node: Dict mapping futures to node IDs
            timeout_seconds: Timeout in seconds
            node_ids: List of parallel node IDs

        Returns:
            Dict with first completed result
        """
        try:
            # Wait for first completed future
            for future in as_completed(future_to_node.keys(), timeout=timeout_seconds):
                node_id = future_to_node[future]
                try:
                    result = future.result()
                    if result.get('success', False):
                        # Cancel remaining futures
                        cancelled = self._cancel_tasks(future_to_node, exclude_node_ids={node_id})

                        return {
                            'mode': 'any',
                            'completed': [{'node_id': node_id, 'result': result}],
                            'cancelled': cancelled,
                            'timed_out': False
                        }
                except Exception:
                    continue  # Try next completed future

        except TimeoutError:
            pass

        # Timeout or all failed - cancel remaining
        self._cancel_tasks(future_to_node)
        return {
            'mode': 'any',
            'completed': [],
            'cancelled': node_ids,
            'timed_out': True
        }

    def _wait_for_count(
        self,
        future_to_node: Dict[Future, str],
        timeout_seconds: int,
        count: int,
        node_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Wait for N tasks to complete, then cancel others.

        Args:
            future_to_node: Dict mapping futures to node IDs
            timeout_seconds: Timeout in seconds
            count: Number of tasks to wait for
            node_ids: List of parallel node IDs

        Returns:
            Dict with N completed results
        """
        if count > len(node_ids):
            raise ValueError(f"wait_for count ({count}) exceeds parallel_nodes count ({len(node_ids)})")

        completed = []
        completed_node_ids = set()

        try:
            for future in as_completed(future_to_node.keys(), timeout=timeout_seconds):
                node_id = future_to_node[future]
                try:
                    result = future.result()
                    if result.get('success', False):
                        completed.append({'node_id': node_id, 'result': result})
                        completed_node_ids.add(node_id)

                        if len(completed) >= count:
                            # Cancel remaining futures
                            cancelled = self._cancel_tasks(
                                future_to_node,
                                exclude_node_ids=completed_node_ids,
                            )

                            return {
                                'mode': f'count_{count}',
                                'completed': completed,
                                'cancelled': cancelled,
                                'timed_out': False
                            }
                except Exception:
                    continue

        except TimeoutError:
            pass

        # Timeout - cancel remaining
        cancelled = self._cancel_tasks(future_to_node, exclude_node_ids=completed_node_ids)

        return {
            'mode': f'count_{count}',
            'completed': completed,
            'cancelled': cancelled,
            'timed_out': True
        }

    def _execute_node_sync(
        self,
        execution_id: str,
        node_id: str,
        context_snapshot: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute single workflow node synchronously.

        This is a sync replacement for the Celery execute_workflow_node task.
        Used by parallel execution to execute child nodes.

        Args:
            execution_id: WorkflowExecution UUID (as string)
            node_id: Node ID to execute
            context_snapshot: Execution context snapshot (dict)

        Returns:
            dict: Node execution result with output/error
        """
        from apps.templates.workflow.context import ContextManager
        from apps.templates.workflow.handlers import NodeExecutionMode, NodeHandlerFactory
        from apps.templates.workflow.models import (
            DAGStructure,
            WorkflowExecution,
        )

        start_time = time.time()

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
                mode=NodeExecutionMode.SYNC
            )

            duration = time.time() - start_time

            logger.info(
                f"Parallel sync execution: node {node_id} completed (success={result.success})",
                extra={
                    'execution_id': execution_id,
                    'node_id': node_id,
                    'success': result.success,
                    'duration_seconds': duration
                }
            )

            return {
                'success': result.success,
                'node_id': node_id,
                'output': result.output,
                'error': result.error,
                'duration_seconds': duration
            }

        except WorkflowExecution.DoesNotExist:
            error_msg = f"Execution {execution_id} not found"
            logger.error(error_msg)
            return {
                'success': False,
                'node_id': node_id,
                'output': None,
                'error': error_msg,
                'duration_seconds': time.time() - start_time
            }

        except Exception as exc:
            error_msg = f"Failed to execute node {node_id}: {str(exc)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'node_id': node_id,
                'output': None,
                'error': error_msg,
                'duration_seconds': time.time() - start_time
            }
