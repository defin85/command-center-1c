from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .master_data_registry import normalize_pool_master_data_bootstrap_entity_type
from .models import PoolMasterDataBootstrapImportEntityType


POOL_MASTER_DATA_BOOTSTRAP_DEPENDENCY_ORDER_INVALID = "POOL_MASTER_DATA_BOOTSTRAP_DEPENDENCY_ORDER_INVALID"

BOOTSTRAP_DEPENDENCY_DECISION_READY = "ready"
BOOTSTRAP_DEPENDENCY_DECISION_DEFERRED = "deferred"
BOOTSTRAP_DEPENDENCY_DECISION_FAILED = "failed"

_DEPENDENCY_ORDER = (
    PoolMasterDataBootstrapImportEntityType.PARTY,
    PoolMasterDataBootstrapImportEntityType.ITEM,
    PoolMasterDataBootstrapImportEntityType.TAX_PROFILE,
    PoolMasterDataBootstrapImportEntityType.GL_ACCOUNT,
    PoolMasterDataBootstrapImportEntityType.CONTRACT,
    PoolMasterDataBootstrapImportEntityType.BINDING,
)


def _fail(detail: str) -> ValueError:
    return ValueError(f"{POOL_MASTER_DATA_BOOTSTRAP_DEPENDENCY_ORDER_INVALID}: {detail}")


def _normalize_bootstrap_entity_type(entity_type: str) -> str:
    try:
        return normalize_pool_master_data_bootstrap_entity_type(entity_type)
    except ValueError as exc:
        raise _fail(str(exc)) from exc


def resolve_bootstrap_import_dependency_order(*, selected_scope: Iterable[str]) -> tuple[str, ...]:
    selected = {_normalize_bootstrap_entity_type(entity_type) for entity_type in selected_scope}
    if not selected:
        raise _fail("selected_scope must contain at least one entity type")
    return tuple(entity_type for entity_type in _DEPENDENCY_ORDER if entity_type in selected)


@dataclass(frozen=True)
class BootstrapDependencyDecision:
    decision: str
    error_code: str = ""
    detail: str = ""


def evaluate_contract_dependency(
    *,
    owner_counterparty_canonical_id: str,
    resolved_party_canonical_ids: set[str],
    allow_deferred: bool,
) -> BootstrapDependencyDecision:
    normalized_owner_id = str(owner_counterparty_canonical_id or "").strip()
    if not normalized_owner_id:
        return BootstrapDependencyDecision(
            decision=BOOTSTRAP_DEPENDENCY_DECISION_FAILED,
            error_code="BOOTSTRAP_CONTRACT_OWNER_REQUIRED",
            detail="Contract row is missing owner_counterparty_canonical_id.",
        )

    if normalized_owner_id in {str(item or "").strip() for item in resolved_party_canonical_ids}:
        return BootstrapDependencyDecision(decision=BOOTSTRAP_DEPENDENCY_DECISION_READY)

    decision = BOOTSTRAP_DEPENDENCY_DECISION_DEFERRED if allow_deferred else BOOTSTRAP_DEPENDENCY_DECISION_FAILED
    return BootstrapDependencyDecision(
        decision=decision,
        error_code="BOOTSTRAP_CONTRACT_OWNER_DEPENDENCY_MISSING",
        detail=f"Owner counterparty '{normalized_owner_id}' is not resolved in party scope.",
    )


def evaluate_binding_dependency(
    *,
    target_entity_type: str,
    canonical_id: str,
    resolved_canonical_ids_by_entity: Mapping[str, set[str]],
    allow_deferred: bool,
) -> BootstrapDependencyDecision:
    normalized_target_entity = _normalize_bootstrap_entity_type(target_entity_type)
    normalized_canonical_id = str(canonical_id or "").strip()
    if not normalized_canonical_id:
        return BootstrapDependencyDecision(
            decision=BOOTSTRAP_DEPENDENCY_DECISION_FAILED,
            error_code="BOOTSTRAP_BINDING_TARGET_REQUIRED",
            detail="Binding row is missing canonical target reference.",
        )

    resolved_by_entity = {
        _normalize_bootstrap_entity_type(entity): {str(value or "").strip() for value in values}
        for entity, values in resolved_canonical_ids_by_entity.items()
    }
    resolved_ids = resolved_by_entity.get(normalized_target_entity, set())
    if normalized_canonical_id in resolved_ids:
        return BootstrapDependencyDecision(decision=BOOTSTRAP_DEPENDENCY_DECISION_READY)

    decision = BOOTSTRAP_DEPENDENCY_DECISION_DEFERRED if allow_deferred else BOOTSTRAP_DEPENDENCY_DECISION_FAILED
    return BootstrapDependencyDecision(
        decision=decision,
        error_code="BOOTSTRAP_BINDING_TARGET_DEPENDENCY_MISSING",
        detail=(
            "Binding target canonical ID is not resolved for "
            f"entity '{normalized_target_entity}' and canonical_id '{normalized_canonical_id}'."
        ),
    )
