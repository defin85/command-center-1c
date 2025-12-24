"""
Unit tests for RedisClient timeline operations.

Tests:
- get_timeline() - pagination, empty timeline, invalid JSON handling
- get_timeline_duration() - empty timeline, single event, multiple events
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from apps.operations.redis_client import RedisClient


class TestRedisClientTimeline:
    """Test RedisClient timeline operations."""

    @pytest.fixture
    def redis_client(self):
        """Provide RedisClient instance with mocked Redis."""
        with patch('apps.operations.redis_client.redis.Redis') as mock_redis_class:
            mock_client = MagicMock()
            mock_redis_class.return_value = mock_client

            client = RedisClient()
            client.client = mock_client
            yield client

    def test_get_timeline_empty(self, redis_client):
        """Test get_timeline with non-existent key returns empty list."""
        # Mock Redis ZCARD returns 0
        redis_client.client.zcard.return_value = 0
        # Mock Redis ZRANGE returns empty list
        redis_client.client.zrange.return_value = []

        events, total = redis_client.get_timeline('op-123')

        assert events == []
        assert total == 0
        redis_client.client.zcard.assert_called_once_with('operation:timeline:op-123')
        redis_client.client.zrange.assert_called_once_with(
            'operation:timeline:op-123', 0, 99, withscores=True
        )

    def test_get_timeline_with_events(self, redis_client):
        """Test get_timeline returns events in correct order."""
        # Mock Redis ZCARD returns total count
        redis_client.client.zcard.return_value = 3

        # Mock Redis ZRANGE returns events with scores (timestamp is score)
        mock_events = [
            (json.dumps({"event": "operation.started", "service": "worker", "metadata": {}, "trace_id": "trace-1"}), 1734567890123),
            (json.dumps({"event": "batch.created", "service": "worker", "metadata": {"batch_size": 100}, "workflow_execution_id": "wf-1"}), 1734567890456),
            (json.dumps({"event": "operation.completed", "service": "worker", "metadata": {"node_id": "node-1"}}), 1734567891234),
        ]
        redis_client.client.zrange.return_value = mock_events

        events, total = redis_client.get_timeline('op-456', limit=100, offset=0)

        assert total == 3
        assert len(events) == 3
        assert events[0]['timestamp'] == 1734567890123
        assert events[0]['event'] == 'operation.started'
        assert events[0]['service'] == 'worker'
        assert events[0]['metadata'] == {}
        assert events[0]['trace_id'] == "trace-1"

        assert events[1]['timestamp'] == 1734567890456
        assert events[1]['event'] == 'batch.created'
        assert events[1]['metadata'] == {"batch_size": 100}
        assert events[1]['workflow_execution_id'] == "wf-1"

        assert events[2]['timestamp'] == 1734567891234
        assert events[2]['event'] == 'operation.completed'
        assert events[2]['node_id'] == "node-1"

    def test_get_timeline_pagination_limit(self, redis_client):
        """Test get_timeline respects limit parameter."""
        redis_client.client.zcard.return_value = 10
        redis_client.client.zrange.return_value = []

        events, total = redis_client.get_timeline('op-789', limit=5, offset=0)

        # Should request range [0, 4] (5 items)
        redis_client.client.zrange.assert_called_once_with(
            'operation:timeline:op-789', 0, 4, withscores=True
        )
        assert total == 10

    def test_get_timeline_pagination_offset(self, redis_client):
        """Test get_timeline respects offset parameter."""
        redis_client.client.zcard.return_value = 20
        redis_client.client.zrange.return_value = []

        events, total = redis_client.get_timeline('op-abc', limit=10, offset=10)

        # Should request range [10, 19] (10 items starting from index 10)
        redis_client.client.zrange.assert_called_once_with(
            'operation:timeline:op-abc', 10, 19, withscores=True
        )
        assert total == 20

    def test_get_timeline_invalid_json_skipped(self, redis_client):
        """Test get_timeline skips events with invalid JSON."""
        redis_client.client.zcard.return_value = 3

        # Mix of valid and invalid JSON
        mock_events = [
            (json.dumps({"event": "valid.event1", "service": "worker", "metadata": {}}), 1000),
            ("invalid json {", 2000),  # Invalid JSON - should be skipped
            (json.dumps({"event": "valid.event2", "service": "orchestrator", "metadata": {}}), 3000),
        ]
        redis_client.client.zrange.return_value = mock_events

        events, total = redis_client.get_timeline('op-invalid')

        # Should skip invalid JSON entry
        assert len(events) == 2
        assert events[0]['event'] == 'valid.event1'
        assert events[1]['event'] == 'valid.event2'
        assert total == 3  # Total still reflects Redis ZCARD

    def test_get_timeline_custom_limit_offset(self, redis_client):
        """Test get_timeline with custom limit and offset."""
        redis_client.client.zcard.return_value = 50
        redis_client.client.zrange.return_value = [
            (json.dumps({"event": "page2.event1", "service": "worker", "metadata": {}}), 5000),
            (json.dumps({"event": "page2.event2", "service": "worker", "metadata": {}}), 6000),
        ]

        events, total = redis_client.get_timeline('op-pagination', limit=2, offset=20)

        assert len(events) == 2
        assert total == 50
        # Should request range [20, 21] (2 items starting from index 20)
        redis_client.client.zrange.assert_called_once_with(
            'operation:timeline:op-pagination', 20, 21, withscores=True
        )

    def test_get_timeline_duration_empty(self, redis_client):
        """Test get_timeline_duration with no events returns None."""
        # Mock Redis ZRANGE returns empty list
        redis_client.client.zrange.return_value = []

        duration = redis_client.get_timeline_duration('op-empty')

        assert duration is None
        # Should call ZRANGE twice (first and last)
        assert redis_client.client.zrange.call_count == 1

    def test_get_timeline_duration_single_event(self, redis_client):
        """Test get_timeline_duration with single event returns None."""
        # Mock first event
        mock_event = [
            ('{"event": "single"}', 1000.0)
        ]
        redis_client.client.zrange.side_effect = [
            mock_event,  # First call (first event)
            mock_event,  # Second call (last event) - same as first
        ]

        duration = redis_client.get_timeline_duration('op-single')

        assert duration is None
        # Should call ZRANGE twice (first and last)
        assert redis_client.client.zrange.call_count == 2

    def test_get_timeline_duration_multiple_events(self, redis_client):
        """Test get_timeline_duration calculates difference correctly."""
        # Mock first and last events
        first_event = [('{"event": "start"}', 1734567890000.0)]
        last_event = [('{"event": "end"}', 1734567891234.0)]

        redis_client.client.zrange.side_effect = [
            first_event,  # First call (first event)
            last_event,   # Second call (last event)
        ]

        duration = redis_client.get_timeline_duration('op-duration')

        # Duration should be 1234 milliseconds
        assert duration == 1234

        # Verify calls
        calls = redis_client.client.zrange.call_args_list
        assert len(calls) == 2
        # First event: ZRANGE key 0 0 withscores=True
        assert calls[0][0] == ('operation:timeline:op-duration', 0, 0)
        # Last event: ZRANGE key -1 -1 withscores=True
        assert calls[1][0] == ('operation:timeline:op-duration', -1, -1)

    def test_get_timeline_duration_large_duration(self, redis_client):
        """Test get_timeline_duration with large time difference."""
        first_event = [('{"event": "start"}', 1000000000000.0)]
        last_event = [('{"event": "end"}', 1000086400000.0)]  # +86400000ms = +24 hours

        redis_client.client.zrange.side_effect = [first_event, last_event]

        duration = redis_client.get_timeline_duration('op-long')

        # Should be 86400000ms (24 hours)
        assert duration == 86400000

    def test_get_timeline_duration_first_empty_returns_none(self, redis_client):
        """Test get_timeline_duration returns None when first ZRANGE is empty."""
        redis_client.client.zrange.return_value = []

        duration = redis_client.get_timeline_duration('op-no-first')

        assert duration is None
        # Should only call ZRANGE once (stops after first is empty)
        assert redis_client.client.zrange.call_count == 1

    def test_get_timeline_key_format(self, redis_client):
        """Test that timeline key uses correct prefix."""
        redis_client.client.zcard.return_value = 0
        redis_client.client.zrange.return_value = []

        redis_client.get_timeline('my-operation-id')

        # Verify key format: operation:timeline:operation_id
        redis_client.client.zcard.assert_called_once_with('operation:timeline:my-operation-id')
        redis_client.client.zrange.assert_called_once()
        args = redis_client.client.zrange.call_args[0]
        assert args[0] == 'operation:timeline:my-operation-id'

    def test_get_timeline_default_parameters(self, redis_client):
        """Test get_timeline uses correct default parameters."""
        redis_client.client.zcard.return_value = 0
        redis_client.client.zrange.return_value = []

        # Call without limit/offset - should use defaults
        redis_client.get_timeline('op-defaults')

        # Default: limit=100, offset=0 -> range [0, 99]
        redis_client.client.zrange.assert_called_once_with(
            'operation:timeline:op-defaults', 0, 99, withscores=True
        )

    def test_get_timeline_events_structure(self, redis_client):
        """Test that returned events have correct structure."""
        redis_client.client.zcard.return_value = 1
        redis_client.client.zrange.return_value = [
            (json.dumps({
                "event": "test.event",
                "service": "test-service",
                "metadata": {"key": "value", "nested": {"data": 123}}
            }), 9999.0)
        ]

        events, _ = redis_client.get_timeline('op-structure')

        assert len(events) == 1
        event = events[0]

        # Verify structure
        assert 'timestamp' in event
        assert 'event' in event
        assert 'service' in event
        assert 'metadata' in event

        # Verify types
        assert isinstance(event['timestamp'], int)
        assert isinstance(event['event'], str)
        assert isinstance(event['service'], str)
        assert isinstance(event['metadata'], dict)

        # Verify values
        assert event['timestamp'] == 9999
        assert event['event'] == 'test.event'
        assert event['service'] == 'test-service'
        assert event['metadata']['key'] == 'value'
        assert event['metadata']['nested']['data'] == 123
