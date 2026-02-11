from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.templates.models import (
    OperationExposure,
    OperationExposureGroupPermission,
    OperationExposurePermission,
    OperationTemplateGroupPermission,
    OperationTemplatePermission,
)


@dataclass
class ExposurePermissionBackfillStats:
    direct_legacy_rows: int = 0
    direct_backfilled_created: int = 0
    direct_backfilled_updated: int = 0
    direct_missing_exposure: int = 0
    group_legacy_rows: int = 0
    group_backfilled_created: int = 0
    group_backfilled_updated: int = 0
    group_missing_exposure: int = 0
    direct_parity_missing_rows: int = 0
    direct_parity_extra_rows: int = 0
    group_parity_missing_rows: int = 0
    group_parity_extra_rows: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "direct_legacy_rows": self.direct_legacy_rows,
            "direct_backfilled_created": self.direct_backfilled_created,
            "direct_backfilled_updated": self.direct_backfilled_updated,
            "direct_missing_exposure": self.direct_missing_exposure,
            "group_legacy_rows": self.group_legacy_rows,
            "group_backfilled_created": self.group_backfilled_created,
            "group_backfilled_updated": self.group_backfilled_updated,
            "group_missing_exposure": self.group_missing_exposure,
            "direct_parity_missing_rows": self.direct_parity_missing_rows,
            "direct_parity_extra_rows": self.direct_parity_extra_rows,
            "group_parity_missing_rows": self.group_parity_missing_rows,
            "group_parity_extra_rows": self.group_parity_extra_rows,
            "parity_mismatches_total": self.parity_mismatches_total,
        }

    @property
    def parity_mismatches_total(self) -> int:
        return (
            self.direct_parity_missing_rows
            + self.direct_parity_extra_rows
            + self.group_parity_missing_rows
            + self.group_parity_extra_rows
        )


def _global_template_exposure_map() -> dict[str, str]:
    return {
        str(alias): str(exposure_id)
        for alias, exposure_id in OperationExposure.objects.filter(
            surface=OperationExposure.SURFACE_TEMPLATE,
            tenant__isnull=True,
        ).values_list("alias", "id")
    }


def _sync_direct_permissions(stats: ExposurePermissionBackfillStats, alias_to_exposure_id: dict[str, str]) -> None:
    queryset = OperationTemplatePermission.objects.select_related("template").all()
    stats.direct_legacy_rows = queryset.count()

    for row in queryset:
        exposure_id = alias_to_exposure_id.get(str(row.template_id))
        if not exposure_id:
            stats.direct_missing_exposure += 1
            continue

        obj, created = OperationExposurePermission.objects.get_or_create(
            user_id=row.user_id,
            exposure_id=exposure_id,
            defaults={
                "level": row.level,
                "granted_by_id": row.granted_by_id,
                "notes": row.notes,
            },
        )
        if created:
            stats.direct_backfilled_created += 1
            continue

        changed_fields: list[str] = []
        if int(obj.level) != int(row.level):
            obj.level = row.level
            changed_fields.append("level")
        if int(obj.granted_by_id or 0) != int(row.granted_by_id or 0):
            obj.granted_by_id = row.granted_by_id
            changed_fields.append("granted_by")
        if str(obj.notes or "") != str(row.notes or ""):
            obj.notes = row.notes
            changed_fields.append("notes")
        if changed_fields:
            obj.save(update_fields=changed_fields)
            stats.direct_backfilled_updated += 1


def _sync_group_permissions(stats: ExposurePermissionBackfillStats, alias_to_exposure_id: dict[str, str]) -> None:
    queryset = OperationTemplateGroupPermission.objects.select_related("template").all()
    stats.group_legacy_rows = queryset.count()

    for row in queryset:
        exposure_id = alias_to_exposure_id.get(str(row.template_id))
        if not exposure_id:
            stats.group_missing_exposure += 1
            continue

        obj, created = OperationExposureGroupPermission.objects.get_or_create(
            group_id=row.group_id,
            exposure_id=exposure_id,
            defaults={
                "level": row.level,
                "granted_by_id": row.granted_by_id,
                "notes": row.notes,
            },
        )
        if created:
            stats.group_backfilled_created += 1
            continue

        changed_fields: list[str] = []
        if int(obj.level) != int(row.level):
            obj.level = row.level
            changed_fields.append("level")
        if int(obj.granted_by_id or 0) != int(row.granted_by_id or 0):
            obj.granted_by_id = row.granted_by_id
            changed_fields.append("granted_by")
        if str(obj.notes or "") != str(row.notes or ""):
            obj.notes = row.notes
            changed_fields.append("notes")
        if changed_fields:
            obj.save(update_fields=changed_fields)
            stats.group_backfilled_updated += 1


def _parity_checks(stats: ExposurePermissionBackfillStats, alias_to_exposure_id: dict[str, str]) -> None:
    direct_expected = {
        (int(row.user_id), str(exposure_id), int(row.level))
        for row in OperationTemplatePermission.objects.all()
        for exposure_id in [alias_to_exposure_id.get(str(row.template_id))]
        if exposure_id
    }
    direct_actual = {
        (int(user_id), str(exposure_id), int(level))
        for user_id, exposure_id, level in OperationExposurePermission.objects.filter(
            exposure__surface=OperationExposure.SURFACE_TEMPLATE,
            exposure__tenant__isnull=True,
        ).values_list("user_id", "exposure_id", "level")
    }

    group_expected = {
        (int(row.group_id), str(exposure_id), int(row.level))
        for row in OperationTemplateGroupPermission.objects.all()
        for exposure_id in [alias_to_exposure_id.get(str(row.template_id))]
        if exposure_id
    }
    group_actual = {
        (int(group_id), str(exposure_id), int(level))
        for group_id, exposure_id, level in OperationExposureGroupPermission.objects.filter(
            exposure__surface=OperationExposure.SURFACE_TEMPLATE,
            exposure__tenant__isnull=True,
        ).values_list("group_id", "exposure_id", "level")
    }

    stats.direct_parity_missing_rows = len(direct_expected - direct_actual)
    stats.direct_parity_extra_rows = len(direct_actual - direct_expected)
    stats.group_parity_missing_rows = len(group_expected - group_actual)
    stats.group_parity_extra_rows = len(group_actual - group_expected)


def run_operation_exposure_permissions_backfill() -> ExposurePermissionBackfillStats:
    stats = ExposurePermissionBackfillStats()
    alias_to_exposure_id = _global_template_exposure_map()

    _sync_direct_permissions(stats, alias_to_exposure_id)
    _sync_group_permissions(stats, alias_to_exposure_id)
    _parity_checks(stats, alias_to_exposure_id)

    return stats
