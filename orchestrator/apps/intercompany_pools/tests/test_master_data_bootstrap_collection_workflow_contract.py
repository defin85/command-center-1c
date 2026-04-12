from __future__ import annotations

from uuid import uuid4

import pytest

from apps.intercompany_pools.master_data_bootstrap_collection_workflow_contract import (
    POOL_MASTER_DATA_BOOTSTRAP_COLLECTION_WORKFLOW_CONTRACT,
    POOL_MASTER_DATA_BOOTSTRAP_COLLECTION_WORKFLOW_CONTRACT_INVALID,
    build_pool_master_data_bootstrap_collection_workflow_input_context,
    validate_pool_master_data_bootstrap_collection_workflow_input_context,
)


def test_build_bootstrap_collection_workflow_input_context_contains_snapshot_and_origin() -> None:
    payload = build_pool_master_data_bootstrap_collection_workflow_input_context(
        collection_id=str(uuid4()),
        tenant_id=str(uuid4()),
        correlation_id="corr-bootstrap-collection-001",
        origin_system="bootstrap_collection_execute",
        origin_event_id="evt-bootstrap-collection-001",
        actor_username="collection-admin",
    )

    assert payload["contract_version"] == POOL_MASTER_DATA_BOOTSTRAP_COLLECTION_WORKFLOW_CONTRACT
    assert payload["collection_id"]
    assert payload["tenant_id"]
    assert payload["correlation_id"] == "corr-bootstrap-collection-001"
    assert payload["origin_system"] == "bootstrap_collection_execute"
    assert payload["origin_event_id"] == "evt-bootstrap-collection-001"
    assert payload["actor_username"] == "collection-admin"


def test_validate_bootstrap_collection_workflow_input_context_accepts_valid_payload() -> None:
    payload = {
        "contract_version": POOL_MASTER_DATA_BOOTSTRAP_COLLECTION_WORKFLOW_CONTRACT,
        "collection_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "correlation_id": "corr-bootstrap-collection-002",
        "origin_system": "tests",
        "origin_event_id": "evt-bootstrap-collection-002",
        "actor_username": "admin",
    }

    validated = validate_pool_master_data_bootstrap_collection_workflow_input_context(
        input_context=payload
    )

    assert validated["collection_id"] == payload["collection_id"]
    assert validated["tenant_id"] == payload["tenant_id"]
    assert validated["actor_username"] == "admin"


def test_validate_bootstrap_collection_workflow_input_context_fails_closed_when_correlation_missing() -> None:
    payload = {
        "contract_version": POOL_MASTER_DATA_BOOTSTRAP_COLLECTION_WORKFLOW_CONTRACT,
        "collection_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "correlation_id": "",
        "origin_system": "tests",
        "origin_event_id": "evt-bootstrap-collection-003",
    }

    with pytest.raises(
        ValueError,
        match=POOL_MASTER_DATA_BOOTSTRAP_COLLECTION_WORKFLOW_CONTRACT_INVALID,
    ):
        validate_pool_master_data_bootstrap_collection_workflow_input_context(
            input_context=payload
        )
