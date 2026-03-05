from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .models import PoolMasterDataBootstrapImportChunkStatus


BOOTSTRAP_CHUNK_RESUME_ACTION_EXECUTE = "execute"
BOOTSTRAP_CHUNK_RESUME_ACTION_SKIP = "skip"
BOOTSTRAP_CHUNK_RESUME_ACTION_RETRY = "retry"
BOOTSTRAP_CHUNK_RESUME_ACTION_BLOCKED = "blocked"


@dataclass(frozen=True)
class BootstrapChunkResumeDecision:
    action: str
    error_code: str = ""
    detail: str = ""


def build_bootstrap_import_chunk_idempotency_key(
    *,
    job_id: str,
    entity_type: str,
    chunk_index: int,
    rows: list[dict[str, Any]],
) -> str:
    payload = {
        "job_id": str(job_id or "").strip(),
        "entity_type": str(entity_type or "").strip().lower(),
        "chunk_index": int(chunk_index),
        "rows": _normalize_json_value(rows),
    }
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    return f"md-bootstrap-chunk:{digest}"


def resolve_bootstrap_import_chunk_resume_action(
    *,
    chunk_status: str,
    stored_idempotency_key: str,
    recomputed_idempotency_key: str,
    attempt_count: int,
    max_attempts: int = 3,
) -> BootstrapChunkResumeDecision:
    normalized_status = str(chunk_status or "").strip().lower()
    if normalized_status not in set(PoolMasterDataBootstrapImportChunkStatus.values):
        raise ValueError(f"POOL_MASTER_DATA_BOOTSTRAP_CHUNK_STATUS_INVALID: '{chunk_status}'")

    if max_attempts < 1:
        raise ValueError("POOL_MASTER_DATA_BOOTSTRAP_MAX_ATTEMPTS_INVALID: max_attempts must be >= 1")

    normalized_stored_key = str(stored_idempotency_key or "").strip()
    normalized_recomputed_key = str(recomputed_idempotency_key or "").strip()
    key_mismatch = bool(normalized_stored_key and normalized_recomputed_key) and (
        normalized_stored_key != normalized_recomputed_key
    )
    if key_mismatch:
        return BootstrapChunkResumeDecision(
            action=BOOTSTRAP_CHUNK_RESUME_ACTION_BLOCKED,
            error_code="BOOTSTRAP_CHUNK_IDEMPOTENCY_MISMATCH",
            detail="Stored and recomputed idempotency keys do not match.",
        )

    if normalized_status in {
        PoolMasterDataBootstrapImportChunkStatus.PENDING,
        PoolMasterDataBootstrapImportChunkStatus.RUNNING,
    }:
        return BootstrapChunkResumeDecision(action=BOOTSTRAP_CHUNK_RESUME_ACTION_EXECUTE)

    if normalized_status == PoolMasterDataBootstrapImportChunkStatus.SUCCEEDED:
        if not normalized_stored_key or not normalized_recomputed_key:
            return BootstrapChunkResumeDecision(
                action=BOOTSTRAP_CHUNK_RESUME_ACTION_BLOCKED,
                error_code="BOOTSTRAP_CHUNK_IDEMPOTENCY_KEY_MISSING",
                detail="Succeeded chunk requires both stored and recomputed idempotency keys.",
            )
        return BootstrapChunkResumeDecision(action=BOOTSTRAP_CHUNK_RESUME_ACTION_SKIP)

    if normalized_status in {
        PoolMasterDataBootstrapImportChunkStatus.FAILED,
        PoolMasterDataBootstrapImportChunkStatus.DEFERRED,
    }:
        if attempt_count >= max_attempts:
            return BootstrapChunkResumeDecision(
                action=BOOTSTRAP_CHUNK_RESUME_ACTION_BLOCKED,
                error_code="BOOTSTRAP_CHUNK_ATTEMPTS_EXHAUSTED",
                detail=f"Chunk attempts exhausted: {attempt_count}/{max_attempts}.",
            )
        if not normalized_stored_key or not normalized_recomputed_key:
            return BootstrapChunkResumeDecision(
                action=BOOTSTRAP_CHUNK_RESUME_ACTION_BLOCKED,
                error_code="BOOTSTRAP_CHUNK_IDEMPOTENCY_KEY_MISSING",
                detail="Retry requires both stored and recomputed idempotency keys.",
            )
        return BootstrapChunkResumeDecision(action=BOOTSTRAP_CHUNK_RESUME_ACTION_RETRY)

    if normalized_status == PoolMasterDataBootstrapImportChunkStatus.CANCELED:
        return BootstrapChunkResumeDecision(
            action=BOOTSTRAP_CHUNK_RESUME_ACTION_BLOCKED,
            error_code="BOOTSTRAP_CHUNK_CANCELED",
            detail="Canceled chunk cannot be resumed automatically.",
        )

    return BootstrapChunkResumeDecision(
        action=BOOTSTRAP_CHUNK_RESUME_ACTION_BLOCKED,
        error_code="BOOTSTRAP_CHUNK_STATUS_UNSUPPORTED",
        detail=f"Unsupported chunk status '{normalized_status}'.",
    )


def _normalize_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize_json_value(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_normalize_json_value(item) for item in value]
    return value
