# Celery Event Replay - Usage Guide

## Quick Start

### 1. Verify Installation

Check that Celery Beat is running:
```bash
./scripts/dev/start-all.sh
```

Verify the task is registered:
```bash
celery -A config.celery inspect registered
```

You should see:
```
apps.operations.tasks.event_replay.replay_failed_events
apps.operations.tasks.event_replay.cleanup_old_replayed_events
```

### 2. Check Current Schedule

```bash
celery -A config.celery inspect scheduled
```

Output should show:
```
replay-failed-events: {schedule: <60.0s>, args: (), kwargs: {'batch_size': 100}, ...}
cleanup-old-replayed-events: {schedule: <crontab: 4 0 * * * (UTC)>, ...}
```

## Common Tasks

### View Pending Events

```python
from apps.operations.models import FailedEvent

# Count pending
pending = FailedEvent.objects.filter(status='pending')
print(f"Pending events: {pending.count()}")

# Show details
for event in pending[:10]:
    print(f"ID: {event.id}")
    print(f"  Type: {event.event_type}")
    print(f"  Correlation: {event.correlation_id}")
    print(f"  Retries: {event.retry_count}/{event.max_retries}")
    print(f"  Error: {event.last_error}")
    print()
```

### Manually Trigger Replay

```bash
# Trigger immediately (don't wait for schedule)
celery -A config.celery call apps.operations.tasks.event_replay.replay_failed_events

# With custom batch size
celery -A config.celery call apps.operations.tasks.event_replay.replay_failed_events \
    --kwargs='{"batch_size": 500}'
```

Or from Python:
```python
from apps.operations.tasks.event_replay import replay_failed_events

# Queue the task
task = replay_failed_events.delay(batch_size=200)
print(f"Task ID: {task.id}")
print(f"Status: {task.status}")
print(f"Result: {task.result}")
```

### Check Task Results

```python
from celery.result import AsyncResult

# Get result of a specific task
result = AsyncResult('task-id-here')
print(f"Status: {result.status}")  # PENDING, STARTED, SUCCESS, FAILURE
print(f"Result: {result.result}")
```

### View Failed Events

```python
from apps.operations.models import FailedEvent

# Count failed
failed = FailedEvent.objects.filter(status='failed')
print(f"Failed events: {failed.count()}")

# Show details
for event in failed[:10]:
    print(f"ID: {event.id}")
    print(f"  Type: {event.event_type}")
    print(f"  Correlation: {event.correlation_id}")
    print(f"  Error: {event.last_error}")
    print()
```

### View Replayed Events

```python
from apps.operations.models import FailedEvent

# Count replayed
replayed = FailedEvent.objects.filter(status='replayed')
print(f"Replayed events: {replayed.count()}")

# Show details
for event in replayed.order_by('-replayed_at')[:10]:
    print(f"ID: {event.id}")
    print(f"  Type: {event.event_type}")
    print(f"  Replayed at: {event.replayed_at}")
    print(f"  Retries: {event.retry_count}")
    print()
```

## Troubleshooting

### Events Stuck in PENDING

**Symptom:** Events remain in PENDING status even after tasks run

**Solution:**
```python
# Check Redis connectivity
import redis
redis_client = redis.Redis.from_url('redis://localhost:6379/0')
redis_client.ping()  # Should return True

# Check error messages
from apps.operations.models import FailedEvent
for event in FailedEvent.objects.filter(status='pending'):
    if event.last_error:
        print(f"{event.id}: {event.last_error}")
```

### Task Not Running

**Symptom:** Task never executes even though schedule is set

**Solution:**
```bash
# Check Celery Beat is running
ps aux | grep celery

# Check Django settings
cd orchestrator
python manage.py shell
>>> from django.conf import settings
>>> print(settings.CELERY_BROKER_URL)
>>> print(settings.CELERY_RESULT_BACKEND)

# Restart Beat
./scripts/dev/restart-service celery-beat
```

### High Memory Usage

**Symptom:** Memory increases rapidly

**Solution:**
```python
# Reduce batch size
# In config/celery.py:
'kwargs': {'batch_size': 50}  # Default is 100

# Run cleanup more often
# In config/celery.py:
'schedule': crontab(hour=0, minute=0)  # Run at midnight instead of 4 AM
```

### Timeout Errors

**Symptom:** Tasks fail with timeout

**Solution:**
```python
# Increase timeout in config/celery.py:
app.conf.task_soft_time_limit = 120  # Increase from 60
app.conf.task_time_limit = 130       # Increase from 70

# Or limit batch size
'kwargs': {'batch_size': 50}  # Smaller batches = faster execution
```

## Performance Monitoring

### Monitor Task Execution

```python
from celery.result import AsyncResult
import json

# Get active tasks
from apps.operations.tasks.event_replay import replay_failed_events

# Look at recent task results
from django.core.cache import cache

key = 'last_replay_task_result'
result = cache.get(key)
if result:
    print(json.dumps(result, indent=2))
```

### Database Query Performance

```python
from django.db import connection
from django.conf import settings

# Enable query logging
settings.DEBUG = True

# Run the query
from apps.operations.models import FailedEvent
pending = list(FailedEvent.objects.filter(status='pending')[:100])

# Check how many queries were executed
print(f"Queries: {len(connection.queries)}")
for query in connection.queries:
    print(f"  {query['time']}s: {query['sql'][:100]}")
```

### Redis Connection Performance

```python
import redis
import time

redis_client = redis.Redis.from_url('redis://localhost:6379/0')

# Measure ping time
start = time.time()
redis_client.ping()
elapsed = time.time() - start
print(f"Redis ping: {elapsed*1000:.2f}ms")

# Measure stream write
start = time.time()
redis_client.xadd('test_stream', {'test': 'data'})
elapsed = time.time() - start
print(f"XADD: {elapsed*1000:.2f}ms")
```

## Advanced Usage

### Custom Batch Processing

```python
from apps.operations.tasks.event_replay import replay_failed_events
from celery import group

# Process multiple batches in parallel
jobs = [
    replay_failed_events.s(batch_size=100),
    replay_failed_events.s(batch_size=100),
    replay_failed_events.s(batch_size=100),
]

result = group(jobs).apply_async()
print(f"Processing {len(jobs)} batches in parallel")
```

### Monitor with Custom Script

```python
#!/usr/bin/env python
import os
import django
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.operations.models import FailedEvent

while True:
    pending = FailedEvent.objects.filter(status='pending').count()
    replayed = FailedEvent.objects.filter(status='replayed').count()
    failed = FailedEvent.objects.filter(status='failed').count()

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
          f"Pending: {pending}, Replayed: {replayed}, Failed: {failed}")

    time.sleep(5)
```

### Export Events for Analysis

```python
import csv
from apps.operations.models import FailedEvent

# Export failed events
failed = FailedEvent.objects.filter(status='failed')

with open('failed_events.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['id', 'event_type', 'correlation_id', 'error', 'created_at'])

    for event in failed:
        writer.writerow([
            event.id,
            event.event_type,
            event.correlation_id,
            event.last_error,
            event.created_at.isoformat(),
        ])

print(f"Exported {failed.count()} events to failed_events.csv")
```

## Testing

### Run Unit Tests

```bash
cd orchestrator
pytest apps/operations/tests/test_event_replay.py -v
```

### Test Specific Scenario

```bash
# Test no pending events
pytest apps/operations/tests/test_event_replay.py::EventReplayTaskTests::test_no_pending_events -v

# Test successful replay
pytest apps/operations/tests/test_event_replay.py::EventReplayTaskTests::test_successful_replay -v
```

### Coverage Report

```bash
pytest apps/operations/tests/test_event_replay.py --cov=apps.operations.tasks.event_replay --cov-report=html
# View htmlcov/index.html in browser
```

### Manual Integration Test

```python
import os
import django
from unittest.mock import patch, MagicMock

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.operations.models import FailedEvent
from apps.operations.tasks.event_replay import replay_failed_events
from django.utils import timezone

# Create test event
event = FailedEvent.objects.create(
    channel='events:test',
    event_type='test.integration',
    correlation_id='test-corr-123',
    payload={'test': 'data'},
    source_service='test',
    original_timestamp=timezone.now(),
    status=FailedEvent.STATUS_PENDING,
)

print(f"Created event: {event.id}")

# Mock Redis and run task
with patch('apps.operations.tasks.event_replay.redis.Redis.from_url') as mock_redis:
    mock_client = MagicMock()
    mock_redis.return_value = mock_client

    result = replay_failed_events()

    print(f"Task result: {result}")

    # Verify event status
    event.refresh_from_db()
    print(f"Event status: {event.status}")
```

## Performance Tuning Examples

### For High-Volume Events (>10k/hour)

```python
# In config/celery.py:
app.conf.beat_schedule = {
    'replay-failed-events': {
        'task': 'apps.operations.tasks.event_replay.replay_failed_events',
        'schedule': 30.0,  # More frequent (every 30 seconds)
        'kwargs': {'batch_size': 500},  # Larger batches
        'options': {'expires': 25.0}
    },
}

# Also increase timeouts:
app.conf.task_soft_time_limit = 120
app.conf.task_time_limit = 130
```

### For Low-Volume Events (<100/hour)

```python
# In config/celery.py:
app.conf.beat_schedule = {
    'replay-failed-events': {
        'task': 'apps.operations.tasks.event_replay.replay_failed_events',
        'schedule': 300.0,  # Less frequent (every 5 minutes)
        'kwargs': {'batch_size': 50},  # Smaller batches
        'options': {'expires': 290.0}
    },
}
```

### For Memory-Constrained Environments

```python
# In config/celery.py:
app.conf.beat_schedule = {
    'replay-failed-events': {
        'task': 'apps.operations.tasks.event_replay.replay_failed_events',
        'schedule': 120.0,  # Every 2 minutes
        'kwargs': {'batch_size': 25},  # Very small batches
        'options': {'expires': 110.0}
    },

    'cleanup-old-replayed-events': {
        'task': 'apps.operations.tasks.event_replay.cleanup_old_replayed_events',
        'schedule': crontab(hour=2, minute=0),  # More frequent cleanup
        'kwargs': {'days': 3},  # Keep fewer days
    },
}
```

## Related Documentation

- [Event Replay Task Implementation](orchestrator/apps/operations/tasks/README.md)
- [FailedEvent Model](orchestrator/apps/operations/models.py)
- [Celery Configuration](orchestrator/config/celery.py)
- [Event Subscriber](orchestrator/apps/operations/event_subscriber.py)

## Support

For issues or questions, refer to:
1. Task logs: `docker logs celery-worker`
2. Beat logs: `docker logs celery-beat`
3. Django admin: http://localhost:8000/admin/operations/failedevent/
4. Test suite: `pytest apps/operations/tests/test_event_replay.py -v`
