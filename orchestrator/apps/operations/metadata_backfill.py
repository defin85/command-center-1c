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


def _template_alias_to_exposure_ref_map() -> dict[str, tuple[str, int]]:
    return {
        str(alias): (
            str(exposure_id),
            int(contract_version) if int(contract_version or 1) >= 1 else 1,
        )
        for alias, exposure_id, contract_version in OperationExposure.objects.filter(
            surface=OperationExposure.SURFACE_TEMPLATE,
            tenant__isnull=True,
        ).values_list("alias", "id", "definition__contract_version")
    }


def run_template_metadata_backfill() -> TemplateMetadataBackfillStats:
    stats = TemplateMetadataBackfillStats()
    alias_to_exposure_ref = _template_alias_to_exposure_ref_map()

    stats.scanned_operations = BatchOperation.objects.count()

    queryset = BatchOperation.objects.only("id", "metadata").iterator()
    for operation in queryset:
        metadata = dict(operation.metadata) if isinstance(operation.metadata, dict) else {}
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

        exposure_ref = alias_to_exposure_ref.get(template_alias)
        if exposure_ref:
            exposure_id, exposure_revision = exposure_ref
            if str(metadata.get("template_exposure_id") or "") != exposure_id:
                metadata["template_exposure_id"] = exposure_id
                changed = True
            try:
                current_revision = int(metadata.get("template_exposure_revision") or 0)
            except (TypeError, ValueError):
                current_revision = 0
            if current_revision != exposure_revision:
                metadata["template_exposure_revision"] = exposure_revision
                changed = True
        else:
            stats.missing_exposure += 1

        if changed:
            operation.metadata = metadata
            operation.save(update_fields=["metadata", "updated_at"])
            stats.updated_operations += 1

    return stats
