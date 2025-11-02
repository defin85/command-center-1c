"""Celery tasks для databases app."""

from celery import shared_task
from django.conf import settings
from django.utils import timezone
import redis
import json
import logging

logger = logging.getLogger(__name__)


@shared_task
def check_databases_health(database_ids):
    """
    Асинхронная проверка здоровья баз данных.

    Args:
        database_ids: List[str] - список ID баз для проверки

    Returns:
        dict: Результаты проверки
    """
    from .models import Database
    from .services import DatabaseService

    results = []
    healthy_count = 0

    for db_id in database_ids:
        try:
            db = Database.objects.get(id=db_id)
            result = DatabaseService.health_check_database(db)
            results.append({
                'database_id': str(db.id),
                'database_name': db.name,
                **result
            })
            if result['healthy']:
                healthy_count += 1
        except Database.DoesNotExist:
            logger.warning(f"Database {db_id} not found during health check")
            continue
        except Exception as e:
            logger.error(f"Error checking database {db_id}: {e}")
            continue

    return {
        'total': len(results),
        'healthy': healthy_count,
        'unhealthy': len(results) - healthy_count,
        'results': results
    }


def get_redis_client():
    """Получить Redis client"""
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=int(settings.REDIS_PORT),
        db=int(settings.REDIS_DB),
        decode_responses=True
    )


@shared_task
def queue_extension_installation(database_ids, extension_config):
    """
    Отправляет задачи установки в Redis queue для Windows Service

    Args:
        database_ids: List[int] - список ID баз
        extension_config: dict - конфигурация расширения
            {
                "name": "ODataAutoConfig",
                "path": "C:\\Extensions\\ODataAutoConfig.cfe"
            }

    Returns:
        dict: Статус операции
    """
    from .models import Database, ExtensionInstallation

    redis_client = get_redis_client()
    queued_count = 0

    for db_id in database_ids:
        try:
            db = Database.objects.get(id=db_id)

            # Создать запись об установке
            installation = ExtensionInstallation.objects.create(
                database=db,
                extension_name=extension_config["name"],
                status="pending",
                metadata={
                    "extension_path": extension_config["path"]
                }
            )

            # Подготовить задачу для Windows Service
            task_data = {
                "task_id": str(installation.id),
                "database_id": db.id,
                "database_name": db.name,
                "connection_string": f'/S"{db.odata_url.split("/")[2]}\\{db.name}"',  # извлечь server из URL
                "username": db.username,
                "password": db.password,  # EncryptedCharField автоматически расшифровывает при чтении
                "extension_path": extension_config["path"],
                "extension_name": extension_config["name"]
            }

            # Отправить в Redis queue
            redis_client.lpush("installation_tasks", json.dumps(task_data))
            queued_count += 1

            logger.info(f"Queued installation task for database {db.name} (id={db.id})")

        except Database.DoesNotExist:
            logger.error(f"Database {db_id} not found")
            continue
        except Exception as e:
            logger.error(f"Error queuing installation for database {db_id}: {e}")
            continue

    return {
        "status": "completed",
        "queued_count": queued_count,
        "total_requested": len(database_ids)
    }


@shared_task(bind=True)
def subscribe_installation_progress(self):
    """
    Фоновый worker для подписки на Redis pub/sub канал
    Обновляет статусы ExtensionInstallation по событиям

    События:
        - task_started: установка начата
        - task_completed: установка завершена успешно
        - task_failed: установка завершена с ошибкой
    """
    import signal
    import sys
    from .models import ExtensionInstallation

    redis_client = get_redis_client()
    pubsub = redis_client.pubsub()
    pubsub.subscribe("installation_progress")

    # Флаг для остановки
    should_stop = False

    def signal_handler(signum, frame):
        nonlocal should_stop
        should_stop = True
        logger.info("Received shutdown signal, stopping subscriber")

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    logger.info("Started listening to installation_progress channel")

    try:
        for message in pubsub.listen():
            if should_stop:
                break

            if message['type'] == 'message':
                try:
                    data = json.loads(message['data'])
                    event = data.get('event')
                    task_id = data.get('task_id')

                    if not task_id:
                        continue

                    installation = ExtensionInstallation.objects.get(id=task_id)

                    if event == 'task_started':
                        installation.status = 'in_progress'
                        installation.started_at = timezone.now()
                        installation.save()
                        logger.info(f"Task {task_id} started")

                    elif event == 'task_completed':
                        installation.status = 'completed'
                        installation.completed_at = timezone.now()
                        installation.duration_seconds = data.get('duration_seconds')
                        installation.save()
                        logger.info(f"Task {task_id} completed in {installation.duration_seconds}s")

                    elif event == 'task_failed':
                        installation.status = 'failed'
                        installation.error_message = data.get('error_message', 'Unknown error')
                        installation.completed_at = timezone.now()
                        installation.save()
                        logger.error(f"Task {task_id} failed: {installation.error_message}")

                    # TODO: Send WebSocket update to frontend
                    # send_websocket_update(data)

                except ExtensionInstallation.DoesNotExist:
                    logger.warning(f"Installation record {task_id} not found")
                except Exception as e:
                    logger.error(f"Error processing progress message: {e}")

    finally:
        pubsub.unsubscribe()
        pubsub.close()
        logger.info("Subscriber stopped gracefully")


# ============================================================================
# Periodic Health Check Tasks
# ============================================================================


@shared_task
def periodic_cluster_health_check():
    """
    Периодическая проверка здоровья всех активных кластеров.
    Запускается каждые 60 секунд через Celery Beat.
    """
    from .models import Cluster
    from .clients import ClusterServiceClient

    clusters = Cluster.objects.exclude(
        status=Cluster.STATUS_MAINTENANCE
    ).only(
        'id', 'name', 'cluster_service_url', 'consecutive_failures',
        'status', 'last_sync_error'
    )

    for cluster in clusters:
        try:
            with ClusterServiceClient(base_url=cluster.cluster_service_url) as client:
                is_healthy = client.health_check()

            cluster.mark_health_check(
                success=is_healthy,
                error_message=None if is_healthy else "Cluster service unavailable"
            )

            logger.info(f"Cluster {cluster.name} health check: {'OK' if is_healthy else 'FAILED'}")

        except Exception as e:
            cluster.mark_health_check(success=False, error_message=str(e))
            logger.error(f"Error checking cluster {cluster.name}: {e}")

    return {
        'checked': clusters.count(),
        'timestamp': timezone.now().isoformat()
    }


@shared_task(bind=True)
def periodic_database_health_check(self):
    """
    Периодическая проверка здоровья баз данных.
    Обрабатывает батчами по 20 баз для масштабируемости.
    Запускается каждые 60 секунд через Celery Beat.
    """
    from .models import Database
    from django_redis import get_redis_connection

    # Проверяем что предыдущий раунд завершился
    redis_conn = get_redis_connection("default")
    lock_key = "health_check:database:lock"

    # Проверяем lock
    if redis_conn.exists(lock_key):
        logger.warning("Previous database health check round still running, skipping")
        return {
            'skipped': True,
            'reason': 'previous_round_running',
            'timestamp': timezone.now().isoformat()
        }

    # Устанавливаем lock на 120 секунд (2x период)
    redis_conn.setex(lock_key, 120, "1")

    try:
        # Только активные базы с включенным health check
        active_databases = Database.objects.filter(
            status__in=[Database.STATUS_ACTIVE, Database.STATUS_ERROR],
            health_check_enabled=True
        ).order_by('last_check_at')  # Проверяем сначала самые старые

        total_count = active_databases.count()

        # Батчинг по 20 баз (для 700 баз = 35 батчей)
        batch_size = 20
        batches_created = 0

        for i in range(0, total_count, batch_size):
            batch = active_databases[i:i+batch_size]

            # Отправляем батч в отдельную задачу для параллельности
            check_database_batch.delay(list(batch.values_list('id', flat=True)))
            batches_created += 1

        logger.info(
            f"Database health check: created {batches_created} batches "
            f"for {total_count} databases"
        )

        return {
            'total_databases': total_count,
            'batches_created': batches_created,
            'timestamp': timezone.now().isoformat()
        }

    finally:
        # Освобождаем lock
        redis_conn.delete(lock_key)


@shared_task
def check_database_batch(database_ids):
    """
    Проверяет батч баз данных (вызывается из periodic_database_health_check).

    Args:
        database_ids: List[str] - ID баз для проверки
    """
    from .models import Database
    from .services import DatabaseService

    for db_id in database_ids:
        try:
            db = Database.objects.get(id=db_id)

            # DatabaseService.health_check_database уже вызывает mark_health_check внутри
            result = DatabaseService.health_check_database(db)

        except Database.DoesNotExist:
            logger.warning(f"Database {db_id} not found during health check")
        except Exception as e:
            logger.error(f"Error checking database {db_id}: {e}")

    return {
        'checked': len(database_ids),
        'timestamp': timezone.now().isoformat()
    }


@shared_task
def periodic_batch_service_health_check():
    """
    Периодическая проверка BatchService инстансов.
    Запускается каждые 30 секунд через Celery Beat.
    """
    from .models import BatchService
    from .clients import BatchServiceClient

    services = BatchService.objects.all()

    for service in services:
        try:
            with BatchServiceClient(base_url=service.url) as client:
                is_healthy = client.health_check()

            service.mark_health_check(
                success=is_healthy,
                error_message=None if is_healthy else "Batch service unavailable"
            )

            logger.info(f"BatchService {service.name} health check: {'OK' if is_healthy else 'FAILED'}")

        except Exception as e:
            service.mark_health_check(success=False, error_message=str(e))
            logger.error(f"Error checking BatchService {service.name}: {e}")

    return {
        'checked': services.count(),
        'timestamp': timezone.now().isoformat()
    }


@shared_task
def cleanup_old_status_history():
    """
    Удаляет записи StatusHistory старше 90 дней.
    Запускается раз в день (ночью).
    """
    from datetime import timedelta
    from .models import StatusHistory

    cutoff_date = timezone.now() - timedelta(days=90)
    deleted_count, _ = StatusHistory.objects.filter(changed_at__lt=cutoff_date).delete()

    logger.info(f"Cleaned up {deleted_count} old StatusHistory records (older than 90 days)")

    return {
        'deleted_count': deleted_count,
        'cutoff_date': cutoff_date.isoformat(),
        'timestamp': timezone.now().isoformat()
    }
