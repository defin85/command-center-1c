"""
LoopHandler for Workflow Engine.

Executes loop nodes with count/while/foreach modes.
"""

import logging
import time
from typing import Any, Dict, List

from jinja2 import StrictUndefined
from jinja2.sandbox import ImmutableSandboxedEnvironment

from apps.templates.workflow.models import WorkflowExecution, WorkflowNode

from .base import BaseNodeHandler, NodeExecutionMode, NodeExecutionResult

logger = logging.getLogger(__name__)


class LoopHandler(BaseNodeHandler):
    """
    Handler for Loop nodes.

    Loop modes:
        - count: for i in range(N)
        - while: while condition_is_true (sandboxed Jinja2)
        - foreach: for item in collection

    Context updates for each iteration:
        - loop.index: Current iteration index (0-based)
        - loop.first: True if first iteration
        - loop.last: True if last iteration
        - item: Current item (foreach mode only)

    Safety:
        - max_iterations hardcoded limit (10000)
        - Sandboxed Jinja2 for while condition evaluation
        - ImmutableSandboxedEnvironment with StrictUndefined

    Current Implementation (Week 8):
        - Uses placeholder execute_workflow_node task (Week 9)
        - SYNC mode only
    """

    # Safety limit for loop iterations
    MAX_ITERATIONS_HARD_LIMIT = 10000

    def __init__(self):
        """Initialize LoopHandler with sandboxed Jinja2 environment."""
        # Setup sandbox environment for while condition evaluation
        self.env = ImmutableSandboxedEnvironment(
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=StrictUndefined
        )

        # Whitelist safe globals
        self.env.globals.update({
            'len': len,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
        })

    def execute(
        self,
        node: WorkflowNode,
        context: Dict[str, Any],
        execution: WorkflowExecution,
        mode: NodeExecutionMode = NodeExecutionMode.SYNC
    ) -> NodeExecutionResult:
        """
        Execute loop node based on mode.

        Args:
            node: WorkflowNode with loop_config
            context: Execution context with variables
            execution: WorkflowExecution for tracking
            mode: Execution mode (currently only SYNC supported)

        Returns:
            NodeExecutionResult with iteration results or error
        """
        start_time = time.time()

        # Create step result for audit
        step_result = self._create_step_result(
            execution=execution,
            node=node,
            input_data={'context_keys': list(context.keys())}
        )

        try:
            # 1. Get loop config
            if not node.loop_config:
                raise ValueError(f"Loop node {node.id} missing loop_config")

            loop_config = node.loop_config
            loop_mode = loop_config.mode
            loop_node_id = loop_config.loop_node_id
            max_iterations = min(loop_config.max_iterations, self.MAX_ITERATIONS_HARD_LIMIT)

            logger.info(
                f"Executing loop node {node.id}",
                extra={
                    'node_id': node.id,
                    'mode': loop_mode,
                    'loop_node_id': loop_node_id,
                    'max_iterations': max_iterations
                }
            )

            # 2. Import Celery task (placeholder in Week 8)
            try:
                from apps.templates.tasks import execute_workflow_node
            except ImportError:
                raise NotImplementedError(
                    "execute_workflow_node task not implemented yet (Week 9)"
                )

            # 3. Execute loop based on mode
            if loop_mode == "count":
                result_data = self._execute_count_loop(
                    loop_config, loop_node_id, context, execution, max_iterations
                )
            elif loop_mode == "while":
                result_data = self._execute_while_loop(
                    loop_config, loop_node_id, context, execution, max_iterations
                )
            elif loop_mode == "foreach":
                result_data = self._execute_foreach_loop(
                    loop_config, loop_node_id, context, execution, max_iterations
                )
            else:
                raise ValueError(f"Unknown loop mode: {loop_mode}")

            duration = time.time() - start_time

            # 4. Return success result
            result = NodeExecutionResult(
                success=True,
                output=result_data,
                error=None,
                mode=NodeExecutionMode.SYNC,
                duration_seconds=duration
            )

            self._update_step_result(step_result, result)

            logger.info(
                f"Loop node {node.id} completed successfully",
                extra={
                    'node_id': node.id,
                    'duration_seconds': duration,
                    'iterations': result_data.get('iterations', 0)
                }
            )

            return result

        except NotImplementedError as exc:
            # Expected error for Week 8 (Celery task not implemented yet)
            error_msg = f"Loop execution not available: {str(exc)}"
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
            error_msg = f"Failed to execute loop node: {str(exc)}"
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

    def _execute_count_loop(
        self,
        loop_config: Any,
        loop_node_id: str,
        context: Dict[str, Any],
        execution: WorkflowExecution,
        max_iterations: int
    ) -> Dict[str, Any]:
        """
        Execute count loop: for i in range(N).

        Args:
            loop_config: LoopConfig Pydantic schema
            loop_node_id: Node ID to execute in loop
            context: Execution context
            execution: WorkflowExecution instance
            max_iterations: Maximum iterations allowed

        Returns:
            Dict with iteration results
        """
        if not loop_config.count:
            raise ValueError("count is required for mode='count'")

        count = min(loop_config.count, max_iterations)
        results = []

        for i in range(count):
            # Update context with loop variables
            loop_context = context.copy()
            loop_context['loop'] = {
                'index': i,
                'first': i == 0,
                'last': i == count - 1,
            }

            # Execute loop node (placeholder - will use Celery in Week 9)
            from apps.templates.tasks import execute_workflow_node
            result = execute_workflow_node(str(execution.id), loop_node_id, loop_context)
            results.append({'iteration': i, 'result': result})

        return {
            'mode': 'count',
            'iterations': count,
            'results': results
        }

    def _execute_while_loop(
        self,
        loop_config: Any,
        loop_node_id: str,
        context: Dict[str, Any],
        execution: WorkflowExecution,
        max_iterations: int
    ) -> Dict[str, Any]:
        """
        Execute while loop: while condition_is_true.

        Args:
            loop_config: LoopConfig Pydantic schema
            loop_node_id: Node ID to execute in loop
            context: Execution context
            execution: WorkflowExecution instance
            max_iterations: Maximum iterations allowed

        Returns:
            Dict with iteration results
        """
        if not loop_config.condition:
            raise ValueError("condition is required for mode='while'")

        condition_expr = loop_config.condition
        results = []
        iteration = 0

        while iteration < max_iterations:
            # Update context with loop variables
            loop_context = context.copy()
            loop_context['loop'] = {
                'index': iteration,
                'first': iteration == 0,
            }

            # Evaluate condition in sandbox
            try:
                template = self.env.from_string(condition_expr)
                rendered = template.render(loop_context)
                should_continue = self._to_bool(rendered)
            except Exception as exc:
                logger.error(f"Failed to evaluate while condition: {exc}", exc_info=True)
                break

            if not should_continue:
                break

            # Execute loop node (placeholder - will use Celery in Week 9)
            from apps.templates.tasks import execute_workflow_node
            result = execute_workflow_node(str(execution.id), loop_node_id, loop_context)
            results.append({'iteration': iteration, 'result': result})

            # Update context with result for next iteration
            context.update(result)
            iteration += 1

        return {
            'mode': 'while',
            'iterations': iteration,
            'results': results,
            'max_iterations_reached': iteration >= max_iterations
        }

    def _execute_foreach_loop(
        self,
        loop_config: Any,
        loop_node_id: str,
        context: Dict[str, Any],
        execution: WorkflowExecution,
        max_iterations: int
    ) -> Dict[str, Any]:
        """
        Execute foreach loop: for item in collection.

        Args:
            loop_config: LoopConfig Pydantic schema
            loop_node_id: Node ID to execute in loop
            context: Execution context
            execution: WorkflowExecution instance
            max_iterations: Maximum iterations allowed

        Returns:
            Dict with iteration results
        """
        if not loop_config.items:
            raise ValueError("items is required for mode='foreach'")

        # Get items collection from context using dot notation
        items = self._resolve_path(context, loop_config.items)

        if not isinstance(items, (list, tuple)):
            raise ValueError(f"items must be a list or tuple, got {type(items).__name__}")

        # Limit iterations
        items_limited = items[:max_iterations]
        results = []

        for i, item in enumerate(items_limited):
            # Update context with loop variables
            loop_context = context.copy()
            loop_context['loop'] = {
                'index': i,
                'first': i == 0,
                'last': i == len(items_limited) - 1,
            }
            loop_context['item'] = item

            # Execute loop node (placeholder - will use Celery in Week 9)
            from apps.templates.tasks import execute_workflow_node
            result = execute_workflow_node(str(execution.id), loop_node_id, loop_context)
            results.append({'iteration': i, 'item': item, 'result': result})

        return {
            'mode': 'foreach',
            'iterations': len(items_limited),
            'total_items': len(items),
            'truncated': len(items) > max_iterations,
            'results': results
        }

    def _resolve_path(self, context: Dict[str, Any], path: str) -> Any:
        """
        Resolve dot notation path in context.

        Args:
            context: Execution context
            path: Dot notation path (e.g., 'data.users')

        Returns:
            Resolved value

        Raises:
            KeyError: If path not found
        """
        keys = path.split('.')
        value = context

        for key in keys:
            if isinstance(value, dict):
                value = value[key]
            else:
                raise KeyError(f"Cannot resolve path '{path}': '{key}' not found")

        return value

    def _to_bool(self, value: Any) -> bool:
        """
        Convert rendered value to boolean.

        Args:
            value: Rendered expression value

        Returns:
            bool: Converted boolean value
        """
        # Direct boolean
        if isinstance(value, bool):
            return value

        # String conversion (case-insensitive)
        if isinstance(value, str):
            value_lower = value.strip().lower()
            if value_lower in ('true', 'yes', '1'):
                return True
            elif value_lower in ('false', 'no', '0', '', 'none'):
                return False
            else:
                # Non-empty string -> True (Pythonic)
                return bool(value_lower)

        # Integer conversion
        if isinstance(value, int):
            return value != 0

        # None -> False
        if value is None:
            return False

        # Collections (list, dict, etc.)
        # Empty -> False, non-empty -> True
        return bool(value)
