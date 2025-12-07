"""FailedEvent model - stores events that failed to publish to Redis."""

from django.db import models


class FailedEvent(models.Model):
    """
    Stores events that failed to publish to Redis.
    Used for graceful degradation when Redis is unavailable.

    Events are stored with retry logic and can be replayed later.
    """

    STATUS_PENDING = 'pending'
    STATUS_REPLAYED = 'replayed'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_REPLAYED, 'Replayed'),
        (STATUS_FAILED, 'Permanently Failed'),
    ]

    id = models.AutoField(primary_key=True)

    # Event data
    channel = models.CharField(max_length=255, db_index=True)
    event_type = models.CharField(max_length=100)
    correlation_id = models.CharField(max_length=64, db_index=True)
    payload = models.JSONField()

    # Metadata
    source_service = models.CharField(max_length=50)
    original_timestamp = models.DateTimeField()

    # Replay tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=5)
    last_error = models.TextField(blank=True)
    replayed_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'failed_events'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['correlation_id']),
            models.Index(fields=['channel', 'status']),
        ]
        verbose_name = 'Failed Event'
        verbose_name_plural = 'Failed Events'

    def __str__(self):
        return f"{self.event_type} [{self.status}] - {self.correlation_id}"
