from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


User = get_user_model()


class PoolFactualReviewReason(models.TextChoices):
    UNATTRIBUTED = "unattributed", "Unattributed"
    LATE_CORRECTION = "late_correction", "Late Correction"


class PoolFactualReviewStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ATTRIBUTED = "attributed", "Attributed"
    RECONCILED = "reconciled", "Reconciled"
    RESOLVED_WITHOUT_CHANGE = "resolved_without_change", "Resolved Without Change"


class PoolFactualReviewItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenancy.Tenant",
        on_delete=models.CASCADE,
        related_name="pool_factual_review_items",
    )
    pool = models.ForeignKey(
        "intercompany_pools.OrganizationPool",
        on_delete=models.PROTECT,
        related_name="factual_review_items",
    )
    batch = models.ForeignKey(
        "intercompany_pools.PoolBatch",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="factual_review_items",
    )
    organization = models.ForeignKey(
        "intercompany_pools.Organization",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="factual_review_items",
    )
    edge = models.ForeignKey(
        "intercompany_pools.PoolEdgeVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="factual_review_items",
    )
    quarter_start = models.DateField(db_index=True)
    quarter_end = models.DateField(db_index=True)
    reason = models.CharField(max_length=32, choices=PoolFactualReviewReason.choices, db_index=True)
    status = models.CharField(
        max_length=32,
        choices=PoolFactualReviewStatus.choices,
        default=PoolFactualReviewStatus.PENDING,
        db_index=True,
    )
    source_document_ref = models.CharField(max_length=512, blank=True, default="")
    delta_payload = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_pool_factual_review_items",
    )
    resolved_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pool_factual_review_items"
        indexes = [
            models.Index(fields=["tenant", "status", "-created_at"]),
            models.Index(fields=["tenant", "reason", "-created_at"]),
            models.Index(fields=["tenant", "pool", "quarter_start"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(quarter_end__gte=F("quarter_start")),
                name="chk_pool_factual_review_quarter_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pool_id}:{self.reason}:{self.status}"

    def clean(self) -> None:
        if self.pool_id and self.tenant_id and self.pool.tenant_id != self.tenant_id:
            raise ValidationError({"pool": "Review item pool must belong to the same tenant."})
        if self.batch_id:
            if self.batch.tenant_id != self.tenant_id:
                raise ValidationError({"batch": "Review item batch must belong to the same tenant."})
            if self.pool_id and self.batch.pool_id != self.pool_id:
                raise ValidationError({"batch": "Review item batch must belong to the same pool."})
        if self.organization_id and self.tenant_id and self.organization.tenant_id != self.tenant_id:
            raise ValidationError({"organization": "Review item organization must belong to the same tenant."})
        if self.edge_id and self.pool_id and self.edge.pool_id != self.pool_id:
            raise ValidationError({"edge": "Review item edge must belong to the same pool."})
        if self.status != PoolFactualReviewStatus.PENDING and self.resolved_at is None:
            raise ValidationError(
                {"resolved_at": "Resolved factual review items must record resolved_at timestamp."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
