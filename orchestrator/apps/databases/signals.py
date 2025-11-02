"""Django signals for automatic status history logging."""

import logging
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Cluster, Database, BatchService, StatusHistory

logger = logging.getLogger(__name__)


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
                reason=f"Health check result (consecutive_failures={instance.consecutive_failures})",
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
                reason=f"Health check result (consecutive_failures={instance.consecutive_failures})",
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


@receiver(pre_save, sender=BatchService)
def log_batch_service_status_change(sender, instance, **kwargs):
    """Log BatchService status changes to StatusHistory."""
    if not instance.pk:
        return

    try:
        old_instance = BatchService.objects.get(pk=instance.pk)
        old_status = old_instance.status
        new_status = instance.status

        if old_status != new_status:
            StatusHistory.objects.create(
                content_object=instance,
                old_status=old_status,
                new_status=new_status,
                reason=f"Health check result (consecutive_failures={instance.consecutive_failures})",
                metadata={
                    'service_id': str(instance.id),
                    'consecutive_failures': instance.consecutive_failures,
                    'last_health_status': instance.last_health_status,
                    'changed_at': timezone.now().isoformat()
                }
            )
            logger.info(f"BatchService {instance.name}: status changed {old_status} → {new_status}")

    except BatchService.DoesNotExist:
        pass
