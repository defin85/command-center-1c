"""FailedEvent model - stores events/messages requiring operator attention.

Originally introduced as a PostgreSQL fallback for events that failed to publish to Redis.
It is also used to persist poison / permanently unprocessable stream messages so they
can be inspected in the admin UI without creating infinite Redis pending growth.
"""

from django.db import models


class FailedEvent(models.Model):
    """
    Stores events that require manual inspection or replay.

    Primary use-case: events that failed to publish to Redis (publish_failure),
    stored with retry logic and replayed by Go services.

    Secondary use-case: poison stream messages acknowledged by EventSubscriber
    (poison_message), stored for manual inspection and excluded from replay loop.

    Events are stored with retry logic and can be replayed later.
    """

    KIND_PUBLISH_FAILURE = "publish_failure"
    KIND_POISON_MESSAGE = "poison_message"

    KIND_CHOICES = [
        (KIND_PUBLISH_FAILURE, "Publish failure"),
        (KIND_POISON_MESSAGE, "Poison message"),
    ]

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
    kind = models.CharField(max_length=32, choices=KIND_CHOICES, default=KIND_PUBLISH_FAILURE)
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
