from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class PoolFactualBalanceSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenancy.Tenant",
        on_delete=models.CASCADE,
        related_name="pool_factual_balance_snapshots",
    )
    pool = models.ForeignKey(
        "intercompany_pools.OrganizationPool",
        on_delete=models.PROTECT,
        related_name="factual_balance_snapshots",
    )
    batch = models.ForeignKey(
        "intercompany_pools.PoolBatch",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="factual_balance_snapshots",
    )
    organization = models.ForeignKey(
        "intercompany_pools.Organization",
        on_delete=models.PROTECT,
        related_name="factual_balance_snapshots",
    )
    edge = models.ForeignKey(
        "intercompany_pools.PoolEdgeVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="factual_balance_snapshots",
    )
    quarter_start = models.DateField(db_index=True)
    quarter_end = models.DateField(db_index=True)
    amount_with_vat = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    amount_without_vat = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    vat_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    incoming_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    outgoing_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    open_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    freshness_at = models.DateTimeField(null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pool_factual_balance_snapshots"
        indexes = [
            models.Index(fields=["tenant", "pool", "quarter_start"]),
            models.Index(fields=["tenant", "organization", "quarter_start"]),
            models.Index(fields=["tenant", "batch", "quarter_start"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(quarter_end__gte=F("quarter_start")),
                name="chk_pool_factual_balance_quarter_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pool_id}:{self.organization_id}:{self.quarter_start}"

    def clean(self) -> None:
        if self.pool_id and self.tenant_id and self.pool.tenant_id != self.tenant_id:
            raise ValidationError({"pool": "Projection pool must belong to the same tenant."})
        if self.batch_id:
            if self.batch.tenant_id != self.tenant_id:
                raise ValidationError({"batch": "Projection batch must belong to the same tenant."})
            if self.pool_id and self.batch.pool_id != self.pool_id:
                raise ValidationError({"batch": "Projection batch must belong to the same pool."})
        if self.organization_id and self.tenant_id and self.organization.tenant_id != self.tenant_id:
            raise ValidationError({"organization": "Projection organization must belong to the same tenant."})
        if self.edge_id and self.pool_id and self.edge.pool_id != self.pool_id:
            raise ValidationError({"edge": "Projection edge must belong to the same pool."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class PoolFactualLane(models.TextChoices):
    READ = "read", "Read"
    RECONCILE = "reconcile", "Reconcile"


class PoolFactualScopeSelection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenancy.Tenant",
        on_delete=models.CASCADE,
        related_name="pool_factual_scope_selections",
    )
    pool = models.ForeignKey(
        "intercompany_pools.OrganizationPool",
        on_delete=models.CASCADE,
        related_name="factual_scope_selections",
    )
    source_profile = models.CharField(max_length=64, db_index=True)
    quarter_start = models.DateField(db_index=True)
    quarter_end = models.DateField(db_index=True)
    gl_account_set = models.ForeignKey(
        "intercompany_pools.PoolMasterGLAccountSet",
        on_delete=models.PROTECT,
        related_name="factual_scope_selections",
    )
    gl_account_set_revision = models.ForeignKey(
        "intercompany_pools.PoolMasterGLAccountSetRevision",
        on_delete=models.PROTECT,
        related_name="factual_scope_selections",
    )
    selection_mode = models.CharField(max_length=32, default="system_managed", db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pool_factual_scope_selections"
        indexes = [
            models.Index(fields=["tenant", "pool", "source_profile", "quarter_start"]),
            models.Index(fields=["tenant", "gl_account_set_revision"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(quarter_end__gte=F("quarter_start")),
                name="chk_pool_factual_scope_selection_quarter_range",
            ),
            models.UniqueConstraint(
                fields=["tenant", "pool", "source_profile", "quarter_start"],
                name="uniq_pool_factual_scope_selection",
            ),
        ]

    def clean(self) -> None:
        if self.pool_id and self.tenant_id and self.pool.tenant_id != self.tenant_id:
            raise ValidationError({"pool": "Factual scope selection pool must belong to the same tenant."})
        if self.gl_account_set_id and self.tenant_id and self.gl_account_set.tenant_id != self.tenant_id:
            raise ValidationError(
                {"gl_account_set": "Factual scope selection GLAccountSet must belong to the same tenant."}
            )
        if (
            self.gl_account_set_revision_id
            and self.tenant_id
            and self.gl_account_set_revision.tenant_id != self.tenant_id
        ):
            raise ValidationError(
                {
                    "gl_account_set_revision": (
                        "Factual scope selection GLAccountSet revision must belong to the same tenant."
                    )
                }
            )
        if (
            self.gl_account_set_id
            and self.gl_account_set_revision_id
            and self.gl_account_set_revision.profile_id != self.gl_account_set_id
        ):
            raise ValidationError(
                {
                    "gl_account_set_revision": (
                        "Factual scope selection revision must belong to the selected GLAccountSet."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class PoolFactualSyncCheckpoint(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenancy.Tenant",
        on_delete=models.CASCADE,
        related_name="pool_factual_sync_checkpoints",
    )
    pool = models.ForeignKey(
        "intercompany_pools.OrganizationPool",
        on_delete=models.PROTECT,
        related_name="factual_sync_checkpoints",
    )
    batch = models.ForeignKey(
        "intercompany_pools.PoolBatch",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="factual_sync_checkpoints",
    )
    database = models.ForeignKey(
        "databases.Database",
        on_delete=models.PROTECT,
        related_name="pool_factual_sync_checkpoints",
    )
    lane = models.CharField(max_length=16, choices=PoolFactualLane.choices, db_index=True)
    workflow_execution_id = models.UUIDField(null=True, blank=True, db_index=True)
    operation_id = models.UUIDField(null=True, blank=True, db_index=True)
    workflow_status = models.CharField(max_length=32, blank=True, default="", db_index=True)
    quarter_start = models.DateField(db_index=True)
    quarter_end = models.DateField(db_index=True)
    scope_fingerprint = models.CharField(max_length=64, blank=True, default="", db_index=True)
    source_checkpoint_token = models.CharField(max_length=255, blank=True, default="")
    last_synced_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_error_code = models.CharField(max_length=64, blank=True, default="")
    last_error = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pool_factual_sync_checkpoints"
        indexes = [
            models.Index(fields=["tenant", "lane", "quarter_start"]),
            models.Index(fields=["tenant", "database", "lane"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(quarter_end__gte=F("quarter_start")),
                name="chk_pool_factual_checkpoint_quarter_range",
            ),
            models.UniqueConstraint(
                fields=["tenant", "pool", "database", "lane", "quarter_start", "scope_fingerprint"],
                condition=~Q(scope_fingerprint=""),
                name="uniq_pool_factual_checkpoint_scope_fingerprint",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pool_id}:{self.database_id}:{self.lane}"

    def clean(self) -> None:
        if self.pool_id and self.tenant_id and self.pool.tenant_id != self.tenant_id:
            raise ValidationError({"pool": "Checkpoint pool must belong to the same tenant."})
        if self.database_id and self.tenant_id and self.database.tenant_id != self.tenant_id:
            raise ValidationError({"database": "Checkpoint database must belong to the same tenant."})
        if self.batch_id:
            if self.batch.tenant_id != self.tenant_id:
                raise ValidationError({"batch": "Checkpoint batch must belong to the same tenant."})
            if self.pool_id and self.batch.pool_id != self.pool_id:
                raise ValidationError({"batch": "Checkpoint batch must belong to the same pool."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
