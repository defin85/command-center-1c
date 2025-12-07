"""CompensationAuditLog model - audit log for Saga compensation actions."""

from django.db import models


class CompensationAuditLog(models.Model):
    """
    Audit log for Saga compensation actions.
    Records all compensation executions from Go Worker for audit trail.
    """

    id = models.AutoField(primary_key=True)
    operation_id = models.CharField(max_length=64, db_index=True)
    compensation_name = models.CharField(max_length=100)
    success = models.BooleanField(default=False)
    attempts = models.IntegerField(default=1)
    duration_seconds = models.FloatField(default=0)
    error_message = models.TextField(blank=True)
    executed_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'compensation_audit_logs'
        ordering = ['-executed_at']
        indexes = [
            models.Index(fields=['operation_id', 'executed_at']),
            models.Index(fields=['success', 'executed_at']),
        ]
        verbose_name = 'Compensation Audit Log'
        verbose_name_plural = 'Compensation Audit Logs'

    def __str__(self):
        status = "OK" if self.success else "FAILED"
        return f"{self.compensation_name} [{status}] - {self.operation_id}"
