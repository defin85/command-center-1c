"""Django signals for automatic status history logging and dashboard invalidation."""

import logging
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from .models import Cluster, Database, StatusHistory
from .events import database_event_publisher

logger = logging.getLogger(__name__)


# Import broadcast function from operations signals (lazy import to avoid circular)
def _broadcast_dashboard_invalidate(scope: str, entity_id: str = None):
    """Lazy wrapper to avoid circular imports."""
    from apps.operations.signals import broadcast_dashboard_invalidate
    broadcast_dashboard_invalidate(scope, entity_id)


def _publish_database_stream_event(action: str, instance: Database) -> None:
    metadata = instance.metadata if isinstance(instance.metadata, dict) else {}
    database_event_publisher.publish(
        action=action,
        database_id=str(instance.id),
        cluster_id=str(instance.cluster_id) if instance.cluster_id else None,
        metadata={
            "status": instance.status,
            "health": instance.last_check_status,
            "sessions_deny": metadata.get("sessions_deny"),
            "scheduled_jobs_deny": metadata.get("scheduled_jobs_deny"),
        },
    )


@receiver(pre_save, sender=Cluster)
def log_cluster_status_change(sender, instance, **kwargs):
    """Log Cluster status changes to StatusHistory."""
    if not instance.pk:
        return  # Новый объект, пропускаем

    try:
        old_instance = Cluster.objects.get(pk=instance.pk)
        old_status = old_instance.status
        new_status = instance.status

        if old_status != new_status:
            # Создаем запись в истории
            StatusHistory.objects.create(
                content_object=instance,
                old_status=old_status,
                new_status=new_status,
                reason="Status updated",
                metadata={
                    'cluster_id': str(instance.id),
                    'consecutive_failures': instance.consecutive_failures,
                    'last_sync_error': instance.last_sync_error[:200] if instance.last_sync_error else '',
                    'changed_at': timezone.now().isoformat()
                }
            )
            logger.info(f"Cluster {instance.name}: status changed {old_status} → {new_status}")

    except Cluster.DoesNotExist:
        pass  # Объект не существовал, пропускаем


@receiver(pre_save, sender=Database)
def log_database_status_change(sender, instance, **kwargs):
    """Log Database status changes to StatusHistory."""
    if not instance.pk:
        return

    try:
        old_instance = Database.objects.get(pk=instance.pk)
        old_status = old_instance.status
        new_status = instance.status

        if old_status != new_status:
            StatusHistory.objects.create(
                content_object=instance,
                old_status=old_status,
                new_status=new_status,
                reason="Status updated",
                metadata={
                    'database_name': instance.name,
                    'cluster_id': str(instance.cluster.id) if instance.cluster else None,
                    'consecutive_failures': instance.consecutive_failures,
                    'last_check_status': instance.last_check_status,
                    'avg_response_time': round(float(instance.avg_response_time), 3) if instance.avg_response_time else None,
                    'changed_at': timezone.now().isoformat()
                }
            )
            logger.info(f"Database {instance.name}: status changed {old_status} → {new_status}")

    except Database.DoesNotExist:
        pass


# ============================================================================
# Dashboard invalidation signals
# ============================================================================

@receiver(post_save, sender=Cluster)
def on_cluster_saved(sender, instance, created, **kwargs):
    """Broadcast invalidation when Cluster is created or updated."""
    _broadcast_dashboard_invalidate("clusters", instance.id)


@receiver(post_delete, sender=Cluster)
def on_cluster_deleted(sender, instance, **kwargs):
    """Broadcast invalidation when Cluster is deleted."""
    _broadcast_dashboard_invalidate("clusters", instance.id)


@receiver(post_save, sender=Database)
def on_database_saved(sender, instance, created, **kwargs):
    """Broadcast invalidation when Database is created or updated."""
    _broadcast_dashboard_invalidate("databases", instance.id)
    _publish_database_stream_event("created" if created else "updated", instance)


@receiver(post_delete, sender=Database)
def on_database_deleted(sender, instance, **kwargs):
    """Broadcast invalidation when Database is deleted."""
    _broadcast_dashboard_invalidate("databases", instance.id)
    _publish_database_stream_event("deleted", instance)
