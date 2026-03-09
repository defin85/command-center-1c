"""
ConditionHandler for Workflow Engine.

Evaluates boolean expressions in sandboxed Jinja2 environment.
"""

import logging
import time
from typing import Any, Dict, Mapping

from jinja2 import StrictUndefined
from jinja2.sandbox import ImmutableSandboxedEnvironment

from apps.templates.workflow.decision_tables import (
    evaluate_decision_table,
    resolve_pinned_decision_table,
)
from apps.templates.workflow.models import WorkflowExecution, WorkflowNode

from .base import BaseNodeHandler, NodeExecutionMode, NodeExecutionResult

logger = logging.getLogger(__name__)


class ConditionHandler(BaseNodeHandler):
    """
    Handler for Condition nodes.

    Flow:
        1. Get expression from node.config (or node schema directly)
        2. Setup ImmutableSandboxedEnvironment for safety
        3. Render expression as Jinja2 template
        4. Convert result to boolean via _to_bool()
        5. Return NodeExecutionResult with boolean output

    Security:
        - ImmutableSandboxedEnvironment: No code execution
        - StrictUndefined: Fail on undefined variables
        - No access to dangerous functions

    Expression location:
        - Currently: node.config.expression
        - Alternative: node.expression (if added to WorkflowNode schema)
    """

    def __init__(self):
        """Initialize ConditionHandler with sandboxed Jinja2 environment."""
        # Setup sandbox environment (similar to TemplateRenderer)
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
        Execute condition node by evaluating expression.

        Args:
            node: WorkflowNode with condition expression
            context: Execution context with variables
            execution: WorkflowExecution for tracking
            mode: Execution mode (always SYNC for conditions)

        Returns:
            NodeExecutionResult with boolean output
        """
        start_time = time.time()

        # Create step result for audit
        step_result = self._create_step_result(
            execution=execution,
            node=node,
            input_data={'context_keys': list(context.keys())}
        )

        try:
            # 1. Get expression from node config
            # Check if expression is in config dict or as separate field
            expression = self._get_expression(node)
            render_context = dict(context)
            context_updates: dict[str, Any] = {}
            if getattr(node, "decision_ref", None) is not None:
                render_context, context_updates = self._apply_decision_ref(
                    node=node,
                    context=context,
                )

            logger.info(
                f"Executing condition node {node.id}",
                extra={
                    'node_id': node.id,
                    'expression': expression,
                    'context_keys': list(context.keys())
                }
            )

            # 2. Render expression in sandbox
            template = self.env.from_string(expression)
            rendered = template.render(render_context)

            # 3. Convert to boolean
            bool_result = self._to_bool(rendered)

            duration = time.time() - start_time

            # 4. Return success result
            result = NodeExecutionResult(
                success=True,
                output=bool_result,
                error=None,
                mode=NodeExecutionMode.SYNC,  # Conditions are always SYNC
                duration_seconds=duration,
                context_updates=context_updates or None,
            )

            # Update step result
            self._update_step_result(step_result, result)

            logger.info(
                f"Condition node {node.id} evaluated to {bool_result}",
                extra={
                    'node_id': node.id,
                    'expression': expression,
                    'result': bool_result,
                    'duration_seconds': duration
                }
            )

            return result

        except Exception as exc:
            error_msg = f"Failed to evaluate condition: {str(exc)}"
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

    def _apply_decision_ref(
        self,
        *,
        node: WorkflowNode,
        context: Dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        decision_ref = getattr(node, "decision_ref", None)
        if decision_ref is None:
            return dict(context), {}

        decision_table = resolve_pinned_decision_table(
            decision_table_id=decision_ref.decision_table_id,
            decision_revision=decision_ref.decision_revision,
        )
        decision_inputs = self._build_decision_inputs(node=node, context=context)
        outputs = evaluate_decision_table(
            decision_table=decision_table,
            inputs=decision_inputs,
        )
        decision_value = self._resolve_decision_value(
            decision_key=decision_ref.decision_key,
            outputs=outputs,
        )
        render_context = dict(context)
        decisions_context = (
            dict(context.get("decisions"))
            if isinstance(context.get("decisions"), Mapping)
            else {}
        )
        decisions_context[decision_ref.decision_key] = decision_value
        render_context["decisions"] = decisions_context
        render_context["result"] = outputs

        updates = {
            f"decisions.{decision_ref.decision_key}": decision_value,
        }
        updates.update(self._build_output_context_updates(node=node, outputs=outputs))
        return render_context, updates

    def _build_decision_inputs(
        self,
        *,
        node: WorkflowNode,
        context: Dict[str, Any],
    ) -> dict[str, Any]:
        io = getattr(node, "io", None)
        io_mode = str(getattr(io, "mode", "implicit_legacy") or "implicit_legacy")
        input_mapping = dict(getattr(io, "input_mapping", {}) or {})
        if io_mode != "explicit_strict" or not input_mapping:
            return dict(context)

        decision_inputs: dict[str, Any] = {}
        missing_source_paths: list[str] = []
        for target_path, source_path in input_mapping.items():
            normalized_target = self._normalize_decision_input_target(target_path)
            try:
                decision_inputs[normalized_target] = self._resolve_path(context, source_path)
            except KeyError:
                missing_source_paths.append(source_path)
        if missing_source_paths:
            raise ValueError(
                "DECISION_INPUT_MAPPING_ERROR: missing source_path(s) for explicit_strict mode: "
                + ", ".join(sorted(set(missing_source_paths)))
            )
        return decision_inputs

    @staticmethod
    def _normalize_decision_input_target(target_path: str) -> str:
        normalized = str(target_path or "").strip()
        if normalized.startswith("input."):
            normalized = normalized[len("input.") :]
        if not normalized:
            raise ValueError("DECISION_INPUT_MAPPING_ERROR: target_path must not be empty")
        return normalized

    def _build_output_context_updates(
        self,
        *,
        node: WorkflowNode,
        outputs: Mapping[str, Any],
    ) -> dict[str, Any]:
        io = getattr(node, "io", None)
        io_mode = str(getattr(io, "mode", "implicit_legacy") or "implicit_legacy")
        output_mapping = dict(getattr(io, "output_mapping", {}) or {})
        if io_mode != "explicit_strict" or not output_mapping:
            return {}

        source_payload = {"result": dict(outputs)}
        updates: dict[str, Any] = {}
        for target_path, source_path in output_mapping.items():
            try:
                updates[target_path] = self._resolve_path(source_payload, source_path)
            except KeyError:
                logger.warning(
                    "Condition output mapping source path is missing; skipping mapping entry",
                    extra={
                        "node_id": node.id,
                        "target_path": target_path,
                        "source_path": source_path,
                    },
                )
        return updates

    @staticmethod
    def _resolve_decision_value(
        *,
        decision_key: str,
        outputs: Mapping[str, Any],
    ) -> Any:
        if decision_key in outputs:
            return outputs[decision_key]
        if len(outputs) == 1:
            return next(iter(outputs.values()))
        return dict(outputs)

    @staticmethod
    def _resolve_path(source: Mapping[str, Any], path: str) -> Any:
        current: Any = source
        for segment in str(path or "").split("."):
            if not isinstance(current, Mapping) or segment not in current:
                raise KeyError(path)
            current = current[segment]
        return current

    def _get_expression(self, node: WorkflowNode) -> str:
        """
        Extract condition expression from node.

        Checks multiple locations:
        1. node.config dict (current approach)
        2. node.expression (if added to WorkflowNode schema)

        Args:
            node: WorkflowNode Pydantic schema

        Returns:
            str: Condition expression (default: 'False')
        """
        # Try node.config first (current implementation)
        if hasattr(node.config, 'model_dump'):
            # NodeConfig is Pydantic model
            config_dict = node.config.model_dump()
        else:
            # NodeConfig is dict (unlikely with Pydantic)
            config_dict = node.config if isinstance(node.config, dict) else {}

        expression = config_dict.get('expression')

        # Fallback: Check if expression is direct attribute
        if not expression and hasattr(node, 'expression'):
            expression = getattr(node, 'expression')

        # Default: Always False if no expression provided
        if not expression:
            logger.warning(
                f"No expression found for condition node {node.id}, defaulting to 'False'",
                extra={'node_id': node.id}
            )
            expression = 'False'

        return expression

    def _to_bool(self, value: Any) -> bool:
        """
        Convert rendered value to boolean.

        Handles:
        - bool: Return as-is
        - str: Case-insensitive "true", "yes", "1" -> True
        - int: 0 -> False, non-zero -> True
        - None: False
        - collections: Empty -> False, non-empty -> True

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
            logger.warning("Condition evaluated to None - returning False")
            return False

        # Collections (list, dict, etc.)
        # Empty -> False, non-empty -> True
        return bool(value)
