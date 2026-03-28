from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


User = get_user_model()


class PoolBatchKind(models.TextChoices):
    RECEIPT = "receipt", "Receipt"
    SALE = "sale", "Sale"


class PoolBatchSourceType(models.TextChoices):
    SCHEMA_TEMPLATE_UPLOAD = "schema_template_upload", "Schema Template Upload"
    INTEGRATION = "integration", "Integration"
    MANUAL = "manual", "Manual"


class PoolBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE, related_name="pool_batches")
    pool = models.ForeignKey("intercompany_pools.OrganizationPool", on_delete=models.PROTECT, related_name="batches")
    batch_kind = models.CharField(max_length=16, choices=PoolBatchKind.choices, db_index=True)
    source_type = models.CharField(max_length=32, choices=PoolBatchSourceType.choices, db_index=True)
    schema_template = models.ForeignKey(
        "intercompany_pools.PoolSchemaTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batches",
    )
    start_organization = models.ForeignKey(
        "intercompany_pools.Organization",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pool_batches_started",
    )
    run = models.OneToOneField(
        "intercompany_pools.PoolRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_batch",
    )
    workflow_execution_id = models.UUIDField(null=True, blank=True, db_index=True)
    operation_id = models.UUIDField(null=True, blank=True, db_index=True)
    workflow_status = models.CharField(max_length=32, blank=True, default="", db_index=True)
    period_start = models.DateField(db_index=True)
    period_end = models.DateField(null=True, blank=True)
    source_reference = models.CharField(max_length=255, blank=True, default="")
    raw_payload_ref = models.CharField(max_length=512, blank=True, default="")
    content_hash = models.CharField(max_length=64, blank=True, default="")
    source_metadata = models.JSONField(default=dict, blank=True)
    normalization_summary = models.JSONField(default=dict, blank=True)
    publication_summary = models.JSONField(default=dict, blank=True)
    last_error_code = models.CharField(max_length=64, blank=True, default="")
    last_error = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pool_batches"
        indexes = [
            models.Index(fields=["tenant", "pool", "period_start"]),
            models.Index(fields=["tenant", "batch_kind", "-created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(period_end__isnull=True) | Q(period_end__gte=F("period_start")),
                name="chk_pool_batch_period_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pool_id}:{self.batch_kind}:{self.id}"

    def clean(self) -> None:
        if self.pool_id and self.tenant_id and self.pool.tenant_id != self.tenant_id:
            raise ValidationError({"pool": "Batch pool must belong to the same tenant."})
        if self.schema_template_id and self.tenant_id and self.schema_template.tenant_id != self.tenant_id:
            raise ValidationError({"schema_template": "Schema template must belong to the same tenant."})
        if self.start_organization_id and self.tenant_id and self.start_organization.tenant_id != self.tenant_id:
            raise ValidationError(
                {"start_organization": "Start organization must belong to the same tenant."}
            )
        if self.run_id:
            if self.run.tenant_id != self.tenant_id:
                raise ValidationError({"run": "Batch run must belong to the same tenant."})
            if self.pool_id and self.run.pool_id != self.pool_id:
                raise ValidationError({"run": "Batch run must belong to the same pool."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class PoolBatchSettlementStatus(models.TextChoices):
    INGESTED = "ingested", "Ingested"
    DISTRIBUTED = "distributed", "Distributed"
    PARTIALLY_CLOSED = "partially_closed", "Partially Closed"
    CLOSED = "closed", "Closed"
    CARRIED_FORWARD = "carried_forward", "Carried Forward"
    ATTENTION_REQUIRED = "attention_required", "Attention Required"


class PoolBatchSettlement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE, related_name="pool_batch_settlements")
    batch = models.OneToOneField(
        "intercompany_pools.PoolBatch",
        on_delete=models.CASCADE,
        related_name="settlement",
    )
    status = models.CharField(
        max_length=32,
        choices=PoolBatchSettlementStatus.choices,
        default=PoolBatchSettlementStatus.INGESTED,
        db_index=True,
    )
    incoming_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    outgoing_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    open_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    summary = models.JSONField(default=dict, blank=True)
    freshness_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pool_batch_settlements"
        indexes = [
            models.Index(fields=["tenant", "status", "-updated_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.batch_id}:{self.status}"

    def clean(self) -> None:
        if self.batch_id and self.tenant_id and self.batch.tenant_id != self.tenant_id:
            raise ValidationError({"batch": "Settlement batch must belong to the same tenant."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class PoolBatchPublicationAttemptStatus(models.TextChoices):
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


class PoolBatchPublicationAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(
        "intercompany_pools.PoolBatch",
        on_delete=models.CASCADE,
        related_name="publication_attempts",
    )
    tenant = models.ForeignKey(
        "tenancy.Tenant",
        on_delete=models.CASCADE,
        related_name="pool_batch_publication_attempts",
    )
    target_database = models.ForeignKey(
        "databases.Database",
        on_delete=models.PROTECT,
        related_name="pool_batch_publication_attempts",
    )
    attempt_number = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=16, choices=PoolBatchPublicationAttemptStatus.choices, db_index=True)
    entity_name = models.CharField(max_length=255)
    documents_count = models.PositiveIntegerField(default=1)
    external_document_identity = models.CharField(max_length=128, blank=True, default="")
    identity_strategy = models.CharField(max_length=64, blank=True, default="")
    posted = models.BooleanField(default=False)
    http_status = models.IntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    request_summary = models.JSONField(default=dict, blank=True)
    response_summary = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pool_batch_publication_attempts"
        indexes = [
            models.Index(fields=["batch", "status", "-created_at"]),
            models.Index(fields=["target_database", "status", "-created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "target_database", "attempt_number"],
                name="uniq_pool_batch_publication_attempt_per_target",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.batch_id}:{self.target_database_id}#{self.attempt_number} ({self.status})"
