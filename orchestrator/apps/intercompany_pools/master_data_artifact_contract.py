from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Mapping

from .document_plan_artifact_contract import validate_document_plan_artifact_v1
from .models import PoolRun


MASTER_DATA_SNAPSHOT_VERSION = "master_data_snapshot.v1"
MASTER_DATA_BINDING_ARTIFACT_VERSION = "master_data_binding_artifact.v1"
MASTER_DATA_GATE_MODE_RESOLVE_UPSERT = "resolve+upsert"

POOL_RUNTIME_MASTER_DATA_SNAPSHOT_REF_CONTEXT_KEY = "master_data_snapshot_ref"
POOL_RUNTIME_MASTER_DATA_BINDING_ARTIFACT_REF_CONTEXT_KEY = "master_data_binding_artifact_ref"
POOL_RUNTIME_MASTER_DATA_BINDING_ARTIFACT_CONTEXT_KEY = "pool_runtime_master_data_binding_artifact"
POOL_MASTER_DATA_BINDING_ARTIFACT_INVALID = "POOL_MASTER_DATA_BINDING_ARTIFACT_INVALID"

REQUIRED_MASTER_DATA_BINDING_ARTIFACT_FIELDS = {
    "version",
    "run_id",
    "mode",
    "snapshot_ref",
    "binding_artifact_ref",
    "targets",
    "bindings",
    "diagnostics",
    "generated_at",
}


def build_master_data_snapshot_ref(
    *,
    run: PoolRun,
    run_input: Mapping[str, Any] | None,
) -> str:
    payload = {
        "run_id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "pool_id": str(run.pool_id),
        "period_start": run.period_start.isoformat(),
        "period_end": run.period_end.isoformat() if run.period_end else None,
        "direction": run.direction,
        "mode": run.mode,
        "run_input": dict(run_input or {}),
    }
    digest = sha256(_canonical_json(payload)).hexdigest()
    return f"{MASTER_DATA_SNAPSHOT_VERSION}:{digest[:32]}"


def build_master_data_binding_artifact_ref(
    *,
    run: PoolRun,
    snapshot_ref: str,
    document_plan_artifact: Mapping[str, Any] | None,
) -> str:
    artifact_payload = (
        validate_document_plan_artifact_v1(artifact=document_plan_artifact)
        if isinstance(document_plan_artifact, Mapping)
        else None
    )
    payload = {
        "run_id": str(run.id),
        "snapshot_ref": str(snapshot_ref or "").strip(),
        "document_plan_artifact": artifact_payload,
    }
    digest = sha256(_canonical_json(payload)).hexdigest()
    return f"{MASTER_DATA_BINDING_ARTIFACT_VERSION}:{digest[:32]}"


def validate_master_data_binding_artifact_v1(*, artifact: Any) -> dict[str, Any]:
    if not isinstance(artifact, Mapping):
        raise ValueError(
            f"{POOL_MASTER_DATA_BINDING_ARTIFACT_INVALID}: master_data_binding_artifact must be an object"
        )
    payload = dict(artifact)
    missing_fields = sorted(
        field_name
        for field_name in REQUIRED_MASTER_DATA_BINDING_ARTIFACT_FIELDS
        if field_name not in payload
    )
    if missing_fields:
        raise ValueError(
            f"{POOL_MASTER_DATA_BINDING_ARTIFACT_INVALID}: missing required fields: {', '.join(missing_fields)}"
        )

    version = str(payload.get("version") or "").strip()
    if version != MASTER_DATA_BINDING_ARTIFACT_VERSION:
        raise ValueError(
            f"{POOL_MASTER_DATA_BINDING_ARTIFACT_INVALID}: unexpected artifact version '{version or '<empty>'}'"
        )

    mode = str(payload.get("mode") or "").strip()
    if mode != MASTER_DATA_GATE_MODE_RESOLVE_UPSERT:
        raise ValueError(
            f"{POOL_MASTER_DATA_BINDING_ARTIFACT_INVALID}: unsupported master-data gate mode '{mode or '<empty>'}'"
        )

    for field_name in (
        "run_id",
        "snapshot_ref",
        "binding_artifact_ref",
        "generated_at",
    ):
        text = str(payload.get(field_name) or "").strip()
        if not text:
            raise ValueError(
                f"{POOL_MASTER_DATA_BINDING_ARTIFACT_INVALID}: field '{field_name}' must be a non-empty string"
            )

    if not isinstance(payload.get("targets"), list):
        raise ValueError(
            f"{POOL_MASTER_DATA_BINDING_ARTIFACT_INVALID}: field 'targets' must be an array"
        )
    if not isinstance(payload.get("bindings"), list):
        raise ValueError(
            f"{POOL_MASTER_DATA_BINDING_ARTIFACT_INVALID}: field 'bindings' must be an array"
        )
    if not isinstance(payload.get("diagnostics"), list):
        raise ValueError(
            f"{POOL_MASTER_DATA_BINDING_ARTIFACT_INVALID}: field 'diagnostics' must be an array"
        )
    return payload


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
