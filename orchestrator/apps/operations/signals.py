"""Django signals for dashboard invalidation via WebSocket."""

import asyncio
import logging
from datetime import datetime

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer

from .models import BatchOperation

logger = logging.getLogger(__name__)

# Group name for dashboard invalidation broadcasts (must match consumers.py)
DASHBOARD_GROUP = "dashboard_updates"


async def _broadcast_dashboard_invalidate_async(payload: dict) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning("Channel layer not available, cannot broadcast invalidation")
        return
    await channel_layer.group_send(DASHBOARD_GROUP, payload)


def broadcast_dashboard_invalidate(scope: str, entity_id: str = None):
    """
    Send invalidation signal to all connected WebSocket clients.

    Args:
        scope: Type of data that changed (e.g., "operations", "databases", "clusters")
        entity_id: Optional ID of the specific entity that changed
    """
    try:
        payload = {
            "type": "dashboard.invalidate",  # dot is replaced with underscore
            "scope": scope,
            "timestamp": datetime.now().isoformat(),
            "entity_id": str(entity_id) if entity_id else None,
        }
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(_broadcast_dashboard_invalidate_async(payload))
        else:
            loop.create_task(_broadcast_dashboard_invalidate_async(payload))
        logger.debug(f"Broadcast dashboard invalidation: scope={scope}, entity_id={entity_id}")
    except Exception as e:
        logger.error(f"Failed to broadcast dashboard invalidation: {e}")


@receiver(post_save, sender=BatchOperation)
def on_batch_operation_saved(sender, instance, created, **kwargs):
    """Broadcast invalidation when BatchOperation is created or updated."""
    broadcast_dashboard_invalidate("operations", instance.id)


@receiver(post_delete, sender=BatchOperation)
def on_batch_operation_deleted(sender, instance, **kwargs):
    """Broadcast invalidation when BatchOperation is deleted."""
    broadcast_dashboard_invalidate("operations", instance.id)
