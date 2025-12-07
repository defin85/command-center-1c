"""Task model - represents a single task within a batch operation."""

from django.db import models
from django.utils import timezone


class Task(models.Model):
    """
    Represents a single task within a batch operation.
    One task = one operation on one database.
    """

    STATUS_PENDING = 'pending'
    STATUS_QUEUED = 'queued'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_RETRY = 'retry'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_QUEUED, 'Queued'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_RETRY, 'Retry'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    # Identity
    id = models.CharField(max_length=64, primary_key=True)

    # Relations
    batch_operation = models.ForeignKey(
        'operations.BatchOperation',
        on_delete=models.CASCADE,
        related_name='tasks'
    )
    database = models.ForeignKey(
        'databases.Database',
        on_delete=models.CASCADE,
        related_name='tasks'
    )

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)

    # Execution Tracking
    celery_task_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    worker_id = models.CharField(max_length=255, blank=True, help_text="Worker that processed this task")

    # Result
    result = models.JSONField(null=True, blank=True, help_text="Task result data")
    error_message = models.TextField(blank=True, help_text="Error message if failed")
    error_code = models.CharField(max_length=50, blank=True, help_text="Error code if failed")

    # Retry Logic
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    next_retry_at = models.DateTimeField(null=True, blank=True)

    # Performance Metrics
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True, help_text="Task duration in seconds")

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tasks'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['batch_operation', 'status']),
            models.Index(fields=['database', 'status']),
            models.Index(fields=['status', 'next_retry_at']),
            models.Index(fields=['celery_task_id']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Task'
        verbose_name_plural = 'Tasks'

    def __str__(self):
        return f"Task {self.id} on {self.database.name} ({self.status})"

    def mark_started(self, worker_id: str = None):
        """Mark task as started."""
        self.status = self.STATUS_PROCESSING
        self.started_at = timezone.now()
        if worker_id:
            self.worker_id = worker_id
        self.save(update_fields=['status', 'started_at', 'worker_id', 'updated_at'])

    def mark_completed(self, result: dict = None):
        """Mark task as completed."""
        self.status = self.STATUS_COMPLETED
        self.completed_at = timezone.now()
        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        if result:
            self.result = result
        self.save(update_fields=['status', 'completed_at', 'duration_seconds', 'result', 'updated_at'])

        # Update batch operation progress
        self.batch_operation.update_progress()

    def mark_failed(self, error_message: str, error_code: str = None, should_retry: bool = True):
        """Mark task as failed and schedule retry if needed."""
        self.error_message = error_message
        if error_code:
            self.error_code = error_code
        self.completed_at = timezone.now()
        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()

        # Determine if we should retry
        if should_retry and self.retry_count < self.max_retries:
            self.status = self.STATUS_RETRY
            self.retry_count += 1
            # Exponential backoff: 2^retry_count minutes
            retry_delay_minutes = 2 ** self.retry_count
            self.next_retry_at = timezone.now() + timezone.timedelta(minutes=retry_delay_minutes)
        else:
            self.status = self.STATUS_FAILED

        self.save(update_fields=[
            'status',
            'error_message',
            'error_code',
            'completed_at',
            'duration_seconds',
            'retry_count',
            'next_retry_at',
            'updated_at'
        ])

        # Update batch operation progress
        self.batch_operation.update_progress()

    @property
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return (
            self.status == self.STATUS_RETRY and
            self.retry_count < self.max_retries and
            self.next_retry_at and
            self.next_retry_at <= timezone.now()
        )

    @property
    def is_terminal(self) -> bool:
        """Check if task is in terminal state (completed, failed, cancelled)."""
        return self.status in [self.STATUS_COMPLETED, self.STATUS_FAILED, self.STATUS_CANCELLED]
