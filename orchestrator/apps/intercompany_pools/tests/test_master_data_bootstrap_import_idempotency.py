from __future__ import annotations

from apps.intercompany_pools.master_data_bootstrap_import_idempotency import (
    BOOTSTRAP_CHUNK_RESUME_ACTION_BLOCKED,
    BOOTSTRAP_CHUNK_RESUME_ACTION_EXECUTE,
    BOOTSTRAP_CHUNK_RESUME_ACTION_RETRY,
    BOOTSTRAP_CHUNK_RESUME_ACTION_SKIP,
    build_bootstrap_import_chunk_idempotency_key,
    resolve_bootstrap_import_chunk_resume_action,
)
from apps.intercompany_pools.models import PoolMasterDataBootstrapImportChunkStatus


def test_build_chunk_idempotency_key_is_stable_for_equivalent_payload() -> None:
    first = build_bootstrap_import_chunk_idempotency_key(
        job_id="job-1",
        entity_type="party",
        chunk_index=0,
        rows=[{"canonical_id": "party-001", "name": "ACME", "flags": {"a": 1, "b": 2}}],
    )
    second = build_bootstrap_import_chunk_idempotency_key(
        job_id="job-1",
        entity_type="party",
        chunk_index=0,
        rows=[{"name": "ACME", "flags": {"b": 2, "a": 1}, "canonical_id": "party-001"}],
    )

    assert first == second


def test_build_chunk_idempotency_key_changes_when_payload_changes() -> None:
    first = build_bootstrap_import_chunk_idempotency_key(
        job_id="job-1",
        entity_type="item",
        chunk_index=1,
        rows=[{"canonical_id": "item-001", "name": "Item A"}],
    )
    second = build_bootstrap_import_chunk_idempotency_key(
        job_id="job-1",
        entity_type="item",
        chunk_index=1,
        rows=[{"canonical_id": "item-001", "name": "Item B"}],
    )

    assert first != second


def test_resolve_chunk_resume_action_skips_already_applied_chunk() -> None:
    key = "chunk-key"
    decision = resolve_bootstrap_import_chunk_resume_action(
        chunk_status=PoolMasterDataBootstrapImportChunkStatus.SUCCEEDED,
        stored_idempotency_key=key,
        recomputed_idempotency_key=key,
        attempt_count=1,
    )

    assert decision.action == BOOTSTRAP_CHUNK_RESUME_ACTION_SKIP
    assert decision.error_code == ""


def test_resolve_chunk_resume_action_retries_failed_chunk_with_matching_key() -> None:
    key = "chunk-key"
    decision = resolve_bootstrap_import_chunk_resume_action(
        chunk_status=PoolMasterDataBootstrapImportChunkStatus.FAILED,
        stored_idempotency_key=key,
        recomputed_idempotency_key=key,
        attempt_count=1,
        max_attempts=3,
    )

    assert decision.action == BOOTSTRAP_CHUNK_RESUME_ACTION_RETRY
    assert decision.error_code == ""


def test_resolve_chunk_resume_action_blocks_when_attempts_are_exhausted() -> None:
    key = "chunk-key"
    decision = resolve_bootstrap_import_chunk_resume_action(
        chunk_status=PoolMasterDataBootstrapImportChunkStatus.FAILED,
        stored_idempotency_key=key,
        recomputed_idempotency_key=key,
        attempt_count=3,
        max_attempts=3,
    )

    assert decision.action == BOOTSTRAP_CHUNK_RESUME_ACTION_BLOCKED
    assert decision.error_code == "BOOTSTRAP_CHUNK_ATTEMPTS_EXHAUSTED"


def test_resolve_chunk_resume_action_blocks_on_idempotency_mismatch() -> None:
    decision = resolve_bootstrap_import_chunk_resume_action(
        chunk_status=PoolMasterDataBootstrapImportChunkStatus.SUCCEEDED,
        stored_idempotency_key="stored",
        recomputed_idempotency_key="new",
        attempt_count=0,
    )

    assert decision.action == BOOTSTRAP_CHUNK_RESUME_ACTION_BLOCKED
    assert decision.error_code == "BOOTSTRAP_CHUNK_IDEMPOTENCY_MISMATCH"


def test_resolve_chunk_resume_action_executes_pending_chunk() -> None:
    decision = resolve_bootstrap_import_chunk_resume_action(
        chunk_status=PoolMasterDataBootstrapImportChunkStatus.PENDING,
        stored_idempotency_key="",
        recomputed_idempotency_key="new",
        attempt_count=0,
    )

    assert decision.action == BOOTSTRAP_CHUNK_RESUME_ACTION_EXECUTE
