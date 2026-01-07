"""BatchOperation model - represents a batch of operations across databases."""

from typing import Optional

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

    # OData operation types
    TYPE_CREATE = 'create'
    TYPE_UPDATE = 'update'
    TYPE_DELETE = 'delete'
    TYPE_QUERY = 'query'

    # RAS operation types
    TYPE_LOCK_SCHEDULED_JOBS = 'lock_scheduled_jobs'
    TYPE_UNLOCK_SCHEDULED_JOBS = 'unlock_scheduled_jobs'
    TYPE_TERMINATE_SESSIONS = 'terminate_sessions'
    TYPE_BLOCK_SESSIONS = 'block_sessions'
    TYPE_UNBLOCK_SESSIONS = 'unblock_sessions'

    # Cluster operation types
    TYPE_SYNC_CLUSTER = 'sync_cluster'
    TYPE_DISCOVER_CLUSTERS = 'discover_clusters'
    TYPE_HEALTH_CHECK = 'health_check'

    # IBCMD operation types
    TYPE_IBCMD_BACKUP = 'ibcmd_backup'
    TYPE_IBCMD_RESTORE = 'ibcmd_restore'
    TYPE_IBCMD_REPLICATE = 'ibcmd_replicate'
    TYPE_IBCMD_CREATE = 'ibcmd_create'
    TYPE_IBCMD_LOAD_CFG = 'ibcmd_load_cfg'
    TYPE_IBCMD_EXTENSION_UPDATE = 'ibcmd_extension_update'
    TYPE_IBCMD_CLI = 'ibcmd_cli'
    # CLI operation types
    TYPE_DESIGNER_CLI = 'designer_cli'

    TYPE_CHOICES = [
        # OData operations
        (TYPE_CREATE, 'Create'),
        (TYPE_UPDATE, 'Update'),
        (TYPE_DELETE, 'Delete'),
        (TYPE_QUERY, 'Query'),
        # RAS operations
        (TYPE_LOCK_SCHEDULED_JOBS, 'Lock Scheduled Jobs'),
        (TYPE_UNLOCK_SCHEDULED_JOBS, 'Unlock Scheduled Jobs'),
        (TYPE_TERMINATE_SESSIONS, 'Terminate Sessions'),
        (TYPE_BLOCK_SESSIONS, 'Block Sessions'),
        (TYPE_UNBLOCK_SESSIONS, 'Unblock Sessions'),
        # Cluster operations
        (TYPE_SYNC_CLUSTER, 'Sync Cluster'),
        (TYPE_DISCOVER_CLUSTERS, 'Discover Clusters'),
        (TYPE_HEALTH_CHECK, 'Health Check'),
        # IBCMD operations
        (TYPE_IBCMD_BACKUP, 'IBCMD Backup'),
        (TYPE_IBCMD_RESTORE, 'IBCMD Restore'),
        (TYPE_IBCMD_REPLICATE, 'IBCMD Replicate'),
        (TYPE_IBCMD_CREATE, 'IBCMD Create'),
        (TYPE_IBCMD_LOAD_CFG, 'IBCMD Load Config/Extension'),
        (TYPE_IBCMD_EXTENSION_UPDATE, 'IBCMD Extension Update'),
        (TYPE_IBCMD_CLI, 'IBCMD CLI (schema-driven)'),
        # CLI operations
        (TYPE_DESIGNER_CLI, 'Designer CLI'),
    ]

    # Identity
    id = models.CharField(max_length=64, primary_key=True)
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)

    # Operation Details
    operation_type = models.CharField(max_length=32, choices=TYPE_CHOICES, db_index=True)
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
    task_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
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
            models.Index(fields=['task_id']),
        ]
        verbose_name = 'Batch Operation'
        verbose_name_plural = 'Batch Operations'
        permissions = (
            ("execute_safe_operation", "Can execute safe operations"),
            ("execute_dangerous_operation", "Can execute dangerous operations"),
            ("cancel_operation", "Can cancel operations"),
            ("view_operation_logs", "Can view operation logs"),
            ("manage_driver_catalogs", "Can manage driver catalogs"),
        )

    def __str__(self):
        return f"Batch {self.name} ({self.status})"

    def update_progress(self):
        """
        Update progress and statistics based on related tasks.
        Should be called after task status changes.
        """
        # Import here to avoid circular import
        from .task import Task

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
    def duration_seconds(self) -> Optional[float]:
        """Calculate operation duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (timezone.now() - self.started_at).total_seconds()
        return None

    @property
    def success_rate(self) -> Optional[float]:
        """Calculate success rate percentage."""
        if self.total_tasks == 0:
            return None
        return (self.completed_tasks / self.total_tasks) * 100
