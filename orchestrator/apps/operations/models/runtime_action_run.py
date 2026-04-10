"""RuntimeActionRun model - async journal for runtime-control actions."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class RuntimeActionRun(models.Model):
    ACTION_PROBE = "probe"
    ACTION_RESTART = "restart"
    ACTION_TAIL_LOGS = "tail_logs"
    ACTION_TRIGGER_NOW = "trigger_now"

    ACTION_CHOICES = [
        (ACTION_PROBE, "Probe"),
        (ACTION_RESTART, "Restart"),
        (ACTION_TAIL_LOGS, "Tail Logs"),
        (ACTION_TRIGGER_NOW, "Trigger Now"),
    ]

    STATUS_ACCEPTED = "accepted"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=64, default="local_scripts", db_index=True)
    runtime_id = models.CharField(max_length=128, db_index=True)
    runtime_name = models.CharField(max_length=64, db_index=True)
    action_type = models.CharField(max_length=32, choices=ACTION_CHOICES, db_index=True)
    target_job_name = models.CharField(max_length=128, blank=True, default="", db_index=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACCEPTED, db_index=True)

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="runtime_action_runs",
    )
    requested_by_username = models.CharField(max_length=150, blank=True, default="")
    reason = models.TextField(blank=True, default="")

    request_payload = models.JSONField(default=dict, blank=True)
    result_payload = models.JSONField(default=dict, blank=True)
    result_excerpt = models.TextField(blank=True, default="")
    error_message = models.TextField(blank=True, default="")

    scheduler_job_run = models.ForeignKey(
        "operations.SchedulerJobRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="runtime_action_runs",
    )

    requested_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "runtime_action_runs"
        ordering = ["-requested_at"]
        verbose_name = "Runtime Action Run"
        verbose_name_plural = "Runtime Action Runs"
        indexes = [
            models.Index(fields=["runtime_id", "requested_at"]),
            models.Index(fields=["action_type", "requested_at"]),
            models.Index(fields=["status", "requested_at"]),
            models.Index(fields=["target_job_name", "requested_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.runtime_name}:{self.action_type} [{self.status}]"
