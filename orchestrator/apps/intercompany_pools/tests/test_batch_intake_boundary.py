from __future__ import annotations

from uuid import uuid4

import pytest


def test_build_batch_intake_execution_context_allows_normalization_provenance_and_run_kickoff() -> None:
    from apps.intercompany_pools.batch_intake_boundary import (
        BATCH_INTAKE_PERSISTENCE_TARGETS,
        build_batch_intake_execution_context,
    )
    from apps.intercompany_pools.models import PoolBatchKind, PoolBatchSourceType

    context = build_batch_intake_execution_context(
        tenant_id=str(uuid4()),
        pool_id=str(uuid4()),
        batch_kind=PoolBatchKind.RECEIPT,
        source_type=PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
        actions=[
            "normalize_batch_payload",
            "persist_batch_provenance",
            "kickoff_receipt_run",
        ],
        persistence_targets=BATCH_INTAKE_PERSISTENCE_TARGETS,
    )

    assert context["subsystem"] == "batch_intake"
    assert context["actions"] == [
        "kickoff_receipt_run",
        "normalize_batch_payload",
        "persist_batch_provenance",
    ]
    assert context["persistence_targets"] == sorted(BATCH_INTAKE_PERSISTENCE_TARGETS)


def test_validate_batch_intake_execution_context_rejects_factual_materialization_targets() -> None:
    from apps.intercompany_pools.batch_intake_boundary import (
        BATCH_INTAKE_CONTRACT_INVALID,
        validate_batch_intake_execution_context,
    )
    from apps.intercompany_pools.models import PoolBatchKind, PoolBatchSourceType

    with pytest.raises(ValueError, match=BATCH_INTAKE_CONTRACT_INVALID):
        validate_batch_intake_execution_context(
            input_context={
                "contract_version": "pool_batch_intake_boundary.v1",
                "tenant_id": str(uuid4()),
                "pool_id": str(uuid4()),
                "subsystem": "batch_intake",
                "batch_kind": PoolBatchKind.SALE,
                "source_type": PoolBatchSourceType.INTEGRATION,
                "actions": ["build_sale_closing_contract"],
                "persistence_targets": [
                    "pool_batches",
                    "pool_batch_settlements",
                ],
            }
        )


def test_validate_batch_intake_execution_context_rejects_review_or_projection_actions() -> None:
    from apps.intercompany_pools.batch_intake_boundary import (
        BATCH_INTAKE_CONTRACT_INVALID,
        validate_batch_intake_execution_context,
    )
    from apps.intercompany_pools.models import PoolBatchKind, PoolBatchSourceType

    with pytest.raises(ValueError, match=BATCH_INTAKE_CONTRACT_INVALID):
        validate_batch_intake_execution_context(
            input_context={
                "contract_version": "pool_batch_intake_boundary.v1",
                "tenant_id": str(uuid4()),
                "pool_id": str(uuid4()),
                "subsystem": "batch_intake",
                "batch_kind": PoolBatchKind.SALE,
                "source_type": PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
                "actions": [
                    "normalize_batch_payload",
                    "enqueue_manual_review",
                ],
                "persistence_targets": ["pool_batches"],
            }
        )
