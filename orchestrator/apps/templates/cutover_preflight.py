from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import connection
from django.db.models import Count
from django.utils import timezone

from apps.templates.models import (
    OperationExposure,
    OperationExposureGroupPermission,
    OperationExposurePermission,
)


@dataclass(frozen=True)
class PreflightCheck:
    key: str
    description: str
    mismatches: int
    critical: bool
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "description": self.description,
            "mismatches": int(self.mismatches),
            "critical": bool(self.critical),
            "details": dict(self.details),
            "status": "pass" if int(self.mismatches) == 0 else "fail",
        }


def _count_batch_template_metadata_orphans() -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM batch_operations bo
            WHERE NULLIF(TRIM(COALESCE(bo.metadata->>'template_id', '')), '') IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM operation_exposures oe
                  WHERE oe.surface = %s
                    AND oe.tenant_id IS NULL
                    AND oe.alias = TRIM(bo.metadata->>'template_id')
              )
            """,
            [OperationExposure.SURFACE_TEMPLATE],
        )
        row = cursor.fetchone()
    return int(row[0] if row else 0)


def _count_template_exposure_payload_mismatches() -> int:
    mismatches = 0
    exposures = OperationExposure.objects.select_related("definition").filter(
        surface=OperationExposure.SURFACE_TEMPLATE,
        tenant__isnull=True,
    )
    for exposure in exposures.iterator():
        payload = exposure.definition.executor_payload if isinstance(exposure.definition.executor_payload, dict) else {}
        operation_type = str(payload.get("operation_type") or exposure.definition.executor_kind or "").strip()
        template_data = payload.get("template_data")
        if not operation_type or not isinstance(template_data, dict):
            mismatches += 1
    return mismatches


def run_operation_exposure_cutover_preflight() -> dict[str, Any]:
    template_surface = OperationExposure.SURFACE_TEMPLATE

    global_alias_duplicates = (
        OperationExposure.objects.filter(surface=template_surface, tenant__isnull=True)
        .values("alias")
        .annotate(cnt=Count("id"))
        .filter(cnt__gt=1)
        .count()
    )
    tenant_alias_duplicates = (
        OperationExposure.objects.filter(surface=template_surface, tenant__isnull=False)
        .values("tenant_id", "alias")
        .annotate(cnt=Count("id"))
        .filter(cnt__gt=1)
        .count()
    )

    direct_permissions_out_of_scope = OperationExposurePermission.objects.exclude(
        exposure__surface=template_surface,
        exposure__tenant__isnull=True,
    ).count()
    group_permissions_out_of_scope = OperationExposureGroupPermission.objects.exclude(
        exposure__surface=template_surface,
        exposure__tenant__isnull=True,
    ).count()

    checks = [
        PreflightCheck(
            key="template_alias_uniqueness_global",
            description="Global template aliases must be unique.",
            mismatches=global_alias_duplicates,
            critical=True,
            details={"surface": template_surface, "tenant_scope": "global"},
        ),
        PreflightCheck(
            key="template_alias_uniqueness_tenant",
            description="Tenant template aliases must be unique per tenant.",
            mismatches=tenant_alias_duplicates,
            critical=True,
            details={"surface": template_surface, "tenant_scope": "tenant"},
        ),
        PreflightCheck(
            key="template_exposure_payload_contract",
            description="Each global template exposure must contain operation_type and template_data in definition payload.",
            mismatches=_count_template_exposure_payload_mismatches(),
            critical=True,
            details={},
        ),
        PreflightCheck(
            key="direct_permission_targets_template_exposure",
            description="Each direct template permission must target global template exposure.",
            mismatches=direct_permissions_out_of_scope,
            critical=True,
            details={},
        ),
        PreflightCheck(
            key="group_permission_targets_template_exposure",
            description="Each group template permission must target global template exposure.",
            mismatches=group_permissions_out_of_scope,
            critical=True,
            details={},
        ),
        PreflightCheck(
            key="batch_operation_template_fk_orphans",
            description="batch_operations.metadata.template_id must not contain orphan exposure aliases.",
            mismatches=_count_batch_template_metadata_orphans(),
            critical=True,
            details={},
        ),
    ]

    total_critical_mismatches = sum(
        int(item.mismatches) for item in checks if item.critical
    )
    total_mismatches = sum(int(item.mismatches) for item in checks)

    return {
        "generated_at": timezone.now().isoformat(),
        "summary": {
            "template_exposures_total": OperationExposure.objects.filter(
                surface=template_surface,
                tenant__isnull=True,
            ).count(),
            "template_definitions_total": OperationExposure.objects.filter(
                surface=template_surface,
                tenant__isnull=True,
            )
            .values("definition_id")
            .distinct()
            .count(),
            "direct_permissions_total": OperationExposurePermission.objects.filter(
                exposure__surface=template_surface,
                exposure__tenant__isnull=True,
            ).count(),
            "group_permissions_total": OperationExposureGroupPermission.objects.filter(
                exposure__surface=template_surface,
                exposure__tenant__isnull=True,
            ).count(),
            "total_checks": len(checks),
            "total_mismatches": total_mismatches,
            "total_critical_mismatches": total_critical_mismatches,
        },
        "checks": [item.to_dict() for item in checks],
    }
