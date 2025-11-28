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
    Отправляет задачи установки в Redis queue используя Message Protocol v2.0

    Args:
        database_ids: List[str] - список UUID баз
        extension_config: dict - конфигурация расширения
            {
                "name": "ODataAutoConfig",
                "path": "C:\\Extensions\\ODataAutoConfig.cfe"
            }

    Returns:
        dict: Статус операции
    """
    import uuid
    from datetime import datetime
    from .models import Database
    from apps.operations.models import BatchOperation, Task

    redis_client = get_redis_client()
    
    # Создать BatchOperation
    operation_id = str(uuid.uuid4())
    batch_operation = BatchOperation.objects.create(
        id=operation_id,
        name=f"Install {extension_config['name']}",
        description=f"Installing extension {extension_config['name']} on {len(database_ids)} database(s)",
        operation_type=BatchOperation.TYPE_INSTALL_EXTENSION,
        target_entity=extension_config['name'],
        payload={
            "extension_name": extension_config["name"],
            "extension_path": extension_config["path"]
        },
        config={
            "batch_size": 10,
            "timeout_seconds": 300,
            "retry_count": 3
        },
        status=BatchOperation.STATUS_PENDING
    )
    
    # Создать Task для каждой базы
    tasks = []
    valid_db_ids = []
    
    for db_id in database_ids:
        try:
            db = Database.objects.get(id=db_id)
            
            # Создать задачу для этой базы
            task = Task.objects.create(
                id=str(uuid.uuid4()),
                batch_operation=batch_operation,
                database=db,
                status=Task.STATUS_PENDING,
                max_retries=3
            )
            tasks.append(task)
            valid_db_ids.append(str(db.id))
            
            logger.info(f"Created task for database {db.name} (task_id={task.id})")
            
        except Database.DoesNotExist:
            logger.error(f"Database {db_id} not found")
            continue
        except Exception as e:
            logger.error(f"Error creating task for database {db_id}: {e}")
            continue
    
    # Связать базы с batch операцией
    if valid_db_ids:
        batch_operation.target_databases.set(Database.objects.filter(id__in=valid_db_ids))
        batch_operation.total_tasks = len(tasks)
        batch_operation.status = BatchOperation.STATUS_QUEUED
        batch_operation.save()
    
    if not valid_db_ids:
        logger.warning("No valid databases found for installation")
        batch_operation.status = BatchOperation.STATUS_FAILED
        batch_operation.save()
        return {
            "status": "failed",
            "queued_count": 0,
            "total_requested": len(database_ids),
            "error": "No valid databases"
        }
    
    # Сформировать OperationMessage v2.0
    message = {
        "version": "2.0",
        "operation_id": batch_operation.id,
        "batch_id": batch_operation.id,
        "operation_type": "install_extension",
        "entity": "extension",
        "target_databases": valid_db_ids,
        "payload": {
            "data": {
                "extension_name": extension_config["name"],
                "extension_path": extension_config["path"]
            },
            "filters": {},
            "options": {}
        },
        "execution_config": {
            "batch_size": 10,
            "timeout_seconds": 300,
            "retry_count": 3,
            "priority": "normal",
            "idempotency_key": batch_operation.id
        },
        "metadata": {
            "created_by": "orchestrator",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "template_id": "",
            "tags": ["extension", "install", extension_config["name"]]
        }
    }

    # Создать lock key для idempotency check в Go Worker (ДО отправки в queue!)
    lock_key = f"cc1c:task:{batch_operation.id}:lock"
    redis_client.setex(lock_key, 3600, "1")  # TTL 1 час

    # Отправить в Redis queue (Message Protocol v2.0)
    redis_client.lpush("cc1c:operations:v1", json.dumps(message))

    logger.info(f"Queued extension installation operation (operation_id={batch_operation.id}, databases={len(valid_db_ids)})")
    
    return {
        "status": "queued",
        "operation_id": batch_operation.id,
        "queued_count": len(valid_db_ids),
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
    Использует RAS Adapter v2 API.
    Запускается каждые 60 секунд через Celery Beat.
    """
    from .models import Cluster
    from .clients import RasAdapterClient

    clusters = Cluster.objects.exclude(
        status=Cluster.STATUS_MAINTENANCE
    ).only(
        'id', 'name', 'cluster_service_url', 'consecutive_failures',
        'status', 'last_sync_error'
    )

    for cluster in clusters:
        try:
            # cluster_service_url now points to RAS Adapter
            with RasAdapterClient(base_url=cluster.cluster_service_url) as client:
                is_healthy = client.health_check()

            cluster.mark_health_check(
                success=is_healthy,
                error_message=None if is_healthy else "RAS Adapter unavailable"
            )

            logger.info(f"Cluster {cluster.name} health check: {'OK' if is_healthy else 'FAILED'}")

        except Exception as e:
            cluster.mark_health_check(success=False, error_message=str(e))
            logger.error(f"Error checking cluster {cluster.name}: {e}")

    return {
        'checked': clusters.count(),
        'timestamp': timezone.now().isoformat()
    }


@shared_task
def sync_cluster_task(cluster_id: str):
    """
    Синхронизация инфобаз для одного кластера.
    Вызывается из API v2 endpoint /clusters/sync-cluster/.

    Использует ClusterService.sync_infobases() - тот же метод что и админка.

    Args:
        cluster_id: UUID кластера для синхронизации

    Returns:
        dict: {status, cluster_id, created, updated, errors} или {status, error}
    """
    from .models import Cluster
    from .services import ClusterService

    logger.info(f"Starting sync_cluster_task for cluster_id={cluster_id}")

    try:
        cluster = Cluster.objects.get(id=cluster_id)

        # Вызываем тот же метод что использует админка
        result = ClusterService.sync_infobases(cluster)

        logger.info(
            f"Cluster {cluster.name} sync completed: "
            f"created={result['created']}, updated={result['updated']}, errors={result['errors']}"
        )

        return {
            'status': 'success',
            'cluster_id': str(cluster_id),
            'cluster_name': cluster.name,
            'created': result['created'],
            'updated': result['updated'],
            'errors': result['errors'],
            'databases_found': result['created'] + result['updated'],
            'timestamp': timezone.now().isoformat()
        }

    except Cluster.DoesNotExist:
        logger.error(f"Cluster not found: {cluster_id}")
        return {
            'status': 'error',
            'cluster_id': str(cluster_id),
            'error': 'Cluster not found'
        }
    except Exception as e:
        logger.error(f"Error syncing cluster {cluster_id}: {e}", exc_info=True)
        return {
            'status': 'error',
            'cluster_id': str(cluster_id),
            'error': str(e)
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
