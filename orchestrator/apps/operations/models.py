from django.db import models
from django.utils import timezone


class BatchOperation(models.Model):
    """Represents a batch of operations to be executed across multiple databases."""

    STATUS_PENDING = 'pending'
    STATUS_QUEUED = 'queued'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_QUEUED, 'Queued'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    TYPE_CREATE = 'create'
    TYPE_UPDATE = 'update'
    TYPE_DELETE = 'delete'
    TYPE_QUERY = 'query'
    TYPE_INSTALL_EXTENSION = 'install_extension'

    TYPE_CHOICES = [
        (TYPE_CREATE, 'Create'),
        (TYPE_UPDATE, 'Update'),
        (TYPE_DELETE, 'Delete'),
        (TYPE_QUERY, 'Query'),
        (TYPE_INSTALL_EXTENSION, 'Install Extension'),
    ]

    # Identity
    id = models.CharField(max_length=64, primary_key=True)
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)

    # Operation Details
    operation_type = models.CharField(max_length=20, choices=TYPE_CHOICES, db_index=True)
    target_entity = models.CharField(max_length=255, help_text="1C entity name (e.g., Справочник_Пользователи)")

    # Target databases (M2M)
    target_databases = models.ManyToManyField(
        'databases.Database',
        related_name='batch_operations',
        help_text="Databases to execute operation on"
    )

    # Template reference (optional)
    template = models.ForeignKey(
        'templates.OperationTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='batch_operations'
    )

    # Payload & Configuration
    payload = models.JSONField(default=dict, help_text="Operation payload/parameters")
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Execution configuration (timeout, retries, etc.)"
    )

    # Status & Progress
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    progress = models.IntegerField(default=0, help_text="Progress percentage (0-100)")

    # Statistics
    total_tasks = models.IntegerField(default=0, help_text="Total number of tasks")
    completed_tasks = models.IntegerField(default=0, help_text="Number of completed tasks")
    failed_tasks = models.IntegerField(default=0, help_text="Number of failed tasks")
    retry_tasks = models.IntegerField(default=0, help_text="Number of tasks in retry")

    # Execution Tracking
    celery_task_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Creator & Metadata
    created_by = models.CharField(max_length=255, blank=True, help_text="User who created operation")
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional metadata")

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'batch_operations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['operation_type', 'status']),
            models.Index(fields=['celery_task_id']),
        ]
        verbose_name = 'Batch Operation'
        verbose_name_plural = 'Batch Operations'

    def __str__(self):
        return f"Batch {self.name} ({self.status})"

    def update_progress(self):
        """
        Update progress and statistics based on related tasks.
        Should be called after task status changes.
        """
        tasks = self.tasks.all()
        self.total_tasks = tasks.count()
        self.completed_tasks = tasks.filter(status=Task.STATUS_COMPLETED).count()
        self.failed_tasks = tasks.filter(status=Task.STATUS_FAILED).count()
        self.retry_tasks = tasks.filter(status=Task.STATUS_RETRY).count()

        if self.total_tasks > 0:
            self.progress = int((self.completed_tasks / self.total_tasks) * 100)
        else:
            self.progress = 0

        # Update batch status based on task statuses
        if self.completed_tasks == self.total_tasks and self.total_tasks > 0:
            self.status = self.STATUS_COMPLETED
            if not self.completed_at:
                self.completed_at = timezone.now()
        elif self.failed_tasks > 0 and (self.completed_tasks + self.failed_tasks) == self.total_tasks:
            self.status = self.STATUS_FAILED
            if not self.completed_at:
                self.completed_at = timezone.now()
        elif tasks.filter(status=Task.STATUS_PROCESSING).exists():
            self.status = self.STATUS_PROCESSING

        self.save(update_fields=[
            'total_tasks',
            'completed_tasks',
            'failed_tasks',
            'retry_tasks',
            'progress',
            'status',
            'completed_at',
            'updated_at'
        ])

    @property
    def duration_seconds(self):
        """Calculate operation duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (timezone.now() - self.started_at).total_seconds()
        return None

    @property
    def success_rate(self):
        """Calculate success rate percentage."""
        if self.total_tasks == 0:
            return None
        return (self.completed_tasks / self.total_tasks) * 100


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
        BatchOperation,
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
