"""TaskExecutionLog model - history of individual task executions."""

import uuid
from django.db import models


class TaskExecutionLog(models.Model):
    """
    History of individual task executions.
    Records detailed execution information for each task run.
    Written by Go workers, read-only in Django.
    """

    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_RETRYING = 'retrying'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_RETRYING, 'Retrying'),
    ]

    id = models.AutoField(primary_key=True)

    # Task identification
    task_id = models.UUIDField(
        default=uuid.uuid4,
        db_index=True,
        help_text="Unique identifier of the task execution"
    )
    task_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Type of task (e.g., 'odata_query', 'lock_sessions')"
    )
    queue_name = models.CharField(
        max_length=100,
        help_text="Name of the queue task was pulled from"
    )
    worker_instance = models.CharField(
        max_length=255,
        help_text="Hostname or pod name of the worker that executed the task"
    )

    # Relation to BatchOperation (optional)
    operation = models.ForeignKey(
        'operations.BatchOperation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='execution_logs',
        help_text="Related batch operation if applicable"
    )

    # Execution status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True
    )

    # Timing
    started_at = models.DateTimeField(db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Execution duration in milliseconds"
    )

    # Input/Output (only key data, not full payloads)
    input_summary = models.JSONField(
        default=dict,
        help_text="Summary of input parameters (only key data)"
    )
    result_summary = models.JSONField(
        default=dict,
        help_text="Summary of execution results"
    )

    # Error handling
    error_message = models.TextField(
        blank=True,
        help_text="Error message if task failed"
    )
    error_type = models.CharField(
        max_length=255,
        blank=True,
        help_text="Exception class name (e.g., 'TimeoutError', 'ConnectionError')"
    )

    # Retry tracking
    retry_count = models.IntegerField(
        default=0,
        help_text="Number of retry attempts"
    )

    class Meta:
        db_table = 'task_execution_logs'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['task_id']),
            models.Index(fields=['task_type', 'started_at']),
            models.Index(fields=['status', 'started_at']),
            models.Index(fields=['operation', 'started_at']),
            models.Index(fields=['worker_instance', 'started_at']),
        ]
        verbose_name = 'Task Execution Log'
        verbose_name_plural = 'Task Execution Logs'

    def __str__(self):
        return f"{self.task_type} [{self.status}] - {self.task_id}"
