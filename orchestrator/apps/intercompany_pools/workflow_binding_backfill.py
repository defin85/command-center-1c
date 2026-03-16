from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.intercompany_pools.document_policy_contract import DOCUMENT_POLICY_METADATA_KEY
from apps.intercompany_pools.models import OrganizationPool
from apps.intercompany_pools.workflow_bindings_store import (
    PoolWorkflowBindingStoreError,
    extract_pool_workflow_bindings,
    list_canonical_pool_workflow_bindings,
    normalize_pool_workflow_bindings_for_storage,
    upsert_canonical_pool_workflow_binding,
)


BACKFILL_ACTOR_USERNAME = "system:pool_workflow_binding_metadata_backfill"

REMEDIATION_REASON_INVALID_LEGACY_BINDING = "invalid_legacy_binding"
REMEDIATION_REASON_CONFLICTING_CANONICAL_BINDING = "conflicting_canonical_binding"
REMEDIATION_REASON_CANONICAL_ONLY_BINDING = "canonical_only_binding"


@dataclass(frozen=True)
class PoolWorkflowBindingBackfillRemediationItem:
    tenant_id: str
    pool_id: str
    pool_code: str
    reason: str
    binding_id: str
    detail: str = ""
    legacy_binding: dict[str, Any] | None = None
    canonical_binding: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "tenant_id": self.tenant_id,
            "pool_id": self.pool_id,
            "pool_code": self.pool_code,
            "reason": self.reason,
            "binding_id": self.binding_id,
            "detail": self.detail,
        }
        if self.legacy_binding is not None:
            payload["legacy_binding"] = dict(self.legacy_binding)
        if self.canonical_binding is not None:
            payload["canonical_binding"] = dict(self.canonical_binding)
        return payload


@dataclass
class PoolWorkflowBindingBackfillStats:
    pools_scanned: int = 0
    pools_with_legacy_bindings: int = 0
    pools_backfilled: int = 0
    pools_already_imported: int = 0
    pools_invalid_legacy: int = 0
    pools_conflicted: int = 0
    legacy_bindings_seen: int = 0
    canonical_created: int = 0
    canonical_unchanged: int = 0
    remediation_list: list[PoolWorkflowBindingBackfillRemediationItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "pools_scanned": self.pools_scanned,
            "pools_with_legacy_bindings": self.pools_with_legacy_bindings,
            "pools_backfilled": self.pools_backfilled,
            "pools_already_imported": self.pools_already_imported,
            "pools_invalid_legacy": self.pools_invalid_legacy,
            "pools_conflicted": self.pools_conflicted,
            "legacy_bindings_seen": self.legacy_bindings_seen,
            "canonical_created": self.canonical_created,
            "canonical_unchanged": self.canonical_unchanged,
            "remediation_count": len(self.remediation_list),
            "remediation_list": [item.to_dict() for item in self.remediation_list],
        }


def run_pool_workflow_binding_backfill(
    *,
    actor_username: str = BACKFILL_ACTOR_USERNAME,
) -> PoolWorkflowBindingBackfillStats:
    stats = PoolWorkflowBindingBackfillStats()

    pools = OrganizationPool.objects.select_related("tenant").order_by("tenant_id", "code", "id")
    for pool in pools.iterator():
        stats.pools_scanned += 1
        metadata = pool.metadata if isinstance(pool.metadata, dict) else {}
        raw_bindings = _upgrade_legacy_document_policy_slots(
            extract_pool_workflow_bindings(metadata)
        )
        if not raw_bindings:
            continue

        stats.pools_with_legacy_bindings += 1
        stats.legacy_bindings_seen += len(raw_bindings)

        try:
            normalized_bindings = normalize_pool_workflow_bindings_for_storage(
                pool_id=str(pool.id),
                workflow_bindings=raw_bindings,
            )
        except PoolWorkflowBindingStoreError as exc:
            stats.pools_invalid_legacy += 1
            _append_remediation(
                stats=stats,
                pool=pool,
                reason=REMEDIATION_REASON_INVALID_LEGACY_BINDING,
                detail=str(exc),
            )
            continue

        canonical_by_id = {
            str(binding["binding_id"]): binding
            for binding in list_canonical_pool_workflow_bindings(pool=pool)
        }
        normalized_by_id = {
            str(binding["binding_id"]): binding
            for binding in normalized_bindings
        }

        if _collect_pool_conflicts(
            stats=stats,
            pool=pool,
            canonical_by_id=canonical_by_id,
            normalized_by_id=normalized_by_id,
        ):
            stats.pools_conflicted += 1
            continue

        created_count = 0
        unchanged_count = 0
        for binding_id, normalized_binding in normalized_by_id.items():
            if binding_id in canonical_by_id:
                unchanged_count += 1
                continue
            _, created = upsert_canonical_pool_workflow_binding(
                pool=pool,
                workflow_binding=normalized_binding,
                actor_username=actor_username,
            )
            if created:
                created_count += 1

        stats.canonical_created += created_count
        stats.canonical_unchanged += unchanged_count
        if created_count > 0:
            stats.pools_backfilled += 1
        else:
            stats.pools_already_imported += 1

    return stats


def _upgrade_legacy_document_policy_slots(
    raw_bindings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    upgraded_bindings: list[dict[str, Any]] = []
    for binding in raw_bindings:
        payload = dict(binding)
        decisions = payload.get("decisions")
        if not isinstance(decisions, list):
            upgraded_bindings.append(payload)
            continue
        upgraded_decisions: list[Any] = []
        for raw_decision in decisions:
            if not isinstance(raw_decision, dict):
                upgraded_decisions.append(raw_decision)
                continue
            decision = dict(raw_decision)
            if (
                str(decision.get("decision_key") or "").strip() == DOCUMENT_POLICY_METADATA_KEY
                and not str(decision.get("slot_key") or "").strip()
            ):
                decision["slot_key"] = DOCUMENT_POLICY_METADATA_KEY
            upgraded_decisions.append(decision)
        payload["decisions"] = upgraded_decisions
        upgraded_bindings.append(payload)
    return upgraded_bindings


def _collect_pool_conflicts(
    *,
    stats: PoolWorkflowBindingBackfillStats,
    pool: OrganizationPool,
    canonical_by_id: dict[str, dict[str, Any]],
    normalized_by_id: dict[str, dict[str, Any]],
) -> bool:
    conflicted = False

    for binding_id, canonical_binding in canonical_by_id.items():
        legacy_binding = normalized_by_id.get(binding_id)
        if legacy_binding is None:
            conflicted = True
            _append_remediation(
                stats=stats,
                pool=pool,
                reason=REMEDIATION_REASON_CANONICAL_ONLY_BINDING,
                binding_id=binding_id,
                detail="canonical binding exists without matching legacy metadata binding",
                canonical_binding=canonical_binding,
            )
            continue
        if not _bindings_match_ignoring_revision(
            canonical_binding=canonical_binding,
            legacy_binding=legacy_binding,
        ):
            conflicted = True
            _append_remediation(
                stats=stats,
                pool=pool,
                reason=REMEDIATION_REASON_CONFLICTING_CANONICAL_BINDING,
                binding_id=binding_id,
                detail="legacy metadata binding does not match canonical binding payload",
                legacy_binding=legacy_binding,
                canonical_binding=canonical_binding,
            )

    return conflicted


def _bindings_match_ignoring_revision(
    *,
    canonical_binding: dict[str, Any],
    legacy_binding: dict[str, Any],
) -> bool:
    normalized_canonical = dict(canonical_binding)
    normalized_canonical.pop("revision", None)
    return normalized_canonical == legacy_binding


def _append_remediation(
    *,
    stats: PoolWorkflowBindingBackfillStats,
    pool: OrganizationPool,
    reason: str,
    binding_id: str = "",
    detail: str = "",
    legacy_binding: dict[str, Any] | None = None,
    canonical_binding: dict[str, Any] | None = None,
) -> None:
    stats.remediation_list.append(
        PoolWorkflowBindingBackfillRemediationItem(
            tenant_id=str(pool.tenant_id),
            pool_id=str(pool.id),
            pool_code=str(pool.code),
            reason=reason,
            binding_id=binding_id,
            detail=detail,
            legacy_binding=legacy_binding,
            canonical_binding=canonical_binding,
        )
    )


__all__ = [
    "BACKFILL_ACTOR_USERNAME",
    "PoolWorkflowBindingBackfillRemediationItem",
    "PoolWorkflowBindingBackfillStats",
    "REMEDIATION_REASON_CANONICAL_ONLY_BINDING",
    "REMEDIATION_REASON_CONFLICTING_CANONICAL_BINDING",
    "REMEDIATION_REASON_INVALID_LEGACY_BINDING",
    "run_pool_workflow_binding_backfill",
]
