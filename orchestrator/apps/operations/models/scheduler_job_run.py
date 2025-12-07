"""SchedulerJobRun model - history of scheduled job executions."""

from django.db import models


class SchedulerJobRun(models.Model):
    """
    History of scheduled job executions.
    Records each run of a scheduled job (e.g., health checks, sync operations).
    Written by Go workers, read-only in Django.
    """

    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_SKIPPED = 'skipped'

    STATUS_CHOICES = [
        (STATUS_RUNNING, 'Running'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_SKIPPED, 'Skipped'),
    ]

    id = models.AutoField(primary_key=True)

    # Job identification
    job_name = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Name of the scheduled job (e.g., 'health_check', 'sync_clusters')"
    )
    worker_instance = models.CharField(
        max_length=255,
        help_text="Hostname or pod name of the worker that executed the job"
    )

    # Execution status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_RUNNING,
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

    # Results
    result_summary = models.TextField(
        blank=True,
        help_text="Summary of job execution results"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if job failed"
    )
    error_traceback = models.TextField(
        blank=True,
        help_text="Full error traceback for debugging"
    )

    # Statistics
    items_processed = models.IntegerField(
        default=0,
        help_text="Number of items processed during execution"
    )
    items_failed = models.IntegerField(
        default=0,
        help_text="Number of items that failed during execution"
    )

    class Meta:
        db_table = 'scheduler_job_runs'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['job_name', 'started_at']),
            models.Index(fields=['status', 'started_at']),
            models.Index(fields=['worker_instance', 'started_at']),
        ]
        verbose_name = 'Scheduler Job Run'
        verbose_name_plural = 'Scheduler Job Runs'

    def __str__(self):
        return f"{self.job_name} [{self.status}] - {self.started_at}"
