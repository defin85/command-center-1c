"""
Immutable Context Manager for Workflow Engine.

Provides thread-safe, immutable context management for workflow execution with:
- Deep copy isolation for thread safety
- Dot notation access for nested values (node_1.output.field)
- Jinja2 template interpolation with sandboxing
- Context merging with conflict detection
- Immutable snapshots for parallel execution
"""

import copy
import logging
import threading
from typing import Any, Dict, Optional

from jinja2 import TemplateSyntaxError, Undefined, UndefinedError
from jinja2.sandbox import ImmutableSandboxedEnvironment

logger = logging.getLogger(__name__)


class ContextManager:
    """
    Manages immutable execution context for workflow.

    Features:
    - Thread-safe immutable snapshots
    - Node output resolution (node_1.output.field)
    - Jinja2 variable interpolation (sandboxed)
    - Context merging with conflict detection
    - Deep copy isolation

    Usage:
        ctx = ContextManager({'database_id': '123'})
        ctx = ctx.set('user_id', '456')  # Returns NEW context
        ctx = ctx.add_node_result('node_1', {'status': 'ok'})
        value = ctx.get('nodes.node_1.status')  # -> 'ok'
        rendered = ctx.resolve_template('ID: {{ database_id }}')  # -> 'ID: 123'
    """

    # Jinja2 sandboxed environment (class-level singleton with thread safety)
    _jinja_env: Optional[ImmutableSandboxedEnvironment] = None
    _jinja_lock: threading.Lock = threading.Lock()

    def __init__(self, initial_context: Optional[Dict[str, Any]] = None):
        """
        Initialize with input context (deep copy for isolation).

        Args:
            initial_context: Initial context data. Will be deep-copied.
        """
        # Deep copy to ensure immutability
        self._context: Dict[str, Any] = copy.deepcopy(initial_context or {})

        # Initialize nodes storage if not present
        if 'nodes' not in self._context:
            self._context['nodes'] = {}

        logger.debug(
            "ContextManager initialized",
            extra={'context_keys': list(self._context.keys())}
        )

    @classmethod
    def _get_jinja_env(cls) -> ImmutableSandboxedEnvironment:
        """
        Get or create Jinja2 sandboxed environment.

        Uses double-checked locking for thread safety.

        Returns:
            ImmutableSandboxedEnvironment: Thread-safe Jinja2 environment
        """
        if cls._jinja_env is None:
            with cls._jinja_lock:
                # Double-checked locking for thread safety
                if cls._jinja_env is None:
                    cls._jinja_env = ImmutableSandboxedEnvironment(
                        # Security settings
                        autoescape=False,  # No HTML escaping for data processing
                        # Undefined behavior - use default Undefined (returns empty string)
                        undefined=Undefined,
                    )
        return cls._jinja_env

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value by key with dot notation support.

        Supports nested access via dot notation:
        - 'database_id' -> direct key
        - 'node_1.output.status' -> nested access
        - 'nodes.node_1.result.data' -> nested access

        Args:
            key: Key to retrieve (supports dot notation)
            default: Default value if key not found

        Returns:
            Value at key or default
        """
        if not key:
            return default

        # Handle dot notation for nested access
        parts = key.split('.')
        value = self._context

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
                if value is None:
                    return default
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> "ContextManager":
        """
        Return NEW ContextManager with updated value (immutable).

        Supports dot notation for nested setting:
        - 'status' -> direct key
        - 'result.data' -> nested set (creates intermediate dicts)

        Args:
            key: Key to set (supports dot notation)
            value: Value to set (will be deep-copied)

        Returns:
            New ContextManager with updated value

        Example:
            new_ctx = ctx.set('result.status', 'success')
        """
        # Create new context with deep copy
        new_context = copy.deepcopy(self._context)

        # Handle dot notation
        parts = key.split('.')

        if len(parts) == 1:
            # Simple key
            new_context[key] = copy.deepcopy(value)
        else:
            # Nested key - navigate and create intermediate dicts
            current = new_context
            for part in parts[:-1]:
                if part not in current or not isinstance(current[part], dict):
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = copy.deepcopy(value)

        return ContextManager(new_context)

    def merge(self, other: Dict[str, Any], allow_overwrite: bool = True) -> "ContextManager":
        """
        Merge dict into context, return NEW ContextManager.

        Args:
            other: Dictionary to merge into context
            allow_overwrite: If False, raises error on key conflicts

        Returns:
            New ContextManager with merged data

        Raises:
            ValueError: If allow_overwrite=False and key conflict detected
        """
        if not other:
            return self.snapshot()

        new_context = copy.deepcopy(self._context)

        for key, value in other.items():
            if not allow_overwrite and key in new_context:
                raise ValueError(
                    f"Context key conflict: '{key}' already exists. "
                    f"Use allow_overwrite=True to override."
                )
            new_context[key] = copy.deepcopy(value)

        logger.debug(
            "Context merged",
            extra={
                'merged_keys': list(other.keys()),
                'allow_overwrite': allow_overwrite
            }
        )

        return ContextManager(new_context)

    def add_node_result(self, node_id: str, result: Dict[str, Any]) -> "ContextManager":
        """
        Add node execution result to context.

        Results are stored in 'nodes.<node_id>' namespace for isolation
        and easy access from subsequent nodes.

        Args:
            node_id: Node identifier
            result: Node execution result data

        Returns:
            New ContextManager with node result added

        Example:
            ctx = ctx.add_node_result('node_1', {'status': 'ok', 'data': {...}})
            # Access via: ctx.get('nodes.node_1.status') -> 'ok'
        """
        new_context = copy.deepcopy(self._context)

        # Ensure nodes dict exists
        if 'nodes' not in new_context:
            new_context['nodes'] = {}

        # Store result under node_id
        new_context['nodes'][node_id] = copy.deepcopy(result)

        # Also store with 'output' key for compatibility with Jinja templates
        # that use {{ node_1.output.field }} pattern
        if node_id not in new_context:
            new_context[node_id] = {}
        new_context[node_id]['output'] = copy.deepcopy(result)

        logger.debug(
            f"Added node result for '{node_id}'",
            extra={
                'node_id': node_id,
                'result_keys': list(result.keys()) if isinstance(result, dict) else None
            }
        )

        return ContextManager(new_context)

    def resolve_template(self, template_str: str) -> str:
        """
        Resolve Jinja2 template string using context variables.

        Uses ImmutableSandboxedEnvironment for security:
        - No access to dangerous attributes/methods
        - No object modification
        - Safe for untrusted templates

        Args:
            template_str: Jinja2 template string (e.g., '{{ database_id }}')

        Returns:
            Resolved string with variables substituted

        Raises:
            ValueError: If template syntax is invalid
        """
        if not template_str:
            return ""

        # Check if string contains Jinja2 markers
        if '{{' not in template_str and '{%' not in template_str:
            return template_str

        try:
            env = self._get_jinja_env()
            template = env.from_string(template_str)
            result = template.render(self._context)

            logger.debug(
                "Template resolved",
                extra={
                    'template_length': len(template_str),
                    'result_length': len(result)
                }
            )

            return result

        except TemplateSyntaxError as exc:
            error_msg = f"Invalid Jinja2 template syntax: {exc}"
            logger.error(error_msg, extra={'template': template_str[:100]})
            raise ValueError(error_msg) from exc

        except UndefinedError as exc:
            # Log warning but return empty for undefined
            logger.warning(
                f"Undefined variable in template: {exc}",
                extra={'template': template_str[:100]}
            )
            return ""

        except Exception as exc:
            error_msg = f"Template rendering failed: {exc}"
            logger.error(error_msg, extra={'template': template_str[:100]}, exc_info=True)
            raise ValueError(error_msg) from exc

    def evaluate_condition(self, condition: str) -> bool:
        """
        Evaluate Jinja2 condition expression in sandboxed environment.

        Evaluates boolean expressions like:
        - '{{ node_1.output.success }}'
        - '{{ count > 5 }}'
        - '{{ status == "completed" }}'

        Args:
            condition: Jinja2 boolean expression

        Returns:
            Boolean result of condition evaluation

        Raises:
            ValueError: If condition is invalid or cannot be evaluated
        """
        if not condition:
            return True  # Empty condition = always true

        try:
            # Resolve template
            resolved = self.resolve_template(condition)

            # Convert to boolean
            # Handle string representations of booleans
            if isinstance(resolved, str):
                resolved_lower = resolved.strip().lower()
                if resolved_lower in ('true', '1', 'yes', 'on'):
                    return True
                elif resolved_lower in ('false', '0', 'no', 'off', ''):
                    return False
                # Try to evaluate as Python expression (safely)
                try:
                    # Only allow simple boolean conversion
                    return bool(resolved_lower)
                except (ValueError, TypeError):
                    return bool(resolved)
            else:
                return bool(resolved)

        except Exception as exc:
            error_msg = f"Condition evaluation failed: {exc}"
            logger.error(
                error_msg,
                extra={'condition': condition[:100]},
                exc_info=True
            )
            raise ValueError(error_msg) from exc

    def to_dict(self) -> Dict[str, Any]:
        """
        Export context as dict (deep copy for safety).

        Returns:
            Deep copy of internal context dictionary
        """
        return copy.deepcopy(self._context)

    def snapshot(self) -> "ContextManager":
        """
        Create immutable snapshot for parallel execution.

        Creates a completely independent copy of the context
        that can be safely passed to parallel tasks.

        Returns:
            New ContextManager with copied context
        """
        return ContextManager(copy.deepcopy(self._context))

    def __contains__(self, key: str) -> bool:
        """Check if key exists in context (supports dot notation)."""
        return self.get(key) is not None

    def __repr__(self) -> str:
        """String representation for debugging."""
        keys = list(self._context.keys())
        return f"ContextManager(keys={keys})"

    def keys(self) -> list:
        """Return list of top-level context keys."""
        return list(self._context.keys())

    def get_node_result(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Get result of a specific node.

        Args:
            node_id: Node identifier

        Returns:
            Node result dict or None if not found
        """
        return self.get(f'nodes.{node_id}')

    def has_node_result(self, node_id: str) -> bool:
        """
        Check if node result exists.

        Args:
            node_id: Node identifier

        Returns:
            True if node result exists
        """
        return self.get_node_result(node_id) is not None
