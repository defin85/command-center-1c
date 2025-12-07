"""
Serializers for Internal API endpoints.

Minimal serializers for Go Worker communication.
"""

from rest_framework import serializers


# =============================================================================
# Scheduler Job History Serializers
# =============================================================================


class SchedulerRunStartSerializer(serializers.Serializer):
    """Input serializer for starting scheduler job run."""

    job_name = serializers.CharField(max_length=255)
    worker_instance = serializers.CharField(max_length=255)


class SchedulerRunCompleteSerializer(serializers.Serializer):
    """Input serializer for completing scheduler job run."""

    status = serializers.ChoiceField(choices=["success", "failed", "partial"])
    duration_ms = serializers.IntegerField(min_value=0)
    result_summary = serializers.CharField(required=False, allow_blank=True, default="")
    error_message = serializers.CharField(required=False, allow_blank=True, default="")
    items_processed = serializers.IntegerField(min_value=0, default=0)
    items_failed = serializers.IntegerField(min_value=0, default=0)


# =============================================================================
# Task Execution Log Serializers
# =============================================================================


class TaskStartSerializer(serializers.Serializer):
    """Input serializer for starting task execution."""

    task_id = serializers.CharField(max_length=64)
    task_type = serializers.CharField(max_length=100)
    queue_name = serializers.CharField(max_length=255)
    worker_instance = serializers.CharField(max_length=255)
    operation_id = serializers.CharField(
        max_length=64, required=False, allow_blank=True
    )


class TaskCompleteSerializer(serializers.Serializer):
    """Input serializer for completing task execution."""

    status = serializers.ChoiceField(choices=["success", "failed", "cancelled"])
    duration_ms = serializers.IntegerField(min_value=0)
    result_summary = serializers.CharField(required=False, allow_blank=True, default="")
    error_message = serializers.CharField(required=False, allow_blank=True, default="")
    error_type = serializers.CharField(required=False, allow_blank=True, default="")
    retry_count = serializers.IntegerField(min_value=0, default=0)


# =============================================================================
# Database Credentials Serializer
# =============================================================================


class DatabaseCredentialsSerializer(serializers.Serializer):
    """Output serializer for database credentials (minimal fields)."""

    odata_url = serializers.URLField()
    username = serializers.CharField()
    password = serializers.CharField()
    cluster_id = serializers.UUIDField(allow_null=True)


# =============================================================================
# Health Update Serializers
# =============================================================================


class HealthUpdateSerializer(serializers.Serializer):
    """Input serializer for health status updates."""

    healthy = serializers.BooleanField()
    error_message = serializers.CharField(required=False, allow_blank=True, default="")
    last_check_at = serializers.DateTimeField(required=False, allow_null=True)
    response_time_ms = serializers.IntegerField(
        required=False, min_value=0, allow_null=True
    )
    error_code = serializers.CharField(required=False, allow_blank=True, default="")
