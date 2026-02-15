from __future__ import annotations

import uuid
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django_fsm import FSMField, transition


User = get_user_model()
DEFAULT_POOL_RUN_COMMAND_LOG_RETENTION_DAYS = 30


def get_pool_run_command_log_expires_at():
    retention_days_raw = getattr(
        settings,
        "POOL_RUN_COMMAND_LOG_RETENTION_DAYS",
        DEFAULT_POOL_RUN_COMMAND_LOG_RETENTION_DAYS,
    )
    try:
        retention_days = int(retention_days_raw)
    except (TypeError, ValueError):
        retention_days = DEFAULT_POOL_RUN_COMMAND_LOG_RETENTION_DAYS

    if retention_days < 1:
        retention_days = 1
    return timezone.now() + timedelta(days=retention_days)


class OrganizationStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    ARCHIVED = "archived", "Archived"


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE, related_name="organizations")
    database = models.OneToOneField(
        "databases.Database",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization",
        help_text="Linked infobase (1:1 mapping).",
    )
    name = models.CharField(max_length=255)
    full_name = models.CharField(max_length=512, blank=True)
    inn = models.CharField(max_length=12, help_text="Taxpayer identification number")
    kpp = models.CharField(max_length=9, blank=True, help_text="Reason code for registration")
    status = models.CharField(
        max_length=16,
        choices=OrganizationStatus.choices,
        default=OrganizationStatus.ACTIVE,
        db_index=True,
    )
    external_ref = models.CharField(max_length=255, blank=True, help_text="External system reference")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pool_organizations"
        indexes = [
            models.Index(fields=["tenant", "inn"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "-updated_at"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "inn"], name="uniq_pool_org_tenant_inn"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.inn})"


class OrganizationPool(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE, related_name="organization_pools")
    code = models.SlugField(max_length=64)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "organization_pools"
        indexes = [
            models.Index(fields=["tenant", "is_active"]),
            models.Index(fields=["tenant", "-updated_at"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uniq_pool_tenant_code"),
        ]

    def __str__(self) -> str:
        return f"{self.code}: {self.name}"

    def validate_graph(self, target_date: date | None = None) -> None:
        from .validators import validate_pool_graph_for_date

        validate_pool_graph_for_date(self, target_date or timezone.localdate())


class PoolSchemaTemplateFormat(models.TextChoices):
    XLSX = "xlsx", "XLSX"
    JSON = "json", "JSON"


class PoolSchemaTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE, related_name="pool_schema_templates")
    code = models.SlugField(max_length=64)
    name = models.CharField(max_length=255)
    format = models.CharField(
        max_length=16,
        choices=PoolSchemaTemplateFormat.choices,
        default=PoolSchemaTemplateFormat.XLSX,
        db_index=True,
    )
    is_public = models.BooleanField(default=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    schema = models.JSONField(default=dict, blank=True, help_text="Field mapping and parse settings.")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pool_schema_templates"
        indexes = [
            models.Index(fields=["tenant", "is_public", "is_active"]),
            models.Index(fields=["tenant", "format"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uniq_pool_template_tenant_code"),
        ]

    def __str__(self) -> str:
        return f"{self.code} ({self.format})"


class PoolRunDirection(models.TextChoices):
    TOP_DOWN = "top_down", "Top Down"
    BOTTOM_UP = "bottom_up", "Bottom Up"


class PoolRunMode(models.TextChoices):
    SAFE = "safe", "Safe"
    UNSAFE = "unsafe", "Unsafe"


class PoolRun(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_VALIDATED = "validated"
    STATUS_PUBLISHING = "publishing"
    STATUS_PARTIAL_SUCCESS = "partial_success"
    STATUS_PUBLISHED = "published"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_VALIDATED, "Validated"),
        (STATUS_PUBLISHING, "Publishing"),
        (STATUS_PARTIAL_SUCCESS, "Partial Success"),
        (STATUS_PUBLISHED, "Published"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE, related_name="pool_runs")
    pool = models.ForeignKey(OrganizationPool, on_delete=models.PROTECT, related_name="runs")
    schema_template = models.ForeignKey(
        PoolSchemaTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="runs",
    )
    mode = models.CharField(
        max_length=16,
        choices=PoolRunMode.choices,
        default=PoolRunMode.SAFE,
        db_index=True,
    )
    direction = models.CharField(
        max_length=16,
        choices=PoolRunDirection.choices,
        default=PoolRunDirection.TOP_DOWN,
        db_index=True,
    )
    status = FSMField(
        default=STATUS_DRAFT,
        choices=STATUS_CHOICES,
        protected=True,
        help_text="Run lifecycle state (FSM-protected).",
    )
    period_start = models.DateField(db_index=True)
    period_end = models.DateField(null=True, blank=True)
    run_input = models.JSONField(default=dict, blank=True)
    source_hash = models.CharField(max_length=64, blank=True, default="")
    idempotency_key = models.CharField(max_length=128, blank=True, default="", db_index=True)
    workflow_execution_id = models.UUIDField(null=True, blank=True, db_index=True)
    workflow_status = models.CharField(max_length=32, blank=True, default="", db_index=True)
    execution_backend = models.CharField(max_length=32, blank=True, default="legacy_pool_runtime", db_index=True)
    workflow_template_name = models.CharField(max_length=200, blank=True, default="")
    seed = models.BigIntegerField(null=True, blank=True)
    validation_summary = models.JSONField(default=dict, blank=True)
    publication_summary = models.JSONField(default=dict, blank=True)
    diagnostics = models.JSONField(default=list, blank=True)
    last_error = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    publication_confirmed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_pool_runs",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    publication_confirmed_at = models.DateTimeField(null=True, blank=True)
    publishing_started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "pool_runs"
        indexes = [
            models.Index(fields=["tenant", "status", "-created_at"]),
            models.Index(fields=["pool", "period_start"]),
            models.Index(fields=["direction", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(period_end__isnull=True) | Q(period_end__gte=F("period_start")),
                name="chk_pool_run_period_range",
            ),
            models.UniqueConstraint(
                fields=["tenant", "idempotency_key"],
                condition=~Q(idempotency_key=""),
                name="uniq_pool_run_tenant_idempotency_key",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pool_id}:{self.id} ({self.status})"

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            self.STATUS_PARTIAL_SUCCESS,
            self.STATUS_PUBLISHED,
            self.STATUS_FAILED,
        }

    @transition(field=status, source=STATUS_DRAFT, target=STATUS_VALIDATED)
    def mark_validated(self, *, summary: dict | None = None, diagnostics: list | None = None) -> None:
        self.validated_at = timezone.now()
        if summary is not None:
            self.validation_summary = summary
        if diagnostics is not None:
            self.diagnostics = diagnostics
        self._record_audit_event(
            event_type="run.validated",
            status_before=self.STATUS_DRAFT,
            status_after=self.STATUS_VALIDATED,
            payload={"summary": summary or {}, "diagnostics_count": len(diagnostics or [])},
        )

    def confirm_publication(self, *, confirmed_by: User | None = None) -> None:
        self.publication_confirmed_at = timezone.now()
        self.publication_confirmed_by = confirmed_by
        self._record_audit_event(
            event_type="run.publication_confirmed",
            actor=confirmed_by,
            status_before=self.status,
            status_after=self.status,
            payload={"mode": self.mode},
        )

    def _can_start_publishing(self) -> bool:
        if self.mode == PoolRunMode.UNSAFE:
            return True
        return self.publication_confirmed_at is not None

    @transition(
        field=status,
        source=STATUS_VALIDATED,
        target=STATUS_PUBLISHING,
        conditions=[_can_start_publishing],
    )
    def start_publishing(self) -> None:
        self.publishing_started_at = timezone.now()
        self._record_audit_event(
            event_type="run.publishing_started",
            status_before=self.STATUS_VALIDATED,
            status_after=self.STATUS_PUBLISHING,
            payload={"mode": self.mode},
        )

    @transition(
        field=status,
        source=[STATUS_PARTIAL_SUCCESS, STATUS_FAILED],
        target=STATUS_PUBLISHING,
        conditions=[_can_start_publishing],
    )
    def restart_publishing(self) -> None:
        source_status = self.status
        self.publishing_started_at = timezone.now()
        self.completed_at = None
        self.last_error = ""
        self._record_audit_event(
            event_type="run.retry_publishing_started",
            status_before=source_status,
            status_after=self.STATUS_PUBLISHING,
            payload={"mode": self.mode},
        )

    @transition(field=status, source=STATUS_PUBLISHING, target=STATUS_PARTIAL_SUCCESS)
    def mark_partial_success(self, *, summary: dict | None = None) -> None:
        self.completed_at = timezone.now()
        if summary is not None:
            self.publication_summary = summary
        self._record_audit_event(
            event_type="run.partial_success",
            status_before=self.STATUS_PUBLISHING,
            status_after=self.STATUS_PARTIAL_SUCCESS,
            payload={"summary": summary or {}},
        )

    @transition(field=status, source=STATUS_PUBLISHING, target=STATUS_PUBLISHED)
    def mark_published(self, *, summary: dict | None = None) -> None:
        self.completed_at = timezone.now()
        if summary is not None:
            self.publication_summary = summary
        self._record_audit_event(
            event_type="run.published",
            status_before=self.STATUS_PUBLISHING,
            status_after=self.STATUS_PUBLISHED,
            payload={"summary": summary or {}},
        )

    @transition(field=status, source=[STATUS_DRAFT, STATUS_VALIDATED, STATUS_PUBLISHING], target=STATUS_FAILED)
    def mark_failed(self, *, error: str, diagnostics: list | None = None, summary: dict | None = None) -> None:
        source_status = self.status
        self.last_error = str(error or "").strip()
        self.completed_at = timezone.now()
        if diagnostics is not None:
            self.diagnostics = diagnostics
        if summary is not None:
            self.publication_summary = summary
        self._record_audit_event(
            event_type="run.failed",
            status_before=source_status,
            status_after=self.STATUS_FAILED,
            payload={
                "error": self.last_error,
                "summary": summary or {},
                "diagnostics_count": len(diagnostics or []),
            },
        )

    def add_audit_event(
        self,
        *,
        event_type: str,
        payload: dict | None = None,
        actor: User | None = None,
        status_before: str | None = None,
        status_after: str | None = None,
    ) -> None:
        self._record_audit_event(
            event_type=event_type,
            payload=payload,
            actor=actor,
            status_before=status_before,
            status_after=status_after,
        )

    def _record_audit_event(
        self,
        *,
        event_type: str,
        payload: dict | None = None,
        actor: User | None = None,
        status_before: str | None = None,
        status_after: str | None = None,
    ) -> None:
        if not self.pk:
            return
        PoolRunAuditEvent.objects.create(
            run=self,
            tenant=self.tenant,
            event_type=event_type,
            status_before=status_before or "",
            status_after=status_after or "",
            payload=payload or {},
            actor=actor,
        )


class PoolRunAuditEvent(models.Model):
    id = models.BigAutoField(primary_key=True)
    run = models.ForeignKey(PoolRun, on_delete=models.CASCADE, related_name="audit_events")
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE, related_name="pool_run_audit_events")
    event_type = models.CharField(max_length=64, db_index=True)
    status_before = models.CharField(max_length=32, blank=True, default="")
    status_after = models.CharField(max_length=32, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "pool_run_audit_events"
        indexes = [
            models.Index(fields=["run", "-created_at"]),
            models.Index(fields=["tenant", "event_type", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.run_id}:{self.event_type}@{self.created_at.isoformat()}"


class PoolRunCommandType(models.TextChoices):
    CONFIRM_PUBLICATION = "confirm_publication", "Confirm Publication"
    ABORT_PUBLICATION = "abort_publication", "Abort Publication"
    RETRY_PUBLICATION = "retry_publication", "Retry Publication"


class PoolRunCommandResultClass(models.TextChoices):
    ACCEPTED = "accepted", "Accepted"
    NOOP = "noop", "No-op"
    CONFLICT = "conflict", "Conflict"
    BAD_REQUEST = "bad_request", "Bad Request"
    ERROR = "error", "Error"


class PoolRunCommandCasOutcome(models.TextChoices):
    WON = "won", "Won"
    LOST = "lost", "Lost"
    NOT_APPLICABLE = "not_applicable", "Not Applicable"


class PoolRunCommandLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    run = models.ForeignKey(PoolRun, on_delete=models.CASCADE, related_name="command_logs")
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE, related_name="pool_run_command_logs")
    command_type = models.CharField(max_length=32, choices=PoolRunCommandType.choices, db_index=True)
    idempotency_key = models.CharField(max_length=128)
    command_fingerprint = models.CharField(max_length=128, blank=True, default="")
    result_class = models.CharField(max_length=32, choices=PoolRunCommandResultClass.choices)
    cas_outcome = models.CharField(
        max_length=32,
        choices=PoolRunCommandCasOutcome.choices,
        default=PoolRunCommandCasOutcome.NOT_APPLICABLE,
    )
    response_status_code = models.PositiveSmallIntegerField(default=200)
    response_snapshot = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_pool_run_command_logs",
    )
    replay_count = models.PositiveIntegerField(default=0)
    last_replayed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    expires_at = models.DateTimeField(default=get_pool_run_command_log_expires_at, db_index=True)

    class Meta:
        db_table = "pool_run_command_log"
        indexes = [
            models.Index(fields=["run", "command_type", "-created_at"]),
            models.Index(fields=["tenant", "command_type", "-created_at"]),
            models.Index(fields=["run", "idempotency_key"]),
            models.Index(fields=["expires_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "command_type", "idempotency_key"],
                name="uniq_pool_run_command_log_scope",
            ),
            models.CheckConstraint(
                condition=~Q(idempotency_key=""),
                name="chk_pool_run_command_log_nonempty_key",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.run_id}:{self.command_type}:{self.idempotency_key}"


class PoolRunCommandOutboxIntent(models.TextChoices):
    ENQUEUE_WORKFLOW_EXECUTION = "enqueue_workflow_execution", "Enqueue Workflow Execution"
    CANCEL_WORKFLOW_EXECUTION = "cancel_workflow_execution", "Cancel Workflow Execution"


class PoolRunCommandOutboxStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    DISPATCHED = "dispatched", "Dispatched"


class PoolRunCommandOutbox(models.Model):
    id = models.BigAutoField(primary_key=True)
    run = models.ForeignKey(PoolRun, on_delete=models.CASCADE, related_name="command_outbox_entries")
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE, related_name="pool_run_command_outbox")
    command_log = models.ForeignKey(
        PoolRunCommandLog,
        on_delete=models.CASCADE,
        related_name="outbox_entries",
        null=True,
        blank=True,
    )
    intent_type = models.CharField(max_length=48, choices=PoolRunCommandOutboxIntent.choices, db_index=True)
    stream_name = models.CharField(max_length=128, default="commands:worker:workflows")
    message_payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16,
        choices=PoolRunCommandOutboxStatus.choices,
        default=PoolRunCommandOutboxStatus.PENDING,
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
        db_table = "pool_run_command_outbox"
        indexes = [
            models.Index(fields=["status", "next_retry_at"]),
            models.Index(fields=["run", "status", "-created_at"]),
            models.Index(fields=["tenant", "status", "-created_at"]),
            models.Index(fields=["command_log", "intent_type"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(stream_name=""),
                name="chk_pool_run_command_outbox_stream_name_nonempty",
            ),
            models.UniqueConstraint(
                fields=["command_log", "intent_type"],
                condition=Q(command_log__isnull=False),
                name="uniq_pool_run_command_outbox_command_intent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.run_id}:{self.intent_type}:{self.status}"


class PoolPublicationAttemptStatus(models.TextChoices):
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


class PoolPublicationAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(PoolRun, on_delete=models.CASCADE, related_name="publication_attempts")
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE, related_name="pool_publication_attempts")
    target_database = models.ForeignKey(
        "databases.Database",
        on_delete=models.PROTECT,
        related_name="pool_publication_attempts",
    )
    attempt_number = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=16, choices=PoolPublicationAttemptStatus.choices, db_index=True)
    entity_name = models.CharField(max_length=255)
    documents_count = models.PositiveIntegerField(default=1)
    external_document_identity = models.CharField(max_length=128, blank=True, default="")
    identity_strategy = models.CharField(max_length=64, blank=True, default="")
    posted = models.BooleanField(default=False)
    http_status = models.IntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True)
    request_summary = models.JSONField(default=dict, blank=True)
    response_summary = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pool_publication_attempts"
        indexes = [
            models.Index(fields=["run", "status", "-created_at"]),
            models.Index(fields=["target_database", "status", "-created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "target_database", "attempt_number"],
                name="uniq_pool_publication_attempt_per_target",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.run_id}:{self.target_database_id}#{self.attempt_number} ({self.status})"


class PoolNodeVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pool = models.ForeignKey(OrganizationPool, on_delete=models.CASCADE, related_name="node_versions")
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="pool_node_versions")
    effective_from = models.DateField(db_index=True)
    effective_to = models.DateField(null=True, blank=True, db_index=True)
    is_root = models.BooleanField(default=False, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pool_node_versions"
        indexes = [
            models.Index(fields=["pool", "effective_from"]),
            models.Index(fields=["pool", "effective_to"]),
            models.Index(fields=["organization", "effective_from"]),
            models.Index(fields=["pool", "is_root"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True) | Q(effective_to__gte=F("effective_from")),
                name="chk_pool_node_effective_range",
            ),
            models.UniqueConstraint(
                fields=["pool", "organization", "effective_from"],
                name="uniq_pool_node_version_start",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pool_id}:{self.organization_id} [{self.effective_from}..{self.effective_to or 'open'}]"


class PoolEdgeVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pool = models.ForeignKey(OrganizationPool, on_delete=models.CASCADE, related_name="edge_versions")
    parent_node = models.ForeignKey(PoolNodeVersion, on_delete=models.CASCADE, related_name="outgoing_edges")
    child_node = models.ForeignKey(PoolNodeVersion, on_delete=models.CASCADE, related_name="incoming_edges")
    weight = models.DecimalField(max_digits=12, decimal_places=6, default=1)
    min_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    max_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    effective_from = models.DateField(db_index=True)
    effective_to = models.DateField(null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pool_edge_versions"
        indexes = [
            models.Index(fields=["pool", "effective_from"]),
            models.Index(fields=["pool", "effective_to"]),
            models.Index(fields=["parent_node", "effective_from"]),
            models.Index(fields=["child_node", "effective_from"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True) | Q(effective_to__gte=F("effective_from")),
                name="chk_pool_edge_effective_range",
            ),
            models.CheckConstraint(
                condition=~Q(parent_node=F("child_node")),
                name="chk_pool_edge_no_self_loop",
            ),
            models.CheckConstraint(
                condition=Q(weight__gt=0),
                name="chk_pool_edge_positive_weight",
            ),
            models.CheckConstraint(
                condition=Q(min_amount__isnull=True)
                | Q(max_amount__isnull=True)
                | Q(max_amount__gte=F("min_amount")),
                name="chk_pool_edge_amount_bounds",
            ),
            models.UniqueConstraint(
                fields=["pool", "parent_node", "child_node", "effective_from"],
                name="uniq_pool_edge_version_start",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.pool_id}:{self.parent_node_id}->{self.child_node_id} "
            f"[{self.effective_from}..{self.effective_to or 'open'}]"
        )
