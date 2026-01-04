"""
DAG Executor for Workflow Engine.

Executes workflow DAG in topological order with:
- Topological ordering via DAGValidator
- Conditional edge evaluation (Jinja2 expressions)
- Node skipping based on conditions
- Error handling and rollback tracking
- Support for all node types (operation, condition, parallel, loop, subworkflow)
"""

import inspect
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from asgiref.sync import sync_to_async

from apps.templates.tracing import (
    add_span_event,
    get_current_span_id,
    set_span_attribute,
    set_span_error,
    start_node_span,
)
from apps.templates.consumers import (
    broadcast_node_update,
    broadcast_workflow_update,
)
from apps.templates.workflow.context import ContextManager
from apps.templates.workflow.handlers import NodeExecutionMode, NodeHandlerFactory
from apps.templates.workflow.models import (
    DAGStructure,
    WorkflowEdge,
    WorkflowExecution,
    WorkflowNode,
)
from apps.templates.workflow.validator import DAGValidator

logger = logging.getLogger(__name__)


class DAGExecutionError(Exception):
    """Exception raised during DAG execution."""

    def __init__(
        self,
        message: str,
        node_id: Optional[str] = None,
        recoverable: bool = False
    ):
        """
        Initialize DAG execution error.

        Args:
            message: Error description
            node_id: Node ID where error occurred (optional)
            recoverable: Whether error is recoverable (for retry logic)
        """
        self.message = message
        self.node_id = node_id
        self.recoverable = recoverable
        super().__init__(self.message)


class DAGExecutor:
    """
    Executes workflow DAG in topological order.

    Features:
    - Topological order execution (uses validator.topological_order)
    - Conditional edge evaluation (Jinja2 expressions)
    - Node skipping based on conditions
    - Error handling and rollback tracking
    - Integration with NodeHandlers for node execution

    Usage:
        executor = DAGExecutor(dag, execution)
        success, result = await executor.execute(context)
    """

    def __init__(self, dag: DAGStructure, execution: WorkflowExecution):
        """
        Initialize DAGExecutor with DAG and execution instance.

        Args:
            dag: DAG structure to execute
            execution: WorkflowExecution instance for state tracking

        Raises:
            ValueError: If DAG is invalid
        """
        self.dag = dag
        self.execution = execution

        # Build node map for quick lookup
        self.node_map: Dict[str, WorkflowNode] = {
            node.id: node for node in dag.nodes
        }

        # Build edge maps
        self.outgoing_edges: Dict[str, List[WorkflowEdge]] = {}
        self.incoming_edges: Dict[str, List[WorkflowEdge]] = {}

        for edge in dag.edges:
            # Outgoing edges (from_node -> [edges])
            if edge.from_node not in self.outgoing_edges:
                self.outgoing_edges[edge.from_node] = []
            self.outgoing_edges[edge.from_node].append(edge)

            # Incoming edges (to_node -> [edges])
            if edge.to_node not in self.incoming_edges:
                self.incoming_edges[edge.to_node] = []
            self.incoming_edges[edge.to_node].append(edge)

        # Get topological order
        self._topological_order: Optional[List[str]] = None
        self._validate_and_get_order()

        logger.info(
            f"DAGExecutor initialized for execution {execution.id}",
            extra={
                'execution_id': str(execution.id),
                'node_count': len(dag.nodes),
                'edge_count': len(dag.edges)
            }
        )

    def _validate_and_get_order(self) -> None:
        """
        Validate DAG and extract topological order.

        Raises:
            ValueError: If DAG validation fails
        """
        validator = DAGValidator(self.dag)
        result = validator.validate()

        if not result.is_valid:
            error_messages = [issue.message for issue in result.errors]
            raise ValueError(f"DAG validation failed: {'; '.join(error_messages)}")

        self._topological_order = result.topological_order

        logger.debug(
            "DAG validated successfully",
            extra={
                'topological_order': self._topological_order,
                'warnings': len(result.warnings)
            }
        )

    async def execute(self, context: ContextManager) -> Tuple[bool, Dict[str, Any]]:
        """
        Execute DAG in topological order.

        Iterates through nodes in topological order, executing each node
        that should be executed based on incoming edge conditions.

        Args:
            context: Initial execution context

        Returns:
            Tuple[success, final_context_or_error]:
                - (True, final_context_dict) if successful
                - (False, {'error': message, 'node_id': id}) if failed
        """
        if not self._topological_order:
            return False, {'error': 'No topological order available', 'node_id': None}

        current_context = context.snapshot()
        executed_nodes: Set[str] = set()
        skipped_nodes: Set[str] = set()

        logger.info(
            f"Starting DAG execution for {self.execution.id}",
            extra={
                'execution_id': str(self.execution.id),
                'node_order': self._topological_order
            }
        )

        try:
            for node_id in self._topological_order:
                node = self.node_map.get(node_id)
                if not node:
                    raise DAGExecutionError(
                        f"Node '{node_id}' not found in node map",
                        node_id=node_id
                    )

                # Check if node should be executed
                should_execute = self._should_execute_node(
                    node_id, current_context, executed_nodes, skipped_nodes
                )

                if not should_execute:
                    # Skip this node
                    skipped_nodes.add(node_id)
                    await sync_to_async(
                        self.execution.update_node_status,
                        thread_sensitive=True
                    )(node_id, 'skipped')

                    # Broadcast node skip via WebSocket
                    await self._broadcast_node_update(node_id, 'skipped')

                    logger.info(
                        f"Skipping node {node_id} (conditions not met)",
                        extra={
                            'execution_id': str(self.execution.id),
                            'node_id': node_id
                        }
                    )
                    continue

                # Execute node
                success, current_context = await self._execute_node(
                    node_id, node, current_context
                )

                if not success:
                    # Node execution failed
                    error_info = current_context.get('_last_error', {})
                    return False, {
                        'error': error_info.get('message', 'Node execution failed'),
                        'node_id': node_id,
                        'context': current_context.to_dict()
                    }

                executed_nodes.add(node_id)

            # All nodes executed successfully
            logger.info(
                f"DAG execution completed successfully for {self.execution.id}",
                extra={
                    'execution_id': str(self.execution.id),
                    'executed_count': len(executed_nodes),
                    'skipped_count': len(skipped_nodes)
                }
            )

            return True, current_context.to_dict()

        except DAGExecutionError as exc:
            logger.error(
                f"DAG execution failed: {exc.message}",
                extra={
                    'execution_id': str(self.execution.id),
                    'node_id': exc.node_id
                },
                exc_info=True
            )
            return False, {
                'error': exc.message,
                'node_id': exc.node_id,
                'recoverable': exc.recoverable
            }

        except Exception as exc:
            logger.error(
                f"Unexpected error during DAG execution: {exc}",
                extra={'execution_id': str(self.execution.id)},
                exc_info=True
            )
            return False, {
                'error': str(exc),
                'node_id': None,
                'recoverable': False
            }

    def _should_execute_node(
        self,
        node_id: str,
        context: ContextManager,
        executed_nodes: Set[str],
        skipped_nodes: Set[str]
    ) -> bool:
        """
        Check if node should execute based on incoming edge conditions.

        A node should execute if:
        1. It has no incoming edges (start node), OR
        2. At least one incoming edge has its condition satisfied AND
           the source node was executed (not skipped)

        Args:
            node_id: Node ID to check
            context: Current execution context
            executed_nodes: Set of already executed node IDs
            skipped_nodes: Set of skipped node IDs

        Returns:
            True if node should execute
        """
        # Get incoming edges for this node
        incoming = self.incoming_edges.get(node_id, [])

        # Start nodes (no incoming edges) always execute
        if not incoming:
            return True

        # Check each incoming edge
        for edge in incoming:
            source_node = edge.from_node

            # Source must have been executed (not skipped)
            if source_node in skipped_nodes:
                continue

            if source_node not in executed_nodes:
                # Source not yet processed - this shouldn't happen in topological order
                logger.warning(
                    f"Source node {source_node} not yet executed for edge to {node_id}",
                    extra={'execution_id': str(self.execution.id)}
                )
                continue

            # Check edge condition
            if self._evaluate_edge_condition(edge, context):
                return True

        # No valid incoming path found
        return False

    def _evaluate_edge_condition(
        self,
        edge: WorkflowEdge,
        context: ContextManager
    ) -> bool:
        """
        Evaluate edge condition expression.

        Args:
            edge: Edge with optional condition
            context: Execution context for variable resolution

        Returns:
            True if condition is satisfied (or no condition)
        """
        # No condition = always true
        if not edge.condition:
            return True

        try:
            result = context.evaluate_condition(edge.condition)

            logger.debug(
                f"Edge condition evaluated: {edge.from_node} -> {edge.to_node}",
                extra={
                    'condition': edge.condition,
                    'result': result
                }
            )

            return result

        except Exception as exc:
            logger.warning(
                f"Edge condition evaluation failed: {exc}",
                extra={
                    'from_node': edge.from_node,
                    'to_node': edge.to_node,
                    'condition': edge.condition
                }
            )
            # On error, treat as false (don't execute)
            return False

    async def _execute_node(
        self,
        node_id: str,
        node: WorkflowNode,
        context: ContextManager
    ) -> Tuple[bool, ContextManager]:
        """
        Execute single node and return updated context.

        Args:
            node_id: Node identifier
            node: WorkflowNode to execute
            context: Current execution context

        Returns:
            Tuple[success, updated_context]:
                - (True, context_with_result) if successful
                - (False, context_with_error) if failed
        """
        logger.info(
            f"Executing node {node_id} (type: {node.type})",
            extra={
                'execution_id': str(self.execution.id),
                'node_id': node_id,
                'node_type': node.type
            }
        )

        # Update node status to running
        await sync_to_async(
            self.execution.update_node_status,
            thread_sensitive=True
        )(node_id, 'running')

        # Broadcast node start via WebSocket
        await self._broadcast_node_update(node_id, 'running')

        # Start OpenTelemetry span for node execution
        with start_node_span(
            node_id=node_id,
            node_name=node.name,
            node_type=node.type,
            execution_id=str(self.execution.id)
        ) as span:
            try:
                # Get appropriate handler
                handler = NodeHandlerFactory.get_handler(node.type)

                if span:
                    add_span_event("node_handler_resolved", {"handler_type": node.type})

                # Execute node
                if inspect.iscoroutinefunction(handler.execute):
                    result = await handler.execute(
                        node=node,
                        context=context.to_dict(),
                        execution=self.execution,
                        mode=NodeExecutionMode.SYNC
                    )
                else:
                    result = await sync_to_async(
                        handler.execute,
                        # IMPORTANT: do not run long-running node handlers in the
                        # global "thread_sensitive" executor. Operation nodes may
                        # synchronously wait for Go Worker completion, and that
                        # would starve other thread_sensitive DB tasks (including
                        # WebSocket handshake/status queries), causing frequent
                        # WS disconnect/reconnect during workflow execution.
                        thread_sensitive=False
                    )(
                        node=node,
                        context=context.to_dict(),
                        execution=self.execution,
                        mode=NodeExecutionMode.SYNC
                    )

                if result.success:
                    # Update context with node result
                    updated_context = context.add_node_result(
                        node_id,
                        {
                            'success': True,
                            'output': result.output,
                            'duration_seconds': result.duration_seconds
                        }
                    )

                    # Update node status
                    await sync_to_async(
                        self.execution.update_node_status,
                        thread_sensitive=True
                    )(
                        node_id, 'completed',
                        result={'output': result.output, 'duration': result.duration_seconds}
                    )

                    logger.info(
                        f"Node {node_id} completed successfully",
                        extra={
                            'execution_id': str(self.execution.id),
                            'node_id': node_id,
                            'duration_seconds': result.duration_seconds
                        }
                    )

                    # Broadcast node completion via WebSocket
                    await self._broadcast_node_update(
                        node_id, 'completed',
                        output=result.output,
                        duration_ms=int((result.duration_seconds or 0) * 1000)
                    )

                    if span:
                        set_span_attribute("node.status", "completed")
                        set_span_attribute("node.duration_seconds", result.duration_seconds)
                        add_span_event("node_completed")

                    return True, updated_context

                else:
                    # Node execution failed
                    error_context = context.add_node_result(
                        node_id,
                        {
                            'success': False,
                            'error': result.error,
                            'duration_seconds': result.duration_seconds
                        }
                    )

                    # Store last error for reporting
                    error_context = error_context.set('_last_error', {
                        'node_id': node_id,
                        'message': result.error
                    })

                    # Update node status
                    await sync_to_async(
                        self.execution.update_node_status,
                        thread_sensitive=True
                    )(
                        node_id, 'failed',
                        result={'error': result.error, 'duration': result.duration_seconds}
                    )

                    logger.error(
                        f"Node {node_id} failed: {result.error}",
                        extra={
                            'execution_id': str(self.execution.id),
                            'node_id': node_id,
                            'error': result.error
                        }
                    )

                    # Broadcast node failure via WebSocket
                    await self._broadcast_node_update(
                        node_id, 'failed',
                        error=result.error,
                        duration_ms=int((result.duration_seconds or 0) * 1000)
                    )

                    if span:
                        set_span_attribute("node.status", "failed")
                        set_span_attribute("node.error", result.error)
                        add_span_event("node_failed", {"error": result.error})

                    return False, error_context

            except ValueError as exc:
                # Handler not found or invalid
                error_msg = f"Handler error for node {node_id}: {exc}"
                logger.error(error_msg, extra={'node_id': node_id}, exc_info=True)

                await sync_to_async(
                    self.execution.update_node_status,
                    thread_sensitive=True
                )(
                    node_id, 'failed',
                    result={'error': error_msg}
                )

                error_context = context.set('_last_error', {
                    'node_id': node_id,
                    'message': error_msg
                })

                if span:
                    set_span_error(exc)

                return False, error_context

            except Exception as exc:
                # Unexpected error
                error_msg = f"Unexpected error executing node {node_id}: {exc}"
                logger.error(error_msg, extra={'node_id': node_id}, exc_info=True)

                await sync_to_async(
                    self.execution.update_node_status,
                    thread_sensitive=True
                )(
                    node_id, 'failed',
                    result={'error': error_msg}
                )

                error_context = context.set('_last_error', {
                    'node_id': node_id,
                    'message': error_msg
                })

                if span:
                    set_span_error(exc)

                return False, error_context

    def get_next_nodes(
        self,
        current_node_id: str,
        context: ContextManager
    ) -> List[str]:
        """
        Get next nodes to execute based on edge conditions.

        Used for async execution to determine next steps.

        Args:
            current_node_id: Current node ID
            context: Current execution context

        Returns:
            List of next node IDs that should be executed
        """
        next_nodes = []

        # Get outgoing edges
        outgoing = self.outgoing_edges.get(current_node_id, [])

        for edge in outgoing:
            if self._evaluate_edge_condition(edge, context):
                next_nodes.append(edge.to_node)

        logger.debug(
            f"Next nodes for {current_node_id}: {next_nodes}",
            extra={
                'execution_id': str(self.execution.id),
                'current_node': current_node_id,
                'next_nodes': next_nodes
            }
        )

        return next_nodes

    async def _broadcast_node_update(
        self,
        node_id: str,
        status: str,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        duration_ms: Optional[int] = None
    ) -> None:
        """
        Broadcast node status update via WebSocket.

        Args:
            node_id: Node identifier
            status: New node status (running, completed, failed, skipped)
            output: Optional output data (for completed)
            error: Optional error message (for failed)
            duration_ms: Optional duration in milliseconds
        """
        try:
            # Calculate progress based on completed nodes
            total_nodes = len(self._topological_order) if self._topological_order else 1
            node_statuses = self.execution.node_statuses or {}

            # Count completed and failed nodes
            completed = sum(
                1 for s in node_statuses.values()
                if isinstance(s, dict) and s.get('status') in ('completed', 'failed', 'skipped')
            )

            progress = completed / total_nodes if total_nodes > 0 else 0

            # Get current trace context
            trace_id = self.execution.trace_id
            span_id = get_current_span_id()

            # Broadcast node update
            await broadcast_node_update(
                execution_id=str(self.execution.id),
                node_id=node_id,
                status=status,
                output=output,
                error=error,
                duration_ms=duration_ms,
                span_id=span_id
            )

            # Also broadcast workflow progress update
            await broadcast_workflow_update(
                execution_id=str(self.execution.id),
                status='running',
                progress=progress,
                current_node_id=node_id,
                trace_id=trace_id
            )

        except Exception as exc:
            # Don't fail execution if broadcast fails
            logger.warning(
                f"Failed to broadcast node update: {exc}",
                extra={
                    'execution_id': str(self.execution.id),
                    'node_id': node_id,
                    'status': status
                }
            )

    @property
    def topological_order(self) -> List[str]:
        """Get topological order of nodes."""
        return self._topological_order or []
