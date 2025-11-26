"""
NodeHandlers for Workflow Engine - Week 7 Implementation.

Implements handler architecture for different workflow node types:
- OperationHandler: Executes operation templates via TemplateRenderer
- ConditionHandler: Evaluates Jinja2 boolean expressions in sandbox

Architecture:
- BaseNodeHandler: Abstract base class with result creation
- NodeExecutionResult: Structured result with mode tracking
- NodeHandlerFactory: Registry-based handler resolution

Integration:
- Track 1 Template Engine: TemplateRenderer, OperationTemplate
- Track 1.5 Workflow: WorkflowNode, WorkflowExecution, WorkflowStepResult

SECURITY:
- ImmutableSandboxedEnvironment for condition evaluation
- StrictUndefined for template safety
- No code execution in expressions
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import logging
import time
import threading

from django.utils import timezone

from .models import WorkflowExecution, WorkflowNode, WorkflowStepResult
from apps.templates.models import OperationTemplate
from apps.templates.engine.renderer import TemplateRenderer
from apps.templates.engine.exceptions import TemplateRenderError, TemplateValidationError

from jinja2.sandbox import ImmutableSandboxedEnvironment
from jinja2 import StrictUndefined

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================


class NodeExecutionMode(Enum):
    """
    Execution mode for workflow nodes.

    - SYNC: Wait for operation completion before proceeding
    - ASYNC: Return immediately with task_id (Celery integration - Week 9)
    """
    SYNC = "sync"
    ASYNC = "async"


@dataclass
class NodeExecutionResult:
    """
    Result of a node execution.

    Attributes:
        success: Whether execution succeeded
        output: Node output data (rendered template, boolean result, etc.)
        error: Error message if failed (None if success)
        mode: Execution mode used (sync/async)
        duration_seconds: Execution duration in seconds (None if async)
    """
    success: bool
    output: Optional[Any]
    error: Optional[str]
    mode: NodeExecutionMode
    duration_seconds: Optional[float]


# ============================================================================
# Base Handler
# ============================================================================


class BaseNodeHandler(ABC):
    """
    Abstract base handler for workflow nodes.

    Defines the handler contract and provides common functionality
    for creating and updating WorkflowStepResult records.

    Subclasses must implement:
        - execute(): Node execution logic
    """

    @abstractmethod
    def execute(
        self,
        node: WorkflowNode,
        context: Dict[str, Any],
        execution: WorkflowExecution,
        mode: NodeExecutionMode = NodeExecutionMode.SYNC
    ) -> NodeExecutionResult:
        """
        Execute workflow node.

        Args:
            node: WorkflowNode Pydantic schema from DAG
            context: Execution context with variables
            execution: WorkflowExecution instance for tracking
            mode: Execution mode (sync/async)

        Returns:
            NodeExecutionResult with success/output/error
        """
        pass

    def _create_step_result(
        self,
        execution: WorkflowExecution,
        node: WorkflowNode,
        input_data: Dict[str, Any]
    ) -> WorkflowStepResult:
        """
        Create WorkflowStepResult for audit trail.

        Args:
            execution: WorkflowExecution instance
            node: WorkflowNode Pydantic schema
            input_data: Input data for this step

        Returns:
            WorkflowStepResult: Created step result instance (status=running)
        """
        step_result = WorkflowStepResult.objects.create(
            workflow_execution=execution,
            node_id=node.id,
            node_name=node.name,
            node_type=node.type,
            status=WorkflowStepResult.STATUS_RUNNING,
            input_data=input_data,
            started_at=timezone.now()
        )

        # Set OpenTelemetry context if available (Week 12)
        step_result.set_opentelemetry_context()
        step_result.save(update_fields=['trace_id', 'span_id'])

        logger.info(
            f"Created step result for node {node.id}",
            extra={
                'execution_id': str(execution.id),
                'node_id': node.id,
                'node_type': node.type,
                'step_result_id': str(step_result.id)
            }
        )

        return step_result

    def _update_step_result(
        self,
        step_result: WorkflowStepResult,
        result: NodeExecutionResult
    ) -> None:
        """
        Update WorkflowStepResult with execution result.

        Args:
            step_result: WorkflowStepResult instance to update
            result: NodeExecutionResult with execution outcome
        """
        step_result.status = (
            WorkflowStepResult.STATUS_COMPLETED if result.success
            else WorkflowStepResult.STATUS_FAILED
        )
        step_result.output_data = result.output
        step_result.error_message = result.error or ""
        step_result.completed_at = timezone.now()

        step_result.save(update_fields=[
            'status', 'output_data', 'error_message', 'completed_at'
        ])

        logger.info(
            f"Updated step result for node {step_result.node_id}",
            extra={
                'step_result_id': str(step_result.id),
                'status': step_result.status,
                'duration_seconds': step_result.duration_seconds,
                'success': result.success
            }
        )


# ============================================================================
# Operation Handler
# ============================================================================


class OperationHandler(BaseNodeHandler):
    """
    Handler for Operation nodes.

    Flow:
        1. Get OperationTemplate by node.template_id
        2. Render template via TemplateRenderer (Track 1 integration)
        3. [Week 9] Create BatchOperation from rendered data
        4. Execute operation (sync: wait, async: return task_id)
        5. Return NodeExecutionResult

    Current Implementation (Week 7):
        - Returns rendered data as output (no BatchOperation yet)
        - SYNC mode only (ASYNC requires Celery - Week 9)

    Integration:
        - apps.templates.models.OperationTemplate: Template storage
        - apps.templates.engine.renderer.TemplateRenderer: Rendering
    """

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
        Execute operation node by rendering template.

        Args:
            node: WorkflowNode with template_id
            context: Execution context with variables
            execution: WorkflowExecution for tracking
            mode: Execution mode (currently only SYNC supported)

        Returns:
            NodeExecutionResult with rendered data or error
        """
        start_time = time.time()

        # Create step result for audit
        step_result = self._create_step_result(
            execution=execution,
            node=node,
            input_data={'context_keys': list(context.keys())}
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

            # 3. TODO Week 9: Create BatchOperation from rendered_data
            # For now, return rendered data as output

            # 4. Execute operation (Week 9: Celery integration)
            # Current: SYNC mode only - return rendered data immediately
            if mode == NodeExecutionMode.ASYNC:
                logger.warning(
                    f"ASYNC mode requested but not implemented (Week 9) - using SYNC",
                    extra={'node_id': node.id}
                )

            duration = time.time() - start_time

            # 5. Return success result
            result = NodeExecutionResult(
                success=True,
                output=rendered_data,
                error=None,
                mode=NodeExecutionMode.SYNC,  # Force SYNC for now
                duration_seconds=duration
            )

            # Update step result
            self._update_step_result(step_result, result)

            logger.info(
                f"Operation node {node.id} completed successfully",
                extra={
                    'node_id': node.id,
                    'duration_seconds': duration,
                    'output_size': len(str(rendered_data))
                }
            )

            return result

        except OperationTemplate.DoesNotExist:
            error_msg = f"OperationTemplate not found: {node.template_id}"
            logger.error(error_msg, extra={'node_id': node.id, 'template_id': node.template_id})

            result = NodeExecutionResult(
                success=False,
                output=None,
                error=error_msg,
                mode=NodeExecutionMode.SYNC,
                duration_seconds=time.time() - start_time
            )
            self._update_step_result(step_result, result)
            return result

        except (TemplateRenderError, TemplateValidationError) as exc:
            error_msg = f"Template rendering failed: {str(exc)}"
            logger.error(
                error_msg,
                extra={'node_id': node.id, 'template_id': node.template_id},
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

        except Exception as exc:
            error_msg = f"Unexpected error executing operation node: {str(exc)}"
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


# ============================================================================
# Condition Handler
# ============================================================================


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
        - Currently: node.config.get('expression', 'False')
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
            rendered = template.render(context)

            # 3. Convert to boolean
            bool_result = self._to_bool(rendered)

            duration = time.time() - start_time

            # 4. Return success result
            result = NodeExecutionResult(
                success=True,
                output=bool_result,
                error=None,
                mode=NodeExecutionMode.SYNC,  # Conditions are always SYNC
                duration_seconds=duration
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


# ============================================================================
# Handler Factory
# ============================================================================


class NodeHandlerFactory:
    """
    Factory for creating node handlers.

    Uses registry pattern for handler resolution:
    - register(): Register handler class for node type
    - get_handler(): Get singleton handler instance

    Handlers are singletons (created once, reused).

    Auto-registration:
        - Handlers are registered at module load time
        - See bottom of this file for registrations
    """

    # Class-level registry
    _handlers: Dict[str, type] = {}
    _instances: Dict[str, BaseNodeHandler] = {}
    _lock = threading.Lock()

    @classmethod
    def register(cls, node_type: str, handler_class: type) -> None:
        """
        Register handler class for node type.

        Args:
            node_type: Node type identifier (operation, condition, etc.)
            handler_class: Handler class (must inherit BaseNodeHandler)

        Raises:
            TypeError: If handler_class is not a BaseNodeHandler subclass
        """
        if not issubclass(handler_class, BaseNodeHandler):
            raise TypeError(
                f"Handler class must inherit from BaseNodeHandler, got {handler_class}"
            )

        cls._handlers[node_type] = handler_class

        logger.debug(
            f"Registered handler for node type '{node_type}'",
            extra={'node_type': node_type, 'handler_class': handler_class.__name__}
        )

    @classmethod
    def get_handler(cls, node_type: str) -> BaseNodeHandler:
        """
        Get handler instance for node type.

        Creates singleton instance on first access with thread-safe double-checked locking.

        Args:
            node_type: Node type identifier

        Returns:
            BaseNodeHandler: Handler instance

        Raises:
            ValueError: If no handler registered for node type
        """
        # Check if handler is registered
        if node_type not in cls._handlers:
            raise ValueError(
                f"No handler registered for node type '{node_type}'. "
                f"Available types: {list(cls._handlers.keys())}"
            )

        # Double-checked locking pattern for thread-safe singleton creation
        if node_type not in cls._instances:  # Fast path (no lock)
            with cls._lock:  # Thread-safe
                if node_type not in cls._instances:  # Re-check inside lock
                    handler_class = cls._handlers[node_type]
                    cls._instances[node_type] = handler_class()

                    logger.debug(
                        f"Created handler instance for node type '{node_type}'",
                        extra={'node_type': node_type, 'handler_class': handler_class.__name__}
                    )

        return cls._instances[node_type]


# ============================================================================
# Auto-registration
# ============================================================================


# Register handlers at module load time
NodeHandlerFactory.register('operation', OperationHandler)
NodeHandlerFactory.register('condition', ConditionHandler)

logger.info(
    "NodeHandlers module initialized",
    extra={
        'registered_handlers': list(NodeHandlerFactory._handlers.keys())
    }
)
