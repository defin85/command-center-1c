"""
Unit tests for Timeline API endpoint.

Tests:
- GET /api/v2/internal/operations/{operation_id}/timeline
- Authentication requirements
- Operation existence validation
- Query parameters (limit, offset)
- Empty timeline handling
- Timeline with events
"""

import uuid
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

from apps.operations.models import BatchOperation


@override_settings(INTERNAL_API_TOKEN='test-internal-token')
class TimelineEndpointTests(TestCase):
    """Tests for timeline v2 endpoint."""

    def setUp(self):
        """Set up test client and data."""
        self.client = APIClient()
        self.client.credentials(HTTP_X_INTERNAL_TOKEN='test-internal-token')

        # Create test operation
        self.operation_id = 'test-op-' + str(uuid.uuid4())
        self.operation = BatchOperation.objects.create(
            id=self.operation_id,
            name='Test Batch Operation',
            operation_type=BatchOperation.TYPE_CREATE,
            target_entity='Document.ЗаказКлиента',
            status=BatchOperation.STATUS_COMPLETED,
        )

    def get_unauthenticated_client(self):
        """Return client without auth headers."""
        return APIClient()

    def test_get_timeline_operation_not_found(self):
        """Test 404 when operation does not exist."""
        non_existent_id = 'non-existent-' + str(uuid.uuid4())

        response = self.client.get(
            f'/api/v2/internal/operations/{non_existent_id}/timeline'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
        self.assertIn('not found', response.data['error'].lower())

    @patch('apps.operations.redis_client.redis_client')
    def test_get_timeline_empty(self, mock_redis_client):
        """Test timeline endpoint with empty timeline."""
        # Mock Redis returns empty timeline
        mock_redis_client.get_timeline.return_value = ([], 0)
        mock_redis_client.get_timeline_duration.return_value = None

        response = self.client.get(
            f'/api/v2/internal/operations/{self.operation_id}/timeline'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['operation_id'], self.operation_id)
        self.assertEqual(response.data['timeline'], [])
        self.assertEqual(response.data['total_events'], 0)
        self.assertIsNone(response.data['duration_ms'])

        # Verify Redis was called correctly
        mock_redis_client.get_timeline.assert_called_once_with(
            self.operation_id, 100, 0  # Default limit=100, offset=0
        )
        mock_redis_client.get_timeline_duration.assert_called_once_with(self.operation_id)

    @patch('apps.operations.redis_client.redis_client')
    def test_get_timeline_with_events(self, mock_redis_client):
        """Test timeline endpoint with events."""
        # Mock Redis returns events
        mock_events = [
            {
                "timestamp": 1734567890123,
                "event": "operation.started",
                "service": "worker",
                "metadata": {}
            },
            {
                "timestamp": 1734567890456,
                "event": "batch.created",
                "service": "worker",
                "metadata": {"batch_size": 100}
            },
            {
                "timestamp": 1734567891234,
                "event": "operation.completed",
                "service": "worker",
                "metadata": {"records_processed": 100}
            }
        ]
        mock_redis_client.get_timeline.return_value = (mock_events, 3)
        mock_redis_client.get_timeline_duration.return_value = 1111  # 1234 - 123 = 1111ms

        response = self.client.get(
            f'/api/v2/internal/operations/{self.operation_id}/timeline'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['operation_id'], self.operation_id)
        self.assertEqual(len(response.data['timeline']), 3)
        self.assertEqual(response.data['total_events'], 3)
        self.assertEqual(response.data['duration_ms'], 1111)

        # Verify event structure
        first_event = response.data['timeline'][0]
        self.assertEqual(first_event['timestamp'], 1734567890123)
        self.assertEqual(first_event['event'], 'operation.started')
        self.assertEqual(first_event['service'], 'worker')
        self.assertIsInstance(first_event['metadata'], dict)

        # Verify second event has metadata
        second_event = response.data['timeline'][1]
        self.assertEqual(second_event['metadata']['batch_size'], 100)

    @patch('apps.operations.redis_client.redis_client')
    def test_get_timeline_with_limit(self, mock_redis_client):
        """Test timeline endpoint respects limit parameter."""
        mock_redis_client.get_timeline.return_value = ([], 0)
        mock_redis_client.get_timeline_duration.return_value = None

        response = self.client.get(
            f'/api/v2/internal/operations/{self.operation_id}/timeline?limit=50'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify limit was passed to Redis
        mock_redis_client.get_timeline.assert_called_once_with(
            self.operation_id, 50, 0
        )

    @patch('apps.operations.redis_client.redis_client')
    def test_get_timeline_with_offset(self, mock_redis_client):
        """Test timeline endpoint respects offset parameter."""
        mock_redis_client.get_timeline.return_value = ([], 0)
        mock_redis_client.get_timeline_duration.return_value = None

        response = self.client.get(
            f'/api/v2/internal/operations/{self.operation_id}/timeline?offset=20'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify offset was passed to Redis
        mock_redis_client.get_timeline.assert_called_once_with(
            self.operation_id, 100, 20  # Default limit=100, offset=20
        )

    @patch('apps.operations.redis_client.redis_client')
    def test_get_timeline_with_limit_and_offset(self, mock_redis_client):
        """Test timeline endpoint with both limit and offset."""
        mock_redis_client.get_timeline.return_value = ([], 0)
        mock_redis_client.get_timeline_duration.return_value = None

        response = self.client.get(
            f'/api/v2/internal/operations/{self.operation_id}/timeline?limit=25&offset=10'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify both parameters were passed
        mock_redis_client.get_timeline.assert_called_once_with(
            self.operation_id, 25, 10
        )

    @patch('apps.operations.redis_client.redis_client')
    def test_get_timeline_invalid_limit_uses_default(self, mock_redis_client):
        """Test timeline endpoint uses default limit for invalid values."""
        mock_redis_client.get_timeline.return_value = ([], 0)
        mock_redis_client.get_timeline_duration.return_value = None

        # Invalid limit - should use default
        response = self.client.get(
            f'/api/v2/internal/operations/{self.operation_id}/timeline?limit=invalid'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should use default limit=100, offset=0
        mock_redis_client.get_timeline.assert_called_once_with(
            self.operation_id, 100, 0
        )

    @patch('apps.operations.redis_client.redis_client')
    def test_get_timeline_invalid_offset_uses_default(self, mock_redis_client):
        """Test timeline endpoint uses default offset for invalid values."""
        mock_redis_client.get_timeline.return_value = ([], 0)
        mock_redis_client.get_timeline_duration.return_value = None

        # Invalid offset - should use default
        response = self.client.get(
            f'/api/v2/internal/operations/{self.operation_id}/timeline?offset=invalid'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should use limit=100, offset=0
        mock_redis_client.get_timeline.assert_called_once_with(
            self.operation_id, 100, 0
        )

    @patch('apps.operations.redis_client.redis_client')
    def test_get_timeline_negative_offset_uses_zero(self, mock_redis_client):
        """Test timeline endpoint clamps negative offset to 0."""
        mock_redis_client.get_timeline.return_value = ([], 0)
        mock_redis_client.get_timeline_duration.return_value = None

        # Negative offset - should use 0
        response = self.client.get(
            f'/api/v2/internal/operations/{self.operation_id}/timeline?offset=-10'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # offset should be clamped to 0
        mock_redis_client.get_timeline.assert_called_once_with(
            self.operation_id, 100, 0
        )

    @patch('apps.operations.redis_client.redis_client')
    def test_get_timeline_limit_exceeds_max(self, mock_redis_client):
        """Test timeline endpoint clamps limit to maximum."""
        mock_redis_client.get_timeline.return_value = ([], 0)
        mock_redis_client.get_timeline_duration.return_value = None

        # Limit > 1000 - should use max 1000
        response = self.client.get(
            f'/api/v2/internal/operations/{self.operation_id}/timeline?limit=5000'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Limit should be clamped to 1000
        mock_redis_client.get_timeline.assert_called_once_with(
            self.operation_id, 1000, 0
        )

    @patch('apps.operations.redis_client.redis_client')
    def test_get_timeline_duration_none_when_empty(self, mock_redis_client):
        """Test duration is None when timeline is empty."""
        mock_redis_client.get_timeline.return_value = ([], 0)
        mock_redis_client.get_timeline_duration.return_value = None

        response = self.client.get(
            f'/api/v2/internal/operations/{self.operation_id}/timeline'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['duration_ms'])

    @patch('apps.operations.redis_client.redis_client')
    def test_get_timeline_duration_calculated(self, mock_redis_client):
        """Test duration is calculated from first to last event."""
        mock_events = [
            {"timestamp": 1000, "event": "start", "service": "worker", "metadata": {}},
            {"timestamp": 5000, "event": "end", "service": "worker", "metadata": {}},
        ]
        mock_redis_client.get_timeline.return_value = (mock_events, 2)
        mock_redis_client.get_timeline_duration.return_value = 4000

        response = self.client.get(
            f'/api/v2/internal/operations/{self.operation_id}/timeline'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['duration_ms'], 4000)

    def test_get_timeline_unauthorized(self):
        """Test timeline endpoint requires authentication."""
        client = self.get_unauthenticated_client()

        response = client.get(
            f'/api/v2/internal/operations/{self.operation_id}/timeline'
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_timeline_wrong_token(self):
        """Test timeline endpoint rejects wrong token."""
        client = APIClient()
        client.credentials(HTTP_X_INTERNAL_TOKEN='wrong-token')

        response = client.get(
            f'/api/v2/internal/operations/{self.operation_id}/timeline'
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('apps.operations.redis_client.redis_client')
    def test_get_timeline_response_structure(self, mock_redis_client):
        """Test timeline response has correct structure."""
        mock_events = [
            {
                "timestamp": 1000,
                "event": "test.event",
                "service": "test-service",
                "metadata": {"key": "value"}
            }
        ]
        mock_redis_client.get_timeline.return_value = (mock_events, 1)
        mock_redis_client.get_timeline_duration.return_value = 123

        response = self.client.get(
            f'/api/v2/internal/operations/{self.operation_id}/timeline'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify response structure
        self.assertIn('operation_id', response.data)
        self.assertIn('timeline', response.data)
        self.assertIn('total_events', response.data)
        self.assertIn('duration_ms', response.data)

        # Verify types
        self.assertIsInstance(response.data['operation_id'], str)
        self.assertIsInstance(response.data['timeline'], list)
        self.assertIsInstance(response.data['total_events'], int)
        self.assertIsInstance(response.data['duration_ms'], int)

    @patch('apps.operations.redis_client.redis_client')
    def test_get_timeline_with_large_dataset(self, mock_redis_client):
        """Test timeline endpoint with large number of events."""
        # Simulate 500 events, requesting first 100
        mock_events = [
            {
                "timestamp": 1000 + i,
                "event": f"event.{i}",
                "service": "worker",
                "metadata": {}
            }
            for i in range(100)
        ]
        mock_redis_client.get_timeline.return_value = (mock_events, 500)
        mock_redis_client.get_timeline_duration.return_value = 10000

        response = self.client.get(
            f'/api/v2/internal/operations/{self.operation_id}/timeline?limit=100&offset=0'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['timeline']), 100)
        self.assertEqual(response.data['total_events'], 500)  # Total in Redis

    @patch('apps.operations.redis_client.redis_client')
    def test_get_timeline_pagination_second_page(self, mock_redis_client):
        """Test timeline endpoint pagination for second page."""
        # Simulate second page (offset=100, limit=100)
        mock_events = [
            {
                "timestamp": 1100 + i,
                "event": f"event.{100 + i}",
                "service": "worker",
                "metadata": {}
            }
            for i in range(50)  # Only 50 events on page 2
        ]
        mock_redis_client.get_timeline.return_value = (mock_events, 150)
        mock_redis_client.get_timeline_duration.return_value = 5000

        response = self.client.get(
            f'/api/v2/internal/operations/{self.operation_id}/timeline?limit=100&offset=100'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['timeline']), 50)  # Actual returned events
        self.assertEqual(response.data['total_events'], 150)  # Total events

        # Verify correct offset was used
        mock_redis_client.get_timeline.assert_called_once_with(
            self.operation_id, 100, 100
        )

    @patch('apps.operations.redis_client.redis_client')
    def test_get_timeline_with_complex_metadata(self, mock_redis_client):
        """Test timeline handles complex nested metadata."""
        mock_events = [
            {
                "timestamp": 1000,
                "event": "complex.event",
                "service": "worker",
                "metadata": {
                    "level1": {
                        "level2": {
                            "level3": ["array", "of", "values"],
                            "number": 42
                        }
                    },
                    "list": [1, 2, 3],
                    "boolean": True,
                    "null": None
                }
            }
        ]
        mock_redis_client.get_timeline.return_value = (mock_events, 1)
        mock_redis_client.get_timeline_duration.return_value = 100

        response = self.client.get(
            f'/api/v2/internal/operations/{self.operation_id}/timeline'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event = response.data['timeline'][0]

        # Verify complex metadata is preserved
        self.assertEqual(event['metadata']['level1']['level2']['number'], 42)
        self.assertEqual(event['metadata']['level1']['level2']['level3'], ["array", "of", "values"])
        self.assertEqual(event['metadata']['list'], [1, 2, 3])
        self.assertTrue(event['metadata']['boolean'])
        self.assertIsNone(event['metadata']['null'])
