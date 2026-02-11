from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import connection
from django.db.models import Count
from django.utils import timezone

from apps.templates.models import (
    OperationExposure,
    OperationTemplate,
    OperationTemplateGroupPermission,
    OperationTemplatePermission,
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


def _count_batch_template_fk_orphans() -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM batch_operations bo
            LEFT JOIN operation_templates ot ON ot.id = bo.template_id
            WHERE bo.template_id IS NOT NULL
              AND ot.id IS NULL
            """
        )
        row = cursor.fetchone()
    return int(row[0] if row else 0)


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

    exposure_aliases_qs = OperationExposure.objects.filter(
        surface=template_surface,
        tenant__isnull=True,
    ).values_list("alias", flat=True)

    legacy_templates_without_exposure = OperationTemplate.objects.exclude(
        id__in=exposure_aliases_qs
    ).count()
    exposures_without_legacy_template = OperationExposure.objects.filter(
        surface=template_surface,
        tenant__isnull=True,
    ).exclude(alias__in=OperationTemplate.objects.values_list("id", flat=True)).count()

    direct_permissions_without_exposure = OperationTemplatePermission.objects.exclude(
        template__id__in=exposure_aliases_qs
    ).count()
    group_permissions_without_exposure = OperationTemplateGroupPermission.objects.exclude(
        template__id__in=exposure_aliases_qs
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
            key="legacy_template_has_exposure",
            description="Each legacy OperationTemplate must have a global template exposure alias.",
            mismatches=legacy_templates_without_exposure,
            critical=True,
            details={},
        ),
        PreflightCheck(
            key="exposure_has_legacy_template",
            description="Each global template exposure alias must map to legacy OperationTemplate before contract.",
            mismatches=exposures_without_legacy_template,
            critical=True,
            details={},
        ),
        PreflightCheck(
            key="legacy_direct_permission_has_exposure",
            description="Each legacy direct template permission must map to template exposure alias.",
            mismatches=direct_permissions_without_exposure,
            critical=True,
            details={},
        ),
        PreflightCheck(
            key="legacy_group_permission_has_exposure",
            description="Each legacy group template permission must map to template exposure alias.",
            mismatches=group_permissions_without_exposure,
            critical=True,
            details={},
        ),
        PreflightCheck(
            key="batch_operation_template_fk_orphans",
            description="batch_operations.template_id must not contain orphan references.",
            mismatches=_count_batch_template_fk_orphans(),
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
            "templates_total": OperationTemplate.objects.count(),
            "template_exposures_total": OperationExposure.objects.filter(
                surface=template_surface,
                tenant__isnull=True,
            ).count(),
            "legacy_direct_permissions_total": OperationTemplatePermission.objects.count(),
            "legacy_group_permissions_total": OperationTemplateGroupPermission.objects.count(),
            "total_checks": len(checks),
            "total_mismatches": total_mismatches,
            "total_critical_mismatches": total_critical_mismatches,
        },
        "checks": [item.to_dict() for item in checks],
    }

