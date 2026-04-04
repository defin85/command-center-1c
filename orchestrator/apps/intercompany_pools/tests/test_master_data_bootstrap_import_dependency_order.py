from __future__ import annotations

import pytest

from apps.intercompany_pools.master_data_bootstrap_import_dependency_order import (
    BOOTSTRAP_DEPENDENCY_DECISION_DEFERRED,
    BOOTSTRAP_DEPENDENCY_DECISION_FAILED,
    BOOTSTRAP_DEPENDENCY_DECISION_READY,
    evaluate_binding_dependency,
    evaluate_contract_dependency,
    resolve_bootstrap_import_dependency_order,
)
from apps.intercompany_pools.models import PoolMasterDataBootstrapImportEntityType


def test_resolve_bootstrap_import_dependency_order_is_deterministic() -> None:
    order = resolve_bootstrap_import_dependency_order(
        selected_scope=[
            PoolMasterDataBootstrapImportEntityType.BINDING,
            PoolMasterDataBootstrapImportEntityType.PARTY,
            PoolMasterDataBootstrapImportEntityType.GL_ACCOUNT,
            PoolMasterDataBootstrapImportEntityType.CONTRACT,
        ]
    )
    assert order == (
        PoolMasterDataBootstrapImportEntityType.PARTY,
        PoolMasterDataBootstrapImportEntityType.GL_ACCOUNT,
        PoolMasterDataBootstrapImportEntityType.CONTRACT,
        PoolMasterDataBootstrapImportEntityType.BINDING,
    )


def test_evaluate_contract_dependency_returns_deferred_for_missing_owner() -> None:
    decision = evaluate_contract_dependency(
        owner_counterparty_canonical_id="party-missing",
        resolved_party_canonical_ids={"party-001"},
        allow_deferred=True,
    )
    assert decision.decision == BOOTSTRAP_DEPENDENCY_DECISION_DEFERRED
    assert decision.error_code == "BOOTSTRAP_CONTRACT_OWNER_DEPENDENCY_MISSING"


def test_evaluate_contract_dependency_returns_failed_for_missing_owner_when_deferred_disabled() -> None:
    decision = evaluate_contract_dependency(
        owner_counterparty_canonical_id="party-missing",
        resolved_party_canonical_ids={"party-001"},
        allow_deferred=False,
    )
    assert decision.decision == BOOTSTRAP_DEPENDENCY_DECISION_FAILED
    assert decision.error_code == "BOOTSTRAP_CONTRACT_OWNER_DEPENDENCY_MISSING"


def test_evaluate_contract_dependency_returns_failed_for_empty_owner() -> None:
    decision = evaluate_contract_dependency(
        owner_counterparty_canonical_id="",
        resolved_party_canonical_ids={"party-001"},
        allow_deferred=True,
    )
    assert decision.decision == BOOTSTRAP_DEPENDENCY_DECISION_FAILED
    assert decision.error_code == "BOOTSTRAP_CONTRACT_OWNER_REQUIRED"


def test_evaluate_binding_dependency_returns_ready_for_resolved_target() -> None:
    decision = evaluate_binding_dependency(
        target_entity_type=PoolMasterDataBootstrapImportEntityType.ITEM,
        canonical_id="item-001",
        resolved_canonical_ids_by_entity={
            PoolMasterDataBootstrapImportEntityType.ITEM: {"item-001"},
        },
        allow_deferred=True,
    )
    assert decision.decision == BOOTSTRAP_DEPENDENCY_DECISION_READY
    assert decision.error_code == ""


def test_evaluate_binding_dependency_returns_deferred_for_missing_target() -> None:
    decision = evaluate_binding_dependency(
        target_entity_type=PoolMasterDataBootstrapImportEntityType.TAX_PROFILE,
        canonical_id="tax-404",
        resolved_canonical_ids_by_entity={
            PoolMasterDataBootstrapImportEntityType.TAX_PROFILE: {"tax-001"},
        },
        allow_deferred=True,
    )
    assert decision.decision == BOOTSTRAP_DEPENDENCY_DECISION_DEFERRED
    assert decision.error_code == "BOOTSTRAP_BINDING_TARGET_DEPENDENCY_MISSING"


def test_evaluate_binding_dependency_returns_failed_for_missing_target_when_deferred_disabled() -> None:
    decision = evaluate_binding_dependency(
        target_entity_type=PoolMasterDataBootstrapImportEntityType.PARTY,
        canonical_id="party-404",
        resolved_canonical_ids_by_entity={
            PoolMasterDataBootstrapImportEntityType.PARTY: {"party-001"},
        },
        allow_deferred=False,
    )
    assert decision.decision == BOOTSTRAP_DEPENDENCY_DECISION_FAILED
    assert decision.error_code == "BOOTSTRAP_BINDING_TARGET_DEPENDENCY_MISSING"


def test_resolve_bootstrap_import_dependency_order_rejects_unknown_entity() -> None:
    with pytest.raises(ValueError, match="POOL_MASTER_DATA_BOOTSTRAP_DEPENDENCY_ORDER_INVALID"):
        resolve_bootstrap_import_dependency_order(selected_scope=["unknown"])
