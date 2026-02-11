from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.operations.models import BatchOperation
from apps.templates.models import OperationExposure


@dataclass
class TemplateMetadataBackfillStats:
    scanned_operations: int = 0
    operations_with_template_ref: int = 0
    updated_operations: int = 0
    missing_exposure: int = 0
    source_template_fk: int = 0
    source_metadata_template_id: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned_operations": self.scanned_operations,
            "operations_with_template_ref": self.operations_with_template_ref,
            "updated_operations": self.updated_operations,
            "missing_exposure": self.missing_exposure,
            "source_template_fk": self.source_template_fk,
            "source_metadata_template_id": self.source_metadata_template_id,
        }


def _template_alias_to_exposure_id_map() -> dict[str, str]:
    return {
        str(alias): str(exposure_id)
        for alias, exposure_id in OperationExposure.objects.filter(
            surface=OperationExposure.SURFACE_TEMPLATE,
            tenant__isnull=True,
        ).values_list("alias", "id")
    }


def run_template_metadata_backfill() -> TemplateMetadataBackfillStats:
    stats = TemplateMetadataBackfillStats()
    alias_to_exposure_id = _template_alias_to_exposure_id_map()

    stats.scanned_operations = BatchOperation.objects.count()

    queryset = BatchOperation.objects.only("id", "template_id", "metadata").iterator()
    for operation in queryset:
        metadata = dict(operation.metadata) if isinstance(operation.metadata, dict) else {}
        template_alias = ""

        if operation.template_id:
            template_alias = str(operation.template_id).strip()
            stats.source_template_fk += 1
        else:
            template_alias = str(metadata.get("template_id") or "").strip()
            if template_alias:
                stats.source_metadata_template_id += 1

        if not template_alias:
            continue

        stats.operations_with_template_ref += 1
        changed = False

        if str(metadata.get("template_id") or "") != template_alias:
            metadata["template_id"] = template_alias
            changed = True

        exposure_id = alias_to_exposure_id.get(template_alias)
        if exposure_id:
            if str(metadata.get("template_exposure_id") or "") != exposure_id:
                metadata["template_exposure_id"] = exposure_id
                changed = True
        else:
            stats.missing_exposure += 1

        if changed:
            operation.metadata = metadata
            operation.save(update_fields=["metadata", "updated_at"])
            stats.updated_operations += 1

    return stats
