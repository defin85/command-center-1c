"""
Unit tests for Timeline API v2 endpoint.

Tests:
- POST /api/v2/operations/get-operation-timeline/ - Get operation timeline
"""

import pytest
from unittest.mock import patch
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.operations.models import BatchOperation
from apps.operations.services import TimelineResult


@pytest.fixture
def user():
    """Create test user."""
    return User.objects.create_user(username='testuser', password='testpass')


@pytest.fixture
def superuser():
    """Create superuser."""
    return User.objects.create_superuser(
        username='admin',
        password='adminpass',
        email='admin@test.com'
    )


@pytest.fixture
def authenticated_client(user):
    """Provide authenticated API client."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def superuser_client(superuser):
    """Provide authenticated superuser API client."""
    client = APIClient()
    client.force_authenticate(user=superuser)
    return client


@pytest.fixture
def sample_operation(user):
    """Create sample batch operation owned by user."""
    return BatchOperation.objects.create(
        id='test-operation-123',
        name='Test Operation',
        operation_type='lock_scheduled_jobs',
        target_entity='Infobase',
        status=BatchOperation.STATUS_COMPLETED,
        created_by=user.username
    )


@pytest.fixture
def other_user_operation():
    """Create operation owned by another user."""
    return BatchOperation.objects.create(
        id='other-operation-456',
        name='Other Operation',
        operation_type='unlock_scheduled_jobs',
        target_entity='Infobase',
        status=BatchOperation.STATUS_COMPLETED,
        created_by='otheruser'
    )


class TestGetOperationTimeline:
    """Test POST /api/v2/operations/get-operation-timeline/ endpoint."""

    @pytest.mark.django_db
    def test_requires_authentication(self, client):
        """Test endpoint requires authentication."""
        response = client.post(
            '/api/v2/operations/get-operation-timeline/',
            {'operation_id': 'test-123'},
            format='json'
        )
        assert response.status_code in [401, 403]

    @pytest.mark.django_db
    def test_requires_operation_id(self, authenticated_client):
        """Test endpoint requires operation_id parameter."""
        response = authenticated_client.post(
            '/api/v2/operations/get-operation-timeline/',
            {},
            format='json'
        )
        assert response.status_code == 400
        data = response.json()
        assert data['success'] is False
        assert 'error' in data
        assert data['error']['code'] == 'VALIDATION_ERROR'

    @pytest.mark.django_db
    def test_not_found_operation(self, authenticated_client):
        """Test 404 when operation doesn't exist."""
        response = authenticated_client.post(
            '/api/v2/operations/get-operation-timeline/',
            {'operation_id': 'nonexistent-operation'},
            format='json'
        )
        assert response.status_code == 404
        data = response.json()
        assert data['success'] is False
        assert data['error']['code'] == 'OPERATION_NOT_FOUND'

    @pytest.mark.django_db
    def test_forbidden_for_other_user_operation(self, authenticated_client, other_user_operation):
        """Test 404 when user doesn't own the operation (security: don't reveal existence)."""
        response = authenticated_client.post(
            '/api/v2/operations/get-operation-timeline/',
            {'operation_id': other_user_operation.id},
            format='json'
        )
        # Security hardening: return 404 instead of 403 to not reveal operation existence
        assert response.status_code == 404
        data = response.json()
        assert data['success'] is False
        assert data['error']['code'] == 'NOT_FOUND'

    @pytest.mark.django_db
    def test_superuser_can_access_any_operation(self, superuser_client, other_user_operation):
        """Test superuser can access any operation's timeline."""
        with patch('apps.operations.services.timeline_service.TimelineService._fetch_timeline_from_redis') as mock_fetch:
            mock_fetch.return_value = ([], 0, None)

            response = superuser_client.post(
                '/api/v2/operations/get-operation-timeline/',
                {'operation_id': other_user_operation.id},
                format='json'
            )
            assert response.status_code == 200

    @pytest.mark.django_db
    def test_success_with_owned_operation(self, authenticated_client, sample_operation):
        """Test successful timeline retrieval for owned operation."""
        mock_events = [
            {
                'timestamp': 1734567890123,
                'event': 'operation.started',
                'service': 'worker',
                'metadata': {}
            },
            {
                'timestamp': 1734567891456,
                'event': 'operation.completed',
                'service': 'worker',
                'metadata': {}
            }
        ]

        with patch('apps.operations.services.timeline_service.TimelineService._fetch_timeline_from_redis') as mock_fetch:
            mock_fetch.return_value = (mock_events, 2, 1333)

            response = authenticated_client.post(
                '/api/v2/operations/get-operation-timeline/',
                {'operation_id': sample_operation.id},
                format='json'
            )
            assert response.status_code == 200

            data = response.json()
            assert data['operation_id'] == sample_operation.id
            assert len(data['timeline']) == 2
            assert data['total_events'] == 2
            assert data['duration_ms'] == 1333

    @pytest.mark.django_db
    def test_custom_limit_and_offset(self, authenticated_client, sample_operation):
        """Test timeline with custom limit and offset."""
        with patch('apps.operations.services.timeline_service.TimelineService._fetch_timeline_from_redis') as mock_fetch:
            mock_fetch.return_value = ([], 0, None)

            response = authenticated_client.post(
                '/api/v2/operations/get-operation-timeline/',
                {
                    'operation_id': sample_operation.id,
                    'limit': 50,
                    'offset': 10
                },
                format='json'
            )
            assert response.status_code == 200

            # Verify fetch was called with correct params
            mock_fetch.assert_called_once_with(sample_operation.id, 50, 10)

    @pytest.mark.django_db
    def test_limit_validation_error_above_max(self, authenticated_client, sample_operation):
        """Test validation error when limit exceeds MAX_LIMIT (500)."""
        response = authenticated_client.post(
            '/api/v2/operations/get-operation-timeline/',
            {
                'operation_id': sample_operation.id,
                'limit': 1000  # Above max
            },
            format='json'
        )
        # Serializer validates max_value=500 and returns 400
        assert response.status_code == 400
        data = response.json()
        assert data['success'] is False
        assert data['error']['code'] == 'VALIDATION_ERROR'

    @pytest.mark.django_db
    def test_graceful_redis_failure(self, authenticated_client, sample_operation):
        """Test graceful handling when Redis is unavailable."""
        with patch('apps.operations.services.timeline_service.TimelineService._fetch_timeline_from_redis') as mock_fetch:
            # Simulate Redis connection error - service catches it and returns empty
            mock_fetch.side_effect = Exception("Redis connection refused")

            # Service should catch exception internally and return empty
            with patch.object(
                TimelineResult,
                '__init__',
                lambda self, **kwargs: None
            ):
                pass  # We test that the service doesn't crash

        # Actually test with the real service handling
        with patch('apps.operations.redis_client.redis_client.get_timeline') as mock_timeline:
            mock_timeline.side_effect = Exception("Redis connection refused")

            response = authenticated_client.post(
                '/api/v2/operations/get-operation-timeline/',
                {'operation_id': sample_operation.id},
                format='json'
            )
            # Should return 200 with empty timeline, not 500
            assert response.status_code == 200
            data = response.json()
            assert data['timeline'] == []
            assert data['total_events'] == 0


class TestTimelineService:
    """Unit tests for TimelineService class."""

    @pytest.mark.django_db
    def test_ownership_check_owner(self, user, sample_operation):
        """Test owner can access their operation."""
        from apps.operations.services import TimelineService

        with patch.object(TimelineService, '_fetch_timeline_from_redis', return_value=([], 0, None)):
            result = TimelineService.get_timeline(
                operation_id=sample_operation.id,
                user=user
            )
            assert result.success is True

    @pytest.mark.django_db
    def test_ownership_check_non_owner(self, user, other_user_operation):
        """Test non-owner cannot access operation (returns NOT_FOUND for security)."""
        from apps.operations.services import TimelineService
        from apps.operations.services.timeline_service import TimelineErrorCode

        result = TimelineService.get_timeline(
            operation_id=other_user_operation.id,
            user=user
        )
        assert result.success is False
        # Security hardening: error message says "not found" but error_code reveals real reason
        assert 'not found' in result.error.lower()
        assert result.error_code == TimelineErrorCode.FORBIDDEN

    @pytest.mark.django_db
    def test_ownership_check_superuser(self, superuser, other_user_operation):
        """Test superuser can access any operation."""
        from apps.operations.services import TimelineService

        with patch.object(TimelineService, '_fetch_timeline_from_redis', return_value=([], 0, None)):
            result = TimelineService.get_timeline(
                operation_id=other_user_operation.id,
                user=superuser
            )
            assert result.success is True

    @pytest.mark.django_db
    def test_internal_call_no_ownership_check(self, other_user_operation):
        """Test internal calls (user=None) skip ownership check."""
        from apps.operations.services import TimelineService

        with patch.object(TimelineService, '_fetch_timeline_from_redis', return_value=([], 0, None)):
            result = TimelineService.get_timeline(
                operation_id=other_user_operation.id,
                user=None  # Internal call
            )
            assert result.success is True

    @pytest.mark.django_db
    def test_nonexistent_operation(self, user):
        """Test error for nonexistent operation."""
        from apps.operations.services import TimelineService

        result = TimelineService.get_timeline(
            operation_id='nonexistent-op',
            user=user
        )
        assert result.success is False
        assert 'not found' in result.error.lower()
