"""Tests for event replay Celery task."""

from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch, MagicMock
import json

from apps.operations.models import FailedEvent
from apps.operations.tasks.event_replay import replay_failed_events, cleanup_old_replayed_events


class EventReplayTaskTests(TestCase):
    """Test cases for event replay functionality."""

    def setUp(self):
        """Set up test data."""
        self.base_time = timezone.now()

    def test_no_pending_events(self):
        """Test task returns zero when no pending events exist."""
        result = replay_failed_events()
        self.assertEqual(result['status'], 'no_pending_events')
        self.assertEqual(result['replayed'], 0)
        self.assertEqual(result['failed'], 0)

    @patch('apps.operations.tasks.event_replay.redis.Redis.from_url')
    def test_redis_unavailable(self, mock_redis):
        """Test task returns error when Redis is unavailable."""
        # Create a test event
        FailedEvent.objects.create(
            channel='events:test',
            event_type='test.event',
            correlation_id='corr-123',
            payload={'test': 'data'},
            source_service='test',
            original_timestamp=self.base_time,
        )

        # Mock Redis connection error
        mock_redis.side_effect = Exception("Connection refused")

        result = replay_failed_events()
        self.assertEqual(result['status'], 'redis_error')
        self.assertIn('error', result)

    @patch('apps.operations.tasks.event_replay.redis.Redis.from_url')
    def test_successful_replay(self, mock_redis):
        """Test successful event replay."""
        # Create test events
        event1 = FailedEvent.objects.create(
            channel='events:test',
            event_type='test.event.1',
            correlation_id='corr-123',
            payload={'test': 'data1'},
            source_service='test',
            original_timestamp=self.base_time,
            status=FailedEvent.STATUS_PENDING,
            retry_count=0,
        )

        event2 = FailedEvent.objects.create(
            channel='events:test',
            event_type='test.event.2',
            correlation_id='corr-124',
            payload={'test': 'data2'},
            source_service='test',
            original_timestamp=self.base_time,
            status=FailedEvent.STATUS_PENDING,
            retry_count=1,
        )

        # Mock Redis client
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        result = replay_failed_events()

        # Verify results
        self.assertEqual(result['replayed'], 2)
        self.assertEqual(result['failed'], 0)

        # Verify events were marked as replayed
        event1.refresh_from_db()
        event2.refresh_from_db()
        self.assertEqual(event1.status, FailedEvent.STATUS_REPLAYED)
        self.assertEqual(event2.status, FailedEvent.STATUS_REPLAYED)
        self.assertIsNotNone(event1.replayed_at)
        self.assertIsNotNone(event2.replayed_at)

        # Verify Redis XADD was called
        self.assertEqual(mock_client.xadd.call_count, 2)

    @patch('apps.operations.tasks.event_replay.redis.Redis.from_url')
    def test_retry_on_failure(self, mock_redis):
        """Test event retry on failure."""
        # Create a test event
        event = FailedEvent.objects.create(
            channel='events:test',
            event_type='test.event',
            correlation_id='corr-123',
            payload={'test': 'data'},
            source_service='test',
            original_timestamp=self.base_time,
            status=FailedEvent.STATUS_PENDING,
            retry_count=0,
            max_retries=5,
        )

        # Mock Redis client to raise exception
        mock_client = MagicMock()
        mock_client.xadd.side_effect = Exception("Write failed")
        mock_redis.return_value = mock_client

        result = replay_failed_events()

        # Verify failure was recorded
        self.assertEqual(result['replayed'], 0)
        self.assertEqual(result['failed'], 1)

        # Verify event retry count increased
        event.refresh_from_db()
        self.assertEqual(event.retry_count, 1)
        self.assertEqual(event.status, FailedEvent.STATUS_PENDING)
        self.assertEqual(event.last_error, "Write failed")

    @patch('apps.operations.tasks.event_replay.redis.Redis.from_url')
    def test_max_retries_exceeded(self, mock_redis):
        """Test event marked as failed when max retries exceeded."""
        # Create a test event that has already exceeded max retries
        event = FailedEvent.objects.create(
            channel='events:test',
            event_type='test.event',
            correlation_id='corr-123',
            payload={'test': 'data'},
            source_service='test',
            original_timestamp=self.base_time,
            status=FailedEvent.STATUS_PENDING,
            retry_count=4,  # Next attempt will be 5th
            max_retries=5,
        )

        # Mock Redis client to raise exception
        mock_client = MagicMock()
        mock_client.xadd.side_effect = Exception("Write failed")
        mock_redis.return_value = mock_client

        result = replay_failed_events()

        # Verify event was marked as permanently failed
        event.refresh_from_db()
        self.assertEqual(event.status, FailedEvent.STATUS_FAILED)
        self.assertEqual(event.retry_count, 5)


class CleanupTaskTests(TestCase):
    """Test cases for cleanup task."""

    def setUp(self):
        """Set up test data."""
        self.base_time = timezone.now()

    def test_cleanup_old_replayed_events(self):
        """Test cleanup removes events older than specified days."""
        # Create recent replayed event (should not be deleted)
        recent_event = FailedEvent.objects.create(
            channel='events:test',
            event_type='test.recent',
            correlation_id='corr-recent',
            payload={'test': 'data'},
            source_service='test',
            original_timestamp=self.base_time,
            status=FailedEvent.STATUS_REPLAYED,
            replayed_at=self.base_time - timezone.timedelta(days=2),
        )

        # Create old replayed event (should be deleted)
        old_event = FailedEvent.objects.create(
            channel='events:test',
            event_type='test.old',
            correlation_id='corr-old',
            payload={'test': 'data'},
            source_service='test',
            original_timestamp=self.base_time - timezone.timedelta(days=10),
            status=FailedEvent.STATUS_REPLAYED,
            replayed_at=self.base_time - timezone.timedelta(days=10),
        )

        # Create pending event (should not be deleted)
        pending_event = FailedEvent.objects.create(
            channel='events:test',
            event_type='test.pending',
            correlation_id='corr-pending',
            payload={'test': 'data'},
            source_service='test',
            original_timestamp=self.base_time - timezone.timedelta(days=10),
            status=FailedEvent.STATUS_PENDING,
        )

        result = cleanup_old_replayed_events(days=7)

        # Verify cleanup result
        self.assertEqual(result['deleted'], 1)

        # Verify events
        self.assertTrue(FailedEvent.objects.filter(id=recent_event.id).exists())
        self.assertFalse(FailedEvent.objects.filter(id=old_event.id).exists())
        self.assertTrue(FailedEvent.objects.filter(id=pending_event.id).exists())
