"""
Django Channels consumers for Service Mesh monitoring.

Provides WebSocket endpoint for real-time service mesh metrics updates.
"""
import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.operations.services.prometheus_client import (
    get_prometheus_client,
    SERVICE_CONFIG,
)

logger = logging.getLogger(__name__)


class ServiceMeshConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for real-time service mesh metrics.

    Connects at: ws://localhost:8000/ws/service-mesh/

    Sends every 2 seconds:
    {
        "type": "metrics_update",
        "services": [...],
        "connections": [...],
        "overall_health": "healthy",
        "timestamp": "..."
    }

    Client messages:
    - {"action": "get_metrics"} - Request current metrics immediately
    - {"action": "ping"} - Heartbeat keepalive
    - {"action": "set_interval", "interval": 5} - Change update interval (2-30 seconds)
    """

    # Group name for broadcasting to all connected clients
    GROUP_NAME = "service_mesh_metrics"

    # Default update interval in seconds
    DEFAULT_INTERVAL = 2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._update_task: Optional[asyncio.Task] = None
        self._interval: int = self.DEFAULT_INTERVAL
        self._running: bool = False

    async def connect(self):
        """Handle WebSocket connection."""
        # Check authentication - reject anonymous users
        user = self.scope.get("user")
        if user is None or user.is_anonymous:
            logger.warning("Rejected unauthenticated WebSocket connection")
            await self.close(code=4001)
            return

        # Join the service mesh group for broadcasts
        await self.channel_layer.group_add(
            self.GROUP_NAME,
            self.channel_name
        )

        await self.accept()
        logger.info(f"Service mesh WebSocket connected: user={user}, channel={self.channel_name}")

        # Send initial metrics immediately
        await self._send_metrics()

        # Start periodic updates
        self._running = True
        self._update_task = asyncio.create_task(self._periodic_update())

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Stop periodic updates
        self._running = False
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

        # Leave the group
        await self.channel_layer.group_discard(
            self.GROUP_NAME,
            self.channel_name
        )

        logger.info(f"Service mesh WebSocket disconnected: code={close_code}")

    async def receive_json(self, content: Dict[str, Any], **kwargs):
        """Handle incoming JSON messages from the client."""
        action = content.get("action")

        if not action:
            await self.send_json({
                "type": "error",
                "code": "missing_action",
                "message": "Message must include 'action' field"
            })
            return

        if action == "get_metrics":
            # Send current metrics immediately
            await self._send_metrics()

        elif action == "ping":
            # Heartbeat response
            await self.send_json({"type": "pong"})

        elif action == "set_interval":
            # Change update interval
            interval = content.get("interval", self.DEFAULT_INTERVAL)
            try:
                interval = int(interval)
                # Clamp to 2-30 seconds
                self._interval = max(2, min(interval, 30))
                await self.send_json({
                    "type": "interval_updated",
                    "interval": self._interval
                })
            except (ValueError, TypeError):
                await self.send_json({
                    "type": "error",
                    "code": "invalid_interval",
                    "message": "Interval must be an integer between 2 and 30"
                })

        else:
            await self.send_json({
                "type": "error",
                "code": "unknown_action",
                "message": f"Unknown action: {action}"
            })

    async def _periodic_update(self):
        """Periodically fetch and send metrics to the client."""
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                if self._running:
                    await self._send_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic metrics update: {e}")
                # Continue running despite errors
                await asyncio.sleep(self._interval)

    async def _send_metrics(self):
        """Fetch metrics from Prometheus and send to client."""
        try:
            client = get_prometheus_client()

            # Fetch all metrics
            services_metrics = await client.get_all_services_metrics()
            connections = await client.get_service_connections()
            overall_health = await client.get_overall_health(services_metrics)

            # Send to client
            await self.send_json({
                "type": "metrics_update",
                "services": [m.to_dict() for m in services_metrics],
                "connections": [c.to_dict() for c in connections],
                "overall_health": overall_health,
                "timestamp": datetime.utcnow().isoformat(),
            })

        except Exception as e:
            logger.error(f"Error fetching service mesh metrics: {e}", exc_info=True)
            # Send error state with fallback data - don't expose error details
            await self.send_json({
                "type": "metrics_update",
                "services": self._get_fallback_services(),
                "connections": [],
                "overall_health": "degraded",
                "timestamp": datetime.utcnow().isoformat(),
                "error": "Metrics service temporarily unavailable",
            })

    def _get_fallback_services(self) -> list:
        """Generate fallback service data when Prometheus is unavailable."""
        fallback = []
        for name, config in SERVICE_CONFIG.items():
            fallback.append({
                'name': name,
                'display_name': config.get('display_name', name.title()),
                'status': 'degraded',
                'ops_per_minute': 0.0,
                'active_operations': 0,
                'p95_latency_ms': 0.0,
                'error_rate': 0.0,
                'last_updated': datetime.utcnow().isoformat(),
            })
        return fallback

    async def metrics_broadcast(self, event: Dict[str, Any]):
        """
        Handler for broadcast messages (called via channel layer).

        This allows other parts of the application to push updates
        to all connected service mesh clients.
        """
        await self.send_json({
            "type": "metrics_update",
            "services": event.get("services", []),
            "connections": event.get("connections", []),
            "overall_health": event.get("overall_health", "degraded"),
            "timestamp": event.get("timestamp", datetime.utcnow().isoformat()),
        })


# ============================================================================
# Helper functions for broadcasting from other parts of the application
# ============================================================================

async def broadcast_service_mesh_update(
    services: list,
    connections: list,
    overall_health: str,
):
    """
    Broadcast service mesh update to all connected clients.

    Can be called from external systems (e.g., when alerts trigger).
    """
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    if not channel_layer:
        logger.warning("Channel layer not available, cannot broadcast service mesh update")
        return

    await channel_layer.group_send(
        ServiceMeshConsumer.GROUP_NAME,
        {
            "type": "metrics_broadcast",
            "services": services,
            "connections": connections,
            "overall_health": overall_health,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )

    logger.debug("Broadcast service_mesh_update to all clients")


def sync_broadcast_service_mesh_update(
    services: list,
    connections: list,
    overall_health: str,
):
    """Synchronous wrapper for broadcast_service_mesh_update."""
    from asgiref.sync import async_to_sync

    async_to_sync(broadcast_service_mesh_update)(
        services, connections, overall_health
    )
