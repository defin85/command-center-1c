# Celery Event Replay Task - Implementation Summary

## What Was Created

### 1. Event Replay Task File
**Location:** `orchestrator/apps/operations/tasks/event_replay.py`

Contains two Celery tasks:
- `replay_failed_events(batch_size=100)` - Replays failed events every 60 seconds
- `cleanup_old_replayed_events(days=7)` - Cleans up old events daily at 04:00 UTC

### 2. Updated Celery Configuration
**Location:** `orchestrator/config/celery.py`

Added two tasks to `beat_schedule`:
```python
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
```

### 3. Unit Tests
**Location:** `orchestrator/apps/operations/tests/test_event_replay.py`

Test coverage includes:
- No pending events scenario
- Redis unavailable scenario
- Successful event replay
- Retry on failure
- Max retries exceeded
- Cleanup old events

Run tests:
```bash
cd orchestrator
pytest apps/operations/tests/test_event_replay.py -v
```

### 4. Package Structure
**Location:** `orchestrator/apps/operations/tasks/`

Created tasks package with:
- `__init__.py` - Package marker
- `event_replay.py` - Task implementations
- `README.md` - Detailed documentation

## How It Works

### Event Replay Flow

1. **Event Failure**: When Redis is unavailable, events are stored in `FailedEvent` table
2. **Scheduled Execution**: Celery Beat runs `replay_failed_events` every 60 seconds
3. **Batch Processing**: Up to 100 pending events are processed per execution
4. **Redis Reconnection**: Task tries to reconnect to Redis
5. **Event Republishing**: Each event is published to Redis Stream (XADD)
6. **Status Update**: 
   - Success → status = REPLAYED, replayed_at = now
   - Failure → retry_count++, status = PENDING (if retries remain)
   - Max retries exceeded → status = FAILED

### Cleanup Flow

1. **Daily Execution**: Celery Beat runs at 04:00 UTC
2. **Query**: Find all events with status=REPLAYED and replayed_at < 7 days ago
3. **Delete**: Remove matching records
4. **Log**: Record number of deleted events

## Database Model

Uses existing `FailedEvent` model in `orchestrator/apps/operations/models.py`:

```python
class FailedEvent(models.Model):
    STATUS_PENDING = 'pending'      # Waiting to be replayed
    STATUS_REPLAYED = 'replayed'    # Successfully replayed
    STATUS_FAILED = 'failed'        # Permanently failed
    
    channel              # Redis channel/stream name
    event_type           # Type of event
    correlation_id       # Unique correlation ID
    payload              # Event data (JSONField)
    source_service       # Service that published
    original_timestamp   # Original creation time
    status               # Current status
    retry_count          # Number of replay attempts
    max_retries          # Max allowed retries (default: 5)
    last_error           # Error message from last attempt
    replayed_at          # Time of successful replay
```

## Configuration Details

### Required Settings (in Django settings)

The task uses `REDIS_URL` from Django settings:
```python
# In orchestrator/config/settings/development.py
REDIS_URL = 'redis://localhost:6379/0'
```

If not specified, defaults to `'redis://localhost:6379/0'`

### Celery Beat Scheduler

The Celery Beat scheduler must be running:
```bash
cd orchestrator
celery -A config.celery beat
```

Or via the startup script:
```bash
./scripts/dev/start-all.sh
```

## Monitoring & Debugging

### View Pending Events
```python
from apps.operations.models import FailedEvent

pending = FailedEvent.objects.filter(status='pending')
print(f"Pending: {pending.count()}")
for event in pending[:5]:
    print(f"  {event.correlation_id}: {event.event_type}")
```

### View Failed Events
```python
failed = FailedEvent.objects.filter(status='failed')
print(f"Failed: {failed.count()}")
for event in failed[:5]:
    print(f"  {event.correlation_id}: {event.last_error}")
```

### Check Celery Beat Schedule
```bash
celery -A config.celery inspect scheduled
```

### View Task Logs
```bash
# Celery worker logs
docker logs celery-worker

# Celery Beat logs
docker logs celery-beat
```

### Django Admin
- Navigate to http://localhost:8000/admin/
- Go to "Operations > Failed Events"
- Filter by status to track progress

## Performance Tuning

### Batch Size
Increase for high-volume scenarios:
```python
# In celery.py
'replay-failed-events': {
    'kwargs': {'batch_size': 500},  # Increased from 100
}
```

### Cleanup Retention Period
Change how long to keep replayed events:
```python
# In celery.py
'cleanup-old-replayed-events': {
    'kwargs': {'days': 14},  # Changed from 7
}
```

### Retry Count
Modify max retries for events in FailedEvent model:
```python
# In models.py
max_retries = models.IntegerField(default=10)  # Changed from 5
```

## Error Handling

### Redis Connection Errors
- Task catches `redis.ConnectionError`
- Returns `{'status': 'redis_unavailable', 'error': 'message'}`
- Celery retries on next schedule (1 minute later)

### Per-Event Failures
- Individual event failures don't block batch processing
- `retry_count` increments for that event only
- If `retry_count >= max_retries`, event marked as FAILED

### Transaction Safety
- Each event update is atomic (Django ORM handles it)
- If Celery task crashes mid-batch, only processed events are updated
- Unprocessed events remain PENDING for next execution

## Testing

### Run Tests
```bash
cd orchestrator
pytest apps/operations/tests/test_event_replay.py -v
```

### Test Coverage
```bash
pytest apps/operations/tests/test_event_replay.py --cov=apps.operations.tasks.event_replay
```

### Test Scenarios Covered
- ✅ No pending events
- ✅ Redis unavailable
- ✅ Successful replay
- ✅ Retry on failure
- ✅ Max retries exceeded
- ✅ Cleanup old events

## Files Created/Modified

### Created Files
```
orchestrator/apps/operations/tasks/
├── __init__.py              # Package marker
├── event_replay.py          # Task implementations (2 tasks, ~150 lines)
└── README.md                # Detailed documentation

orchestrator/apps/operations/tests/
└── test_event_replay.py     # Unit tests (10 test cases)
```

### Modified Files
```
orchestrator/config/celery.py  # Added 2 beat_schedule entries
```

## Deployment Checklist

- [x] Code written and tested
- [x] Database migration exists for FailedEvent model
- [x] Celery Beat schedule configured
- [x] Error handling implemented
- [x] Monitoring ready
- [x] Documentation complete

## Ready for Merge

The implementation is complete and ready for:
1. Code review
2. Integration testing
3. Staging deployment
4. Production deployment

No additional migrations needed (FailedEvent model already exists).
