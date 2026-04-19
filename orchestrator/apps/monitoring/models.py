from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.tenancy.models import Tenant


class UiIncidentTelemetryBatch(models.Model):
    id = models.BigAutoField(primary_key=True)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="ui_incident_telemetry_batches",
    )
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ui_incident_telemetry_batches",
    )
    actor_username = models.CharField(max_length=150, blank=True, default="")
    batch_id = models.CharField(max_length=160)
    flush_reason = models.CharField(max_length=32)
    session_id = models.CharField(max_length=160, blank=True, default="")
    release_app = models.CharField(max_length=120, blank=True, default="")
    release_fingerprint = models.CharField(max_length=160, blank=True, default="")
    release_mode = models.CharField(max_length=80, blank=True, default="")
    release_origin = models.CharField(max_length=255, blank=True, default="")
    route_path = models.CharField(max_length=255, blank=True, default="")
    route_search = models.CharField(max_length=255, blank=True, default="")
    route_hash = models.CharField(max_length=255, blank=True, default="")
    route_context = models.JSONField(default=dict, blank=True)
    accepted_event_count = models.PositiveIntegerField(default=0)
    duplicate_event_count = models.PositiveIntegerField(default=0)
    dropped_event_count = models.PositiveIntegerField(default=0)
    first_occurred_at = models.DateTimeField(null=True, blank=True)
    last_occurred_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "monitoring_ui_incident_telemetry_batches"
        ordering = ["-last_occurred_at", "-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "batch_id"],
                name="uiit_batch_tenant_batch_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "last_occurred_at"], name="uiit_batch_tenant_last_idx"),
            models.Index(fields=["tenant", "actor_username"], name="uiit_batch_tenant_actor_idx"),
        ]


class UiIncidentTelemetryEvent(models.Model):
    id = models.BigAutoField(primary_key=True)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="ui_incident_telemetry_events",
    )
    batch = models.ForeignKey(
        UiIncidentTelemetryBatch,
        on_delete=models.CASCADE,
        related_name="events",
    )
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ui_incident_telemetry_events",
    )
    actor_username = models.CharField(max_length=150, blank=True, default="")
    session_id = models.CharField(max_length=160, blank=True, default="")
    event_id = models.CharField(max_length=160)
    event_type = models.CharField(max_length=80)
    occurred_at = models.DateTimeField()
    route_path = models.CharField(max_length=255, blank=True, default="")
    route_search = models.CharField(max_length=255, blank=True, default="")
    route_hash = models.CharField(max_length=255, blank=True, default="")
    route_context = models.JSONField(default=dict, blank=True)
    request_id = models.CharField(max_length=160, blank=True, default="")
    ui_action_id = models.CharField(max_length=160, blank=True, default="")
    trace_id = models.CharField(max_length=160, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "monitoring_ui_incident_telemetry_events"
        ordering = ["occurred_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "event_id"],
                name="uiit_event_tenant_event_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "occurred_at"], name="uiit_event_tenant_time_idx"),
            models.Index(fields=["tenant", "session_id"], name="uiit_event_tenant_sess_idx"),
            models.Index(fields=["tenant", "request_id"], name="uiit_event_tenant_req_idx"),
            models.Index(fields=["tenant", "ui_action_id"], name="uiit_event_tenant_act_idx"),
            models.Index(fields=["tenant", "route_path"], name="uiit_event_tenant_route_idx"),
            models.Index(fields=["tenant", "actor_username"], name="uiit_event_tenant_user_idx"),
            models.Index(fields=["tenant", "event_type"], name="uiit_event_tenant_type_idx"),
        ]
