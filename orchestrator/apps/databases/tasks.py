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
