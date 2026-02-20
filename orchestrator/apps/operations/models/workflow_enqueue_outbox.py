"""WorkflowEnqueueOutbox model - transactional outbox for workflow enqueue commands."""

from django.db import models
from django.utils import timezone


class WorkflowEnqueueOutbox(models.Model):
    """Stores workflow enqueue commands before/after stream publish."""

    STATUS_PENDING = "pending"
    STATUS_DISPATCHED = "dispatched"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_DISPATCHED, "Dispatched"),
    ]

    id = models.BigAutoField(primary_key=True)
    operation_id = models.CharField(max_length=64, unique=True, db_index=True)
    stream_name = models.CharField(max_length=128, default="commands:worker:workflows")
    message_payload = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    dispatch_attempts = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_attempted_at = models.DateTimeField(null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    stream_message_id = models.CharField(max_length=64, blank=True, default="")
    last_error_code = models.CharField(max_length=64, blank=True, default="")
    last_error = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "workflow_enqueue_outbox"
        indexes = [
            models.Index(fields=["status", "next_retry_at"]),
            models.Index(fields=["operation_id", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(stream_name=""),
                name="chk_workflow_enqueue_outbox_stream_name_nonempty",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.operation_id}:{self.status}"
