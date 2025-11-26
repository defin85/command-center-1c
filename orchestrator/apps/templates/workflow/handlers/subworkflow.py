"""
SubWorkflowHandler for Workflow Engine.

Executes nested workflow templates with input/output mapping.
"""

import logging
import time
from typing import Any, Dict

from apps.templates.workflow.models import WorkflowExecution, WorkflowNode, WorkflowTemplate

from .base import BaseNodeHandler, NodeExecutionMode, NodeExecutionResult

logger = logging.getLogger(__name__)


class SubWorkflowHandler(BaseNodeHandler):
    """
    Handler for SubWorkflow nodes.

    Flow:
        1. Get subworkflow_config (subworkflow_id, input_mapping, output_mapping, max_depth)
        2. Check recursion depth to prevent infinite loops
        3. Map input context using input_mapping (dot notation support)
        4. Execute subworkflow via WorkflowEngine
        5. Map output context using output_mapping
        6. Return NodeExecutionResult with mapped outputs

    Safety:
        - max_depth hardcoded limit (20)
        - Recursion depth tracking via _subworkflow_depth in context
        - Prevents circular workflow references

    Current Implementation (Week 8):
        - Uses placeholder WorkflowEngine (Week 9)
        - SYNC mode only

    Integration:
        - apps.templates.workflow.engine.WorkflowEngine: Workflow executor (placeholder in Week 8)
    """

    # Safety limit for subworkflow recursion depth
    MAX_DEPTH_HARD_LIMIT = 20

    def execute(
        self,
        node: WorkflowNode,
        context: Dict[str, Any],
        execution: WorkflowExecution,
        mode: NodeExecutionMode = NodeExecutionMode.SYNC
    ) -> NodeExecutionResult:
        """
        Execute subworkflow node.

        Args:
            node: WorkflowNode with subworkflow_config
            context: Execution context with variables
            execution: WorkflowExecution for tracking
            mode: Execution mode (currently only SYNC supported)

        Returns:
            NodeExecutionResult with mapped outputs or error
        """
        start_time = time.time()

        # Create step result for audit
        step_result = self._create_step_result(
            execution=execution,
            node=node,
            input_data={'context_keys': list(context.keys())}
        )

        try:
            # 1. Get subworkflow config
            if not node.subworkflow_config:
                raise ValueError(f"SubWorkflow node {node.id} missing subworkflow_config")

            subworkflow_config = node.subworkflow_config
            subworkflow_id = subworkflow_config.subworkflow_id
            input_mapping = subworkflow_config.input_mapping
            output_mapping = subworkflow_config.output_mapping
            max_depth = min(subworkflow_config.max_depth, self.MAX_DEPTH_HARD_LIMIT)

            logger.info(
                f"Executing subworkflow node {node.id}",
                extra={
                    'node_id': node.id,
                    'subworkflow_id': subworkflow_id,
                    'max_depth': max_depth
                }
            )

            # 2. Check recursion depth
            current_depth = context.get('_subworkflow_depth', 0)
            if current_depth >= max_depth:
                raise RecursionError(
                    f"Subworkflow recursion depth exceeded: {current_depth} >= {max_depth}"
                )

            # 3. Get subworkflow template
            try:
                subworkflow_template = WorkflowTemplate.objects.get(id=subworkflow_id)
            except WorkflowTemplate.DoesNotExist:
                raise ValueError(f"Subworkflow template not found: {subworkflow_id}")

            if not subworkflow_template.is_valid or not subworkflow_template.is_active:
                raise ValueError(
                    f"Subworkflow template {subworkflow_id} is not valid or not active"
                )

            # 4. Map input context
            subworkflow_context = self._map_context(
                context, input_mapping, direction='input'
            )

            # Add recursion depth tracking
            subworkflow_context['_subworkflow_depth'] = current_depth + 1

            # 5. Execute subworkflow via WorkflowEngine (placeholder in Week 8)
            try:
                from apps.templates.workflow.engine import WorkflowEngine
                engine = WorkflowEngine()
                subworkflow_result = engine.execute_workflow(
                    subworkflow_template, subworkflow_context
                )
            except ImportError:
                raise NotImplementedError(
                    "WorkflowEngine not implemented yet (Week 9)"
                )

            # 6. Map output context
            mapped_output = self._map_context(
                subworkflow_result, output_mapping, direction='output'
            )

            duration = time.time() - start_time

            # 7. Return success result
            result = NodeExecutionResult(
                success=True,
                output=mapped_output,
                error=None,
                mode=NodeExecutionMode.SYNC,
                duration_seconds=duration
            )

            self._update_step_result(step_result, result)

            logger.info(
                f"SubWorkflow node {node.id} completed successfully",
                extra={
                    'node_id': node.id,
                    'subworkflow_id': subworkflow_id,
                    'duration_seconds': duration,
                    'recursion_depth': current_depth + 1
                }
            )

            return result

        except NotImplementedError as exc:
            # Expected error for Week 8 (WorkflowEngine not implemented yet)
            error_msg = f"SubWorkflow execution not available: {str(exc)}"
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

        except RecursionError as exc:
            error_msg = f"Subworkflow recursion depth exceeded: {str(exc)}"
            logger.error(error_msg, extra={'node_id': node.id})

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
            error_msg = f"Failed to execute subworkflow node: {str(exc)}"
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

    def _map_context(
        self,
        source_context: Dict[str, Any],
        mapping: Dict[str, str],
        direction: str
    ) -> Dict[str, Any]:
        """
        Map context using input/output mapping with dot notation support.

        Args:
            source_context: Source context to map from
            mapping: Mapping dict (source_path -> target_path)
            direction: 'input' or 'output' (for logging)

        Returns:
            Mapped context dict

        Example:
            mapping = {"database.id": "target_db_id"}
            source_context = {"database": {"id": "db123"}}
            -> {"target_db_id": "db123"}
        """
        mapped_context = {}

        for source_path, target_path in mapping.items():
            try:
                # Resolve source value using dot notation
                value = self._resolve_path(source_context, source_path)

                # Set target value using dot notation
                self._set_path(mapped_context, target_path, value)

                logger.debug(
                    f"Mapped {direction} context: {source_path} -> {target_path}",
                    extra={'source_path': source_path, 'target_path': target_path}
                )

            except KeyError as exc:
                logger.warning(
                    f"Failed to map {direction} context: {source_path} not found",
                    extra={'source_path': source_path, 'error': str(exc)}
                )
                # Continue with other mappings instead of failing

        return mapped_context

    def _resolve_path(self, context: Dict[str, Any], path: str) -> Any:
        """
        Resolve dot notation path in context.

        Args:
            context: Context dict
            path: Dot notation path (e.g., 'database.id')

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

    def _set_path(self, context: Dict[str, Any], path: str, value: Any) -> None:
        """
        Set value at dot notation path in context.

        Args:
            context: Context dict to modify
            path: Dot notation path (e.g., 'result.status')
            value: Value to set

        Example:
            context = {}
            _set_path(context, 'result.status', 'success')
            -> context = {"result": {"status": "success"}}
        """
        keys = path.split('.')

        # Navigate to parent dict, creating nested dicts as needed
        current = context
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # Set final value
        current[keys[-1]] = value
