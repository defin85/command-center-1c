"""
TimelineService - Service for operation timeline retrieval.

Provides timeline data from Redis with ownership validation for public endpoints.
Gracefully handles Redis unavailability.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from django.contrib.auth.models import AbstractUser

from ..models import BatchOperation

logger = logging.getLogger(__name__)


# Constants
MAX_LIMIT = 500  # Maximum events per request
DEFAULT_LIMIT = 100


class TimelineErrorCode:
    """Error codes for timeline operations."""
    NOT_FOUND = "NOT_FOUND"
    FORBIDDEN = "FORBIDDEN"  # Returned as NOT_FOUND to prevent information disclosure
    REDIS_ERROR = "REDIS_ERROR"


@dataclass
class TimelineResult:
    """Result of timeline retrieval."""
    success: bool
    operation_id: str
    timeline: list
    total_events: int
    duration_ms: Optional[int]
    error: Optional[str] = None
    error_code: Optional[str] = None


class TimelineService:
    """
    Service for retrieving operation execution timelines.

    Features:
    - Ownership validation for public endpoints (user must own operation)
    - Graceful handling of Redis unavailability
    - Limit capping to prevent excessive data retrieval
    """

    @classmethod
    def get_timeline(
        cls,
        operation_id: str,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
        user: Optional[AbstractUser] = None
    ) -> TimelineResult:
        """
        Get operation timeline from Redis.

        Args:
            operation_id: Operation ID (BatchOperation.id)
            limit: Maximum events to return (capped at MAX_LIMIT)
            offset: Starting offset for pagination
            user: If provided, validates user owns the operation (public endpoint).
                  If None, skips ownership check (internal service-to-service).

        Returns:
            TimelineResult with timeline events and metadata

        Note:
            - When user is provided, checks that operation.created_by == user.username
              or user is superuser
            - When Redis is unavailable, returns empty timeline (not 500 error)
        """
        # Validate and cap parameters
        limit = min(max(1, limit), MAX_LIMIT)
        offset = max(0, offset)

        # Check operation exists
        try:
            operation = BatchOperation.objects.get(id=operation_id)
        except BatchOperation.DoesNotExist:
            return TimelineResult(
                success=False,
                operation_id=operation_id,
                timeline=[],
                total_events=0,
                duration_ms=None,
                error="Operation not found",
                error_code=TimelineErrorCode.NOT_FOUND
            )

        # Ownership validation for public endpoints
        if user is not None:
            if not cls._check_ownership(operation, user):
                # Security: Return NOT_FOUND instead of FORBIDDEN to prevent information disclosure
                # Log actual reason for audit
                logger.warning(
                    f"User {user.username} attempted to access timeline for operation {operation_id} "
                    f"owned by {operation.created_by}",
                    extra={
                        'user': user.username,
                        'operation_id': operation_id,
                        'operation_owner': operation.created_by,
                        'reason': 'forbidden'
                    }
                )
                return TimelineResult(
                    success=False,
                    operation_id=operation_id,
                    timeline=[],
                    total_events=0,
                    duration_ms=None,
                    error="Operation not found",  # Same message as NOT_FOUND for security
                    error_code=TimelineErrorCode.FORBIDDEN
                )

        # Get timeline from Redis (with graceful degradation)
        events, total, duration_ms = cls._fetch_timeline_from_redis(
            operation_id, limit, offset
        )

        return TimelineResult(
            success=True,
            operation_id=operation_id,
            timeline=events,
            total_events=total,
            duration_ms=duration_ms
        )

    @staticmethod
    def _check_ownership(operation: BatchOperation, user: AbstractUser) -> bool:
        """
        Check if user has access to the operation.

        Args:
            operation: BatchOperation instance
            user: User requesting access

        Returns:
            True if user owns the operation or is superuser
        """
        # Superusers can access any operation
        if user.is_superuser:
            return True

        # Check ownership by username
        return operation.created_by == user.username

    @staticmethod
    def _fetch_timeline_from_redis(
        operation_id: str,
        limit: int,
        offset: int
    ) -> tuple[list, int, Optional[int]]:
        """
        Fetch timeline data from Redis with graceful error handling.

        Args:
            operation_id: Operation ID
            limit: Max events to return
            offset: Starting offset

        Returns:
            (events_list, total_count, duration_ms)
            Returns ([], 0, None) on Redis errors
        """
        from ..redis_client import redis_client

        try:
            # Get timeline events
            events, total = redis_client.get_timeline(operation_id, limit, offset)

            # Get duration (first to last event)
            duration_ms = redis_client.get_timeline_duration(operation_id)

            return events, total, duration_ms

        except Exception as e:
            # Log error but don't fail the request
            logger.warning(
                f"Failed to fetch timeline from Redis for operation {operation_id}: {e}",
                exc_info=True
            )
            return [], 0, None
