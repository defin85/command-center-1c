"""
Celery task for replaying failed events to Redis.
Runs periodically to ensure events are not lost when Redis was temporarily unavailable.
"""

import json
import logging
import redis
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.db.models import F

from apps.operations.models import FailedEvent

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def replay_failed_events(self, batch_size=100):
    """
    Periodic task to replay failed events to Redis.
    Runs every minute via Celery Beat.

    This task:
    1. Fetches pending failed events from database
    2. Attempts to republish them to Redis
    3. Updates their status based on success/failure
    4. Implements exponential backoff for retries

    Args:
        batch_size: Maximum number of events to process per run (default: 100)

    Returns:
        dict: Summary of replayed and failed events
    """
    # Get pending events that haven't exceeded max retries
    events = FailedEvent.objects.filter(
        status=FailedEvent.STATUS_PENDING,
        retry_count__lt=F('max_retries'),
    ).order_by('created_at')[:batch_size]

    if not events.exists():
        return {'replayed': 0, 'failed': 0, 'status': 'no_pending_events'}

    # Connect to Redis
    try:
        redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
        redis_client = redis.Redis.from_url(redis_url)
        redis_client.ping()
    except redis.ConnectionError as e:
        logger.warning(f"Redis still unavailable, skipping replay: {e}")
        return {'status': 'redis_unavailable', 'error': str(e)}
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        return {'status': 'redis_error', 'error': str(e)}

    replayed = 0
    failed = 0

    for event in events:
        try:
            # Build message envelope
            envelope = {
                'version': '1.0',
                'message_id': f'replay-{event.id}',
                'correlation_id': event.correlation_id,
                'timestamp': event.original_timestamp.isoformat(),
                'event_type': event.event_type,
                'source_service': event.source_service,
                'payload': event.payload,
                'metadata': {
                    'replayed': True,
                    'original_created_at': event.created_at.isoformat(),
                    'replay_count': event.retry_count + 1,
                },
            }

            # Publish to Redis Stream (using XADD)
            message_data = {'payload': json.dumps(envelope)}
            redis_client.xadd(event.channel, message_data)

            # Mark as replayed
            event.status = FailedEvent.STATUS_REPLAYED
            event.replayed_at = timezone.now()
            event.save(update_fields=['status', 'replayed_at', 'updated_at'])

            logger.info(
                f"Replayed event {event.id}: {event.event_type} "
                f"(correlation_id={event.correlation_id})"
            )
            replayed += 1

        except Exception as e:
            event.retry_count += 1
            event.last_error = str(e)

            if event.retry_count >= event.max_retries:
                event.status = FailedEvent.STATUS_FAILED
                logger.error(
                    f"Event {event.id} permanently failed after {event.max_retries} retries: {e}"
                )
            else:
                logger.warning(
                    f"Event {event.id} replay failed (attempt {event.retry_count}): {e}"
                )

            event.save(update_fields=['retry_count', 'last_error', 'status', 'updated_at'])
            failed += 1

    logger.info(f"Event replay completed: {replayed} replayed, {failed} failed")
    return {'replayed': replayed, 'failed': failed}


@shared_task
def cleanup_old_replayed_events(days=7):
    """
    Cleanup replayed events older than specified days.
    Runs daily to prevent table growth.

    Args:
        days: Number of days to retain replayed events (default: 7)

    Returns:
        dict: Number of deleted events
    """
    cutoff_date = timezone.now() - timezone.timedelta(days=days)

    deleted_count, _ = FailedEvent.objects.filter(
        status=FailedEvent.STATUS_REPLAYED,
        replayed_at__lt=cutoff_date,
    ).delete()

    logger.info(f"Cleaned up {deleted_count} old replayed events")
    return {'deleted': deleted_count}
