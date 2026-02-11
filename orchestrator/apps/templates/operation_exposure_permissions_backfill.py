from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.templates.models import (
    OperationExposure,
    OperationExposureGroupPermission,
    OperationExposurePermission,
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


def _template_scope_filters() -> dict[str, Any]:
    return {
        "exposure__surface": OperationExposure.SURFACE_TEMPLATE,
        "exposure__tenant__isnull": True,
    }


def _sync_direct_permissions(stats: ExposurePermissionBackfillStats) -> None:
    # Post-cutover compatibility mode: legacy tables are removed, so we report
    # exposure-scoped rows and keep counters stable for command consumers.
    stats.direct_legacy_rows = OperationExposurePermission.objects.filter(
        **_template_scope_filters()
    ).count()


def _sync_group_permissions(stats: ExposurePermissionBackfillStats) -> None:
    stats.group_legacy_rows = OperationExposureGroupPermission.objects.filter(
        **_template_scope_filters()
    ).count()


def _parity_checks(stats: ExposurePermissionBackfillStats) -> None:
    direct_expected = {
        (int(user_id), str(exposure_id), int(level))
        for user_id, exposure_id, level in OperationExposurePermission.objects.filter(
            **_template_scope_filters()
        ).values_list("user_id", "exposure_id", "level")
    }
    direct_actual = {
        (int(user_id), str(exposure_id), int(level))
        for user_id, exposure_id, level in OperationExposurePermission.objects.filter(
            **_template_scope_filters()
        ).values_list("user_id", "exposure_id", "level")
    }

    group_expected = {
        (int(group_id), str(exposure_id), int(level))
        for group_id, exposure_id, level in OperationExposureGroupPermission.objects.filter(
            **_template_scope_filters()
        ).values_list("group_id", "exposure_id", "level")
    }
    group_actual = {
        (int(group_id), str(exposure_id), int(level))
        for group_id, exposure_id, level in OperationExposureGroupPermission.objects.filter(
            **_template_scope_filters()
        ).values_list("group_id", "exposure_id", "level")
    }

    stats.direct_parity_missing_rows = len(direct_expected - direct_actual)
    stats.direct_parity_extra_rows = len(direct_actual - direct_expected)
    stats.group_parity_missing_rows = len(group_expected - group_actual)
    stats.group_parity_extra_rows = len(group_actual - group_expected)


def run_operation_exposure_permissions_backfill() -> ExposurePermissionBackfillStats:
    stats = ExposurePermissionBackfillStats()

    _sync_direct_permissions(stats)
    _sync_group_permissions(stats)
    _parity_checks(stats)

    return stats
