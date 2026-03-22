from __future__ import annotations

from typing import Any

from apps.intercompany_pools.models import PoolWorkflowBinding
from apps.intercompany_pools.workflow_binding_attachments_store import (
    POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING,
)
from apps.tenancy.models import Tenant


def build_binding_profile_usage_summary(
    *,
    tenant: Tenant,
    binding_profile_id: str,
) -> dict[str, Any]:
    records = list(
        PoolWorkflowBinding.objects.filter(
            tenant=tenant,
            binding_profile_id=binding_profile_id,
        )
        .select_related("pool", "binding_profile_revision")
        .order_by("pool__code", "effective_from", "created_at", "binding_id")
    )
    attachments = [_serialize_usage_attachment(record) for record in records]
    revision_totals: dict[tuple[str, int | None], int] = {}
    for attachment in attachments:
        key = (
            attachment["binding_profile_revision_id"],
            attachment["binding_profile_revision_number"],
        )
        revision_totals[key] = revision_totals.get(key, 0) + 1
    revision_summary = [
        {
            "binding_profile_revision_id": binding_profile_revision_id,
            "binding_profile_revision_number": binding_profile_revision_number,
            "attachment_count": attachment_count,
        }
        for (
            binding_profile_revision_id,
            binding_profile_revision_number,
        ), attachment_count in revision_totals.items()
    ]
    revision_summary.sort(
        key=lambda item: (
            -(item["binding_profile_revision_number"] or 0),
            str(item["binding_profile_revision_id"]),
        )
    )
    return {
        "attachment_count": len(attachments),
        "revision_summary": revision_summary,
        "attachments": attachments,
    }


def _serialize_usage_attachment(record: PoolWorkflowBinding) -> dict[str, Any]:
    if record.binding_profile_revision is None or not record.binding_profile_revision_id:
        from apps.intercompany_pools.binding_profiles_store import BindingProfileStoreError

        raise BindingProfileStoreError(
            f"{POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING}: "
            f"Workflow binding '{record.binding_id}' is missing binding_profile references."
        )
    return {
        "pool_id": str(record.pool_id),
        "pool_code": record.pool.code,
        "pool_name": record.pool.name,
        "binding_id": record.binding_id,
        "attachment_revision": record.revision,
        "binding_profile_revision_id": record.binding_profile_revision_id,
        "binding_profile_revision_number": record.binding_profile_revision.revision_number,
        "status": record.status,
        "selector": {
            "direction": record.direction or None,
            "mode": record.mode or None,
            "tags": list(record.selector_tags),
        },
        "effective_from": record.effective_from.isoformat(),
        "effective_to": record.effective_to.isoformat() if record.effective_to else None,
    }


__all__ = ["build_binding_profile_usage_summary"]
