"""
Django Channels consumers for real-time workflow updates.

Provides WebSocket endpoints for:
- Real-time workflow execution status updates
- Node execution progress notifications
- Client-initiated status queries
"""
import logging
from typing import Optional, Any, Dict
from uuid import UUID

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)


class UUIDEncoder(DjangoJSONEncoder):
    """JSON encoder that handles UUID objects."""

    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)


class WorkflowExecutionConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for workflow execution updates.

    Provides real-time updates for:
    - Workflow status changes (pending -> running -> completed/failed)
    - Individual node execution progress
    - Error notifications

    Client messages:
    - {"action": "get_status"} - Request current workflow status
    - {"action": "subscribe_nodes", "node_ids": [...]} - Subscribe to specific nodes

    Server messages:
    - {"type": "workflow_status", "status": "...", "progress": 0.0-1.0, ...}
    - {"type": "node_status", "node_id": "...", "status": "...", ...}
    - {"type": "error", "message": "...", "code": "..."}
    """

    # Group name prefix for workflow executions
    GROUP_PREFIX = "workflow_execution_"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.execution_id: Optional[str] = None
        self.group_name: Optional[str] = None
        self.subscribed_nodes: set = set()

    async def connect(self):
        """
        Handle WebSocket connection.

        Validates execution_id and joins the corresponding channel group.
        """
        self.execution_id = self.scope["url_route"]["kwargs"].get("execution_id")

        if not self.execution_id:
            logger.warning("WebSocket connection rejected: missing execution_id")
            await self.close(code=4000)
            return

        # Validate UUID format
        try:
            UUID(self.execution_id)
        except ValueError:
            logger.warning(f"WebSocket connection rejected: invalid execution_id format: {self.execution_id}")
            await self.close(code=4001)
            return

        # Validate execution exists
        execution = await self._get_execution()
        if not execution:
            logger.warning(f"WebSocket connection rejected: execution not found: {self.execution_id}")
            await self.close(code=4004)
            return

        self.group_name = f"{self.GROUP_PREFIX}{self.execution_id}"

        # Join the execution's channel group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        logger.info(f"WebSocket connected: execution_id={self.execution_id}, channel={self.channel_name}")

        # Send current status immediately after connection
        await self._send_current_status()

    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection.

        Leaves the channel group for this execution.
        """
        if self.group_name:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

        logger.info(f"WebSocket disconnected: execution_id={self.execution_id}, code={close_code}")

    async def receive_json(self, content: Dict[str, Any], **kwargs):
        """
        Handle incoming JSON messages from the client.

        Supported actions:
        - get_status: Request current workflow status
        - subscribe_nodes: Subscribe to specific node updates
        - unsubscribe_nodes: Unsubscribe from node updates
        """
        action = content.get("action")

        if not action:
            await self.send_error("missing_action", "Message must include 'action' field")
            return

        if action == "get_status":
            await self._send_current_status()

        elif action == "subscribe_nodes":
            node_ids = content.get("node_ids", [])
            if isinstance(node_ids, list):
                self.subscribed_nodes.update(node_ids)
                await self.send_json({
                    "type": "subscription_update",
                    "subscribed_nodes": list(self.subscribed_nodes)
                })

        elif action == "unsubscribe_nodes":
            node_ids = content.get("node_ids", [])
            if isinstance(node_ids, list):
                self.subscribed_nodes.difference_update(node_ids)
                await self.send_json({
                    "type": "subscription_update",
                    "subscribed_nodes": list(self.subscribed_nodes)
                })

        elif action == "ping":
            # Heartbeat/keepalive support
            await self.send_json({"type": "pong"})

        else:
            await self.send_error("unknown_action", f"Unknown action: {action}")

    async def workflow_update(self, event: Dict[str, Any]):
        """
        Handler for workflow status updates (called via channel layer).

        Event format:
        {
            "type": "workflow_update",
            "status": "running",
            "progress": 0.5,
            "current_node_id": "node_1",
            "trace_id": "...",
            "updated_at": "2025-01-01T00:00:00Z"
        }
        """
        await self.send_json({
            "type": "workflow_status",
            "execution_id": self.execution_id,
            "status": event.get("status"),
            "progress": event.get("progress"),
            "current_node_id": event.get("current_node_id"),
            "trace_id": event.get("trace_id"),
            "error_message": event.get("error_message"),
            "updated_at": event.get("updated_at"),
        })

    async def node_update(self, event: Dict[str, Any]):
        """
        Handler for individual node status updates (called via channel layer).

        Event format:
        {
            "type": "node_update",
            "node_id": "node_1",
            "status": "completed",
            "output": {...},
            "duration_ms": 150,
            "span_id": "...",
            "started_at": "...",
            "completed_at": "..."
        }
        """
        node_id = event.get("node_id")

        # If client subscribed to specific nodes, filter
        if self.subscribed_nodes and node_id not in self.subscribed_nodes:
            return

        await self.send_json({
            "type": "node_status",
            "execution_id": self.execution_id,
            "node_id": node_id,
            "status": event.get("status"),
            "output": event.get("output"),
            "error": event.get("error"),
            "duration_ms": event.get("duration_ms"),
            "span_id": event.get("span_id"),
            "started_at": event.get("started_at"),
            "completed_at": event.get("completed_at"),
        })

    async def execution_completed(self, event: Dict[str, Any]):
        """
        Handler for workflow completion (called via channel layer).

        Event format:
        {
            "type": "execution_completed",
            "status": "completed" | "failed" | "cancelled",
            "result": {...},
            "error_message": "...",
            "duration_ms": 5000
        }
        """
        await self.send_json({
            "type": "execution_completed",
            "execution_id": self.execution_id,
            "status": event.get("status"),
            "result": event.get("result"),
            "error_message": event.get("error_message"),
            "duration_ms": event.get("duration_ms"),
            "completed_at": event.get("completed_at"),
        })

    async def send_error(self, code: str, message: str):
        """Send error message to the client."""
        await self.send_json({
            "type": "error",
            "code": code,
            "message": message
        })

    @database_sync_to_async
    def _get_execution(self):
        """Get workflow execution from database."""
        from apps.templates.workflow.models import WorkflowExecution

        try:
            return WorkflowExecution.objects.select_related('workflow_template').get(
                id=self.execution_id
            )
        except WorkflowExecution.DoesNotExist:
            return None

    async def _send_current_status(self):
        """Send current workflow execution status to the client."""
        execution = await self._get_execution()

        if not execution:
            await self.send_error("not_found", f"Execution {self.execution_id} not found")
            return

        # Get execution data in sync context
        status_data = await self._get_execution_status(execution)

        await self.send_json({
            "type": "workflow_status",
            "execution_id": self.execution_id,
            **status_data
        })

    @database_sync_to_async
    def _get_execution_status(self, execution) -> Dict[str, Any]:
        """Get status data from execution object."""
        return {
            "status": execution.status,
            "progress": execution.progress_percent / 100.0,
            "current_node_id": execution.current_node_id,
            "trace_id": execution.trace_id,
            "error_message": execution.error_message,
            "node_statuses": execution.node_statuses or {},
            "created_at": execution.created_at.isoformat() if execution.created_at else None,
            "updated_at": execution.updated_at.isoformat() if execution.updated_at else None,
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
        }


# ============================================================================
# Helper functions for broadcasting from other parts of the application
# ============================================================================

async def broadcast_workflow_update(
    execution_id: str,
    status: str,
    progress: float = 0.0,
    current_node_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    error_message: Optional[str] = None,
):
    """
    Broadcast workflow status update to all connected clients.

    Call this from WorkflowEngine when status changes.
    """
    from channels.layers import get_channel_layer
    from datetime import datetime

    channel_layer = get_channel_layer()
    if not channel_layer:
        logger.warning("Channel layer not available, cannot broadcast workflow update")
        return

    group_name = f"{WorkflowExecutionConsumer.GROUP_PREFIX}{execution_id}"

    await channel_layer.group_send(
        group_name,
        {
            "type": "workflow_update",
            "status": status,
            "progress": progress,
            "current_node_id": current_node_id,
            "trace_id": trace_id,
            "error_message": error_message,
            "updated_at": datetime.utcnow().isoformat(),
        }
    )

    logger.debug(f"Broadcast workflow_update: execution={execution_id}, status={status}")


async def broadcast_node_update(
    execution_id: str,
    node_id: str,
    status: str,
    output: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    duration_ms: Optional[int] = None,
    span_id: Optional[str] = None,
):
    """
    Broadcast node status update to all connected clients.

    Call this from DAGExecutor when a node starts/completes.
    """
    from channels.layers import get_channel_layer
    from datetime import datetime

    channel_layer = get_channel_layer()
    if not channel_layer:
        logger.warning("Channel layer not available, cannot broadcast node update")
        return

    group_name = f"{WorkflowExecutionConsumer.GROUP_PREFIX}{execution_id}"

    now = datetime.utcnow().isoformat()

    await channel_layer.group_send(
        group_name,
        {
            "type": "node_update",
            "node_id": node_id,
            "status": status,
            "output": output,
            "error": error,
            "duration_ms": duration_ms,
            "span_id": span_id,
            "started_at": now if status == "running" else None,
            "completed_at": now if status in ("completed", "failed", "skipped") else None,
        }
    )

    logger.debug(f"Broadcast node_update: execution={execution_id}, node={node_id}, status={status}")


async def broadcast_execution_completed(
    execution_id: str,
    status: str,
    result: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
):
    """
    Broadcast workflow completion to all connected clients.

    Call this from WorkflowEngine when execution completes.
    """
    from channels.layers import get_channel_layer
    from datetime import datetime

    channel_layer = get_channel_layer()
    if not channel_layer:
        logger.warning("Channel layer not available, cannot broadcast completion")
        return

    group_name = f"{WorkflowExecutionConsumer.GROUP_PREFIX}{execution_id}"

    await channel_layer.group_send(
        group_name,
        {
            "type": "execution_completed",
            "status": status,
            "result": result,
            "error_message": error_message,
            "duration_ms": duration_ms,
            "completed_at": datetime.utcnow().isoformat(),
        }
    )

    logger.info(f"Broadcast execution_completed: execution={execution_id}, status={status}")


# ============================================================================
# Synchronous wrappers for use from non-async code (Celery tasks, etc.)
# ============================================================================

def sync_broadcast_workflow_update(
    execution_id: str,
    status: str,
    progress: float = 0.0,
    current_node_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    error_message: Optional[str] = None,
):
    """Synchronous wrapper for broadcast_workflow_update."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        # If called from async context, schedule as task
        asyncio.create_task(broadcast_workflow_update(
            execution_id, status, progress, current_node_id, trace_id, error_message
        ))
    else:
        # If called from sync context, run until complete
        loop.run_until_complete(broadcast_workflow_update(
            execution_id, status, progress, current_node_id, trace_id, error_message
        ))


def sync_broadcast_node_update(
    execution_id: str,
    node_id: str,
    status: str,
    output: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    duration_ms: Optional[int] = None,
    span_id: Optional[str] = None,
):
    """Synchronous wrapper for broadcast_node_update."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        asyncio.create_task(broadcast_node_update(
            execution_id, node_id, status, output, error, duration_ms, span_id
        ))
    else:
        loop.run_until_complete(broadcast_node_update(
            execution_id, node_id, status, output, error, duration_ms, span_id
        ))


def sync_broadcast_execution_completed(
    execution_id: str,
    status: str,
    result: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
):
    """Synchronous wrapper for broadcast_execution_completed."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        asyncio.create_task(broadcast_execution_completed(
            execution_id, status, result, error_message, duration_ms
        ))
    else:
        loop.run_until_complete(broadcast_execution_completed(
            execution_id, status, result, error_message, duration_ms
        ))
