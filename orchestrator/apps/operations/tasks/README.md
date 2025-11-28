# Operations Tasks

## Event Replay (`event_replay.py`)

Celery tasks for replaying failed events that couldn't be published to Redis.

### Overview

When Redis is temporarily unavailable, events fail to publish. To ensure no events are lost, failed events are stored in the database (`FailedEvent` model) and then replayed periodically via Celery Beat.

### Tasks

#### `replay_failed_events(batch_size=100)`

**Schedule:** Every 60 seconds
**Purpose:** Replay pending failed events to Redis

**How it works:**
1. Queries database for pending events (status=PENDING) that haven't exceeded max retries
2. Attempts to reconnect to Redis
3. For each event, builds message envelope and publishes to Redis Stream (XADD)
4. Marks events as REPLAYED on success or increments retry count on failure
5. Marks events as FAILED if max retries exceeded

**Parameters:**
- `batch_size` (int, default=100): Max events to process per execution

**Returns:**
```python
{
    'replayed': int,    # Number of successfully replayed events
    'failed': int,      # Number of events that failed to replay
    'status': str       # 'no_pending_events' | 'redis_unavailable' | 'redis_error'
}
```

**Example:**
```bash
# Manual execution
celery -A config.celery call apps.operations.tasks.event_replay.replay_failed_events

# With parameters
celery -A config.celery call apps.operations.tasks.event_replay.replay_failed_events \
    --kwargs='{"batch_size": 200}'
```

#### `cleanup_old_replayed_events(days=7)`

**Schedule:** Daily at 04:00 UTC
**Purpose:** Clean up old replayed events to prevent table growth

**How it works:**
1. Queries database for replayed events older than specified days
2. Deletes matching events
3. Logs number of deleted records

**Parameters:**
- `days` (int, default=7): Retain replayed events for this many days

**Returns:**
```python
{
    'deleted': int  # Number of deleted events
}
```

### Configuration (Celery Beat)

Tasks are configured in `orchestrator/config/celery.py`:

```python
app.conf.beat_schedule = {
    'replay-failed-events': {
        'task': 'apps.operations.tasks.event_replay.replay_failed_events',
        'schedule': 60.0,  # Every minute
        'kwargs': {'batch_size': 100},
        'options': {'expires': 55.0}
    },

    'cleanup-old-replayed-events': {
        'task': 'apps.operations.tasks.event_replay.cleanup_old_replayed_events',
        'schedule': crontab(hour=4, minute=0),  # Daily at 4 AM UTC
        'kwargs': {'days': 7},
    },
}
```

### Database Model

Failed events are stored in `FailedEvent` model:

```python
class FailedEvent(models.Model):
    STATUS_PENDING = 'pending'      # Waiting to be replayed
    STATUS_REPLAYED = 'replayed'    # Successfully replayed
    STATUS_FAILED = 'failed'        # Permanently failed (max retries exceeded)

    channel          # Redis channel/stream name (db_index=True)
    event_type       # Type of event (e.g., 'operation.completed')
    correlation_id   # Unique correlation ID for tracing (db_index=True)
    payload          # Event data (JSONField)
    source_service   # Service that published event (e.g., 'worker')
    original_timestamp  # When event was originally created
    status           # Current status (pending/replayed/failed)
    retry_count      # Number of replay attempts
    max_retries      # Max allowed retries (default: 5)
    last_error       # Error message from last failed attempt
    replayed_at      # Timestamp of successful replay
```

### Message Format

Replayed events are published with this envelope format:

```json
{
    "version": "1.0",
    "message_id": "replay-{event_id}",
    "correlation_id": "...",
    "timestamp": "2025-01-15T10:30:00Z",
    "event_type": "operation.completed",
    "source_service": "worker",
    "payload": { ... },
    "metadata": {
        "replayed": true,
        "original_created_at": "2025-01-15T10:29:00Z",
        "replay_count": 1
    }
}
```

### Error Handling

**Exponential Backoff:**
- Failed events are retried automatically
- Each retry increments `retry_count`
- If `retry_count` reaches `max_retries`, event is marked as FAILED

**Redis Connection Errors:**
- Task catches `redis.ConnectionError` and returns `{'status': 'redis_unavailable'}`
- Celery will retry the task on next schedule (1 minute later)

**Per-Event Errors:**
- Individual event failures don't block batch processing
- Only that event's `retry_count` increments

### Monitoring

**Check pending events:**
```python
from apps.operations.models import FailedEvent

pending = FailedEvent.objects.filter(status=FailedEvent.STATUS_PENDING)
print(f"Pending events: {pending.count()}")
print(f"High-retry events: {pending.filter(retry_count__gte=4).count()}")
```

**Check recent failures:**
```python
failed = FailedEvent.objects.filter(status=FailedEvent.STATUS_FAILED)
for event in failed[:10]:
    print(f"{event.correlation_id}: {event.last_error}")
```

**Monitor task execution via Django admin:**
- Go to http://localhost:8000/admin/
- Navigate to "Operations > Failed Events"
- Filter by status to track pending/replayed/failed

### Performance Considerations

- **Batch Size:** Default 100 events per execution. Increase for high-volume scenarios, decrease if memory is constrained
- **Redis Timeout:** Events use Redis Stream (XADD) which is fast. Expect ~1ms per event
- **Cleanup:** Old replayed events are deleted daily to prevent unbounded growth
- **Indexes:** Database indexes on `(status, created_at)`, `correlation_id`, and `(channel, status)` for fast queries

### Testing

Run unit tests:
```bash
cd orchestrator
pytest apps/operations/tests/test_event_replay.py -v
```

Key test scenarios:
- No pending events → returns early
- Redis unavailable → returns error
- Successful replay → events marked as REPLAYED
- Failure with retries → retry_count incremented
- Max retries exceeded → event marked as FAILED

### Troubleshooting

**Events never replay:**
- Check Celery Beat is running: `celery -A config.celery inspect active_queues`
- Check logs: `docker logs celery-beat`
- Verify Redis connectivity: `redis-cli ping`

**Events stuck in PENDING:**
- Check Redis connectivity (see above)
- Check `last_error` field in database
- Verify event format matches Redis subscription expectations

**Cleanup not running:**
- Check Celery Beat schedule: `celery -A config.celery inspect scheduled`
- Verify time is set to UTC in Django settings

### Related

- [FailedEvent Model](../models.py) - Database model for storing failed events
- [Event Subscriber](../event_subscriber.py) - Subscribes to events from Redis
- [Celery Configuration](../../config/celery.py) - Beat schedule definition
