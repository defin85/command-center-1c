"""
Serializers for Internal API endpoints.

Minimal serializers for Go Worker communication.
"""

import uuid

from rest_framework import serializers


# =============================================================================
# Scheduler Job History Serializers
# =============================================================================


class SchedulerRunStartSerializer(serializers.Serializer):
    """Input serializer for starting scheduler job run."""

    job_name = serializers.CharField(max_length=255)
    worker_instance = serializers.CharField(max_length=255)
    job_config = serializers.JSONField(required=False, default=dict)


class SchedulerRunCompleteSerializer(serializers.Serializer):
    """Input serializer for completing scheduler job run."""

    status = serializers.ChoiceField(choices=["success", "failed", "skipped"])
    duration_ms = serializers.IntegerField(min_value=0, required=False, default=0)
    result_summary = serializers.CharField(required=False, allow_blank=True, default="")
    error_message = serializers.CharField(required=False, allow_blank=True, default="")
    items_processed = serializers.IntegerField(min_value=0, default=0)
    items_failed = serializers.IntegerField(min_value=0, default=0)


# =============================================================================
# Task Execution Log Serializers
# =============================================================================


class TaskExecutionStartSerializer(serializers.Serializer):
    """Input serializer for starting task execution."""

    operation_id = serializers.CharField(max_length=64)
    task_type = serializers.CharField(max_length=100)
    target_id = serializers.CharField(max_length=64)
    target_type = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    worker_instance = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    parameters = serializers.JSONField(required=False, default=dict)


class TaskExecutionCompleteSerializer(serializers.Serializer):
    """Input serializer for completing task execution."""

    status = serializers.ChoiceField(choices=["success", "failed", "skipped"])
    duration_ms = serializers.IntegerField(min_value=0, required=False, default=0)
    result = serializers.JSONField(required=False, default=dict)
    error_message = serializers.CharField(required=False, allow_blank=True, default="")
    error_code = serializers.CharField(required=False, allow_blank=True, default="")
    retry_count = serializers.IntegerField(min_value=0, default=0)


# =============================================================================
# Artifacts Purge Serializers
# =============================================================================


class ArtifactPurgeJobClaimSerializer(serializers.Serializer):
    """Input serializer for claiming next purge job."""

    worker_instance = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class ArtifactPurgeJobProgressUpdateSerializer(serializers.Serializer):
    """Input serializer for purge job progress updates."""

    deleted_objects = serializers.IntegerField(min_value=0, required=False, default=0)
    deleted_bytes = serializers.IntegerField(min_value=0, required=False, default=0)


class ArtifactPurgeJobCompleteSerializer(serializers.Serializer):
    """Input serializer for completing purge job."""

    status = serializers.ChoiceField(choices=["success", "failed"])
    deleted_objects = serializers.IntegerField(min_value=0, required=False, default=0)
    deleted_bytes = serializers.IntegerField(min_value=0, required=False, default=0)
    error_code = serializers.CharField(required=False, allow_blank=True, default="")
    error_message = serializers.CharField(required=False, allow_blank=True, default="")


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


# =============================================================================
# Failed Event Serializers (Event Replay System)
# =============================================================================


class FailedEventSerializer(serializers.Serializer):
    """Output serializer for FailedEvent (used in pending list)."""

    id = serializers.IntegerField(read_only=True)
    channel = serializers.CharField()
    event_type = serializers.CharField()
    correlation_id = serializers.CharField()
    payload = serializers.JSONField()
    source_service = serializers.CharField()
    original_timestamp = serializers.DateTimeField()
    status = serializers.CharField()
    retry_count = serializers.IntegerField()
    max_retries = serializers.IntegerField()
    last_error = serializers.CharField()
    created_at = serializers.DateTimeField()


class FailedEventReplayedSerializer(serializers.Serializer):
    """Input serializer for marking event as replayed."""

    replayed_at = serializers.DateTimeField(required=False, allow_null=True)


class FailedEventFailedSerializer(serializers.Serializer):
    """Input serializer for marking event as failed (increment retry)."""

    error_message = serializers.CharField(required=True, max_length=10000)
    increment_retry = serializers.BooleanField(default=True)


class FailedEventsCleanupSerializer(serializers.Serializer):
    """Input serializer for cleanup of old replayed events."""

    retention_days = serializers.IntegerField(default=7, min_value=1, max_value=365)


# =============================================================================
# Template Serializers (for Go Worker Template Engine)
# =============================================================================


class TemplateSerializer(serializers.Serializer):
    """Output serializer for exposure-backed runtime template data."""

    id = serializers.CharField()
    name = serializers.CharField()
    operation_type = serializers.CharField()
    target_entity = serializers.CharField()
    template_data = serializers.JSONField()
    version = serializers.IntegerField(default=1)
    is_active = serializers.BooleanField()


class TemplateRenderRequestSerializer(serializers.Serializer):
    """Input serializer for template rendering request."""

    context = serializers.JSONField(
        help_text="Context data for template rendering"
    )


class TemplateRenderResponseSerializer(serializers.Serializer):
    """Output serializer for template rendering response."""

    rendered = serializers.JSONField()
    success = serializers.BooleanField()
    error = serializers.CharField(required=False, allow_blank=True, default="")


# =============================================================================
# Timeline Serializers (Operation Observability)
# =============================================================================


class TimelineEventSerializer(serializers.Serializer):
    """Single timeline event."""

    timestamp = serializers.IntegerField(help_text="Timestamp in milliseconds")
    event = serializers.CharField()
    service = serializers.CharField(required=False, default="")
    metadata = serializers.JSONField(required=False, default=dict)


class TimelineResponseSerializer(serializers.Serializer):
    """Response for get-operation-timeline endpoint."""

    operation_id = serializers.CharField()
    timeline = TimelineEventSerializer(many=True)
    total_events = serializers.IntegerField()
    duration_ms = serializers.IntegerField(allow_null=True)


# =============================================================================
# Workflow Execution Serializers (Go Workflow Engine)
# =============================================================================


class WorkflowExecutionStatusUpdateSerializer(serializers.Serializer):
    """Input serializer for workflow execution status updates."""

    execution_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=[
        "pending",
        "running",
        "completed",
        "failed",
        "cancelled",
    ])
    error_message = serializers.CharField(required=False, allow_blank=True, default="")
    error_code = serializers.CharField(required=False, allow_blank=True, max_length=128)
    error_details = serializers.JSONField(required=False, allow_null=True)
    result = serializers.JSONField(required=False, default=dict)


class PoolRuntimeOperationRefSerializer(serializers.Serializer):
    """Pinned operation binding provenance for pool runtime bridge payload."""

    alias = serializers.CharField(max_length=255)
    binding_mode = serializers.ChoiceField(choices=["required_alias", "alias_latest", "pinned_exposure"])
    template_exposure_id = serializers.UUIDField(required=False, allow_null=True)
    template_exposure_revision = serializers.IntegerField(required=False, allow_null=True, min_value=1)

    def validate(self, attrs):
        binding_mode = str(attrs.get("binding_mode") or "").strip()
        template_exposure_id = attrs.get("template_exposure_id")
        template_exposure_revision = attrs.get("template_exposure_revision")

        if binding_mode == "pinned_exposure":
            errors: dict[str, str] = {}
            if template_exposure_id is None:
                errors["template_exposure_id"] = "This field is required for pinned_exposure mode."
            if template_exposure_revision is None:
                errors["template_exposure_revision"] = (
                    "This field is required for pinned_exposure mode."
                )
            if errors:
                raise serializers.ValidationError(errors)
        else:
            attrs.pop("template_exposure_id", None)
            attrs.pop("template_exposure_revision", None)

        return attrs


class PoolRuntimePublicationAuthSerializer(serializers.Serializer):
    """Publication auth provenance context for pool.publication_odata credentials resolution."""

    strategy = serializers.ChoiceField(choices=["actor", "service"])
    actor_username = serializers.CharField(max_length=255, required=False, allow_blank=False)
    source = serializers.CharField(max_length=64)

    def validate(self, attrs):
        strategy = str(attrs.get("strategy") or "").strip().lower()
        source = str(attrs.get("source") or "").strip()
        actor_username = str(attrs.get("actor_username") or "").strip()

        if not source:
            raise serializers.ValidationError({"source": "source is required."})
        if strategy == "actor" and not actor_username:
            raise serializers.ValidationError({"actor_username": "actor_username is required for actor strategy."})
        if strategy == "service":
            attrs.pop("actor_username", None)

        attrs["strategy"] = strategy
        attrs["source"] = source
        if actor_username:
            attrs["actor_username"] = actor_username
        return attrs


class PoolRuntimeStepExecutionSerializer(serializers.Serializer):
    """Input serializer for canonical pool runtime bridge endpoint."""

    tenant_id = serializers.UUIDField()
    pool_run_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    workflow_execution_id = serializers.UUIDField()
    node_id = serializers.CharField(max_length=128)
    operation_type = serializers.CharField(max_length=255)
    operation_ref = PoolRuntimeOperationRefSerializer()
    step_attempt = serializers.IntegerField(min_value=1)
    transport_attempt = serializers.IntegerField(min_value=1)
    idempotency_key = serializers.CharField(min_length=8, max_length=255)
    publication_auth = PoolRuntimePublicationAuthSerializer(required=False, allow_null=True)
    step_deadline_utc = serializers.DateTimeField(required=False, allow_null=True)
    payload = serializers.JSONField()

    def validate_payload(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("payload must be an object.")
        return value

    def validate(self, attrs):
        operation_type = str(attrs.get("operation_type") or "").strip()
        raw_pool_run_id = str(attrs.get("pool_run_id") or "").strip()
        pool_run_optional_operation_types = {
            "pool.master_data_sync.inbound",
            "pool.master_data_sync.dispatch",
            "pool.master_data_sync.finalize",
            "pool.master_data_sync.launch",
        }

        if not operation_type:
            raise serializers.ValidationError({"operation_type": "operation_type is required."})
        if operation_type not in pool_run_optional_operation_types and not raw_pool_run_id:
            raise serializers.ValidationError(
                {"pool_run_id": "pool_run_id is required for this operation_type."}
            )
        if raw_pool_run_id:
            try:
                uuid.UUID(raw_pool_run_id)
            except ValueError as exc:
                raise serializers.ValidationError({"pool_run_id": "pool_run_id must be a valid UUID."}) from exc

        attrs["operation_type"] = operation_type
        attrs["pool_run_id"] = raw_pool_run_id
        return attrs
