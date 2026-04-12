from __future__ import annotations

from typing import Any, Mapping
from uuid import uuid4

from .master_data_bootstrap_collection_service import (
    mark_pool_master_data_bootstrap_collection_failed,
    run_pool_master_data_bootstrap_collection_stage_chunk,
    serialize_pool_master_data_bootstrap_collection_request,
)
from .master_data_bootstrap_collection_workflow_contract import (
    validate_pool_master_data_bootstrap_collection_workflow_input_context,
)
from .master_data_bootstrap_collection_workflow_runtime import (
    start_pool_master_data_bootstrap_collection_stage_workflow,
)


def execute_pool_master_data_bootstrap_collection_step(
    *,
    input_context: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_context = validate_pool_master_data_bootstrap_collection_workflow_input_context(
        input_context=input_context
    )
    collection_id = str(normalized_context["collection_id"])
    stage = str(normalized_context["stage"])
    runner_token = str(normalized_context["runner_token"])
    try:
        chunk_result = run_pool_master_data_bootstrap_collection_stage_chunk(
            collection_id=collection_id,
            stage=stage,
            runner_token=runner_token,
        )
    except Exception as exc:  # noqa: BLE001
        error_code = str(
            getattr(exc, "code", f"BOOTSTRAP_COLLECTION_{str(stage).upper()}_FANOUT_FAILED")
            or f"BOOTSTRAP_COLLECTION_{str(stage).upper()}_FANOUT_FAILED"
        )
        error_detail = str(getattr(exc, "detail", exc) or error_code)
        mark_pool_master_data_bootstrap_collection_failed(
            collection_id=collection_id,
            error_code=error_code,
            error_detail=error_detail,
        )
        raise

    if chunk_result.should_continue and not chunk_result.stale_runner:
        start_pool_master_data_bootstrap_collection_stage_workflow(
            collection=chunk_result.collection,
            stage=stage,
            correlation_id=f"corr-bootstrap-collection-{stage}-{collection_id}-{uuid4()}",
            origin_system=f"bootstrap_collection_{stage}",
            origin_event_id=f"bootstrap-collection:{stage}:continue:{collection_id}:{uuid4()}",
            actor_username=str(normalized_context.get("actor_username") or ""),
        )

    serialized = serialize_pool_master_data_bootstrap_collection_request(
        collection=chunk_result.collection,
        include_items=False,
    )
    return {
        "step": "master_data_bootstrap.collection.stage",
        "collection_id": collection_id,
        "stage": stage,
        "runner_token": runner_token,
        "status": serialized["status"],
        "aggregate_counters": serialized["aggregate_counters"],
        "progress": serialized["progress"],
        "child_job_status_counts": serialized["child_job_status_counts"],
        "pending_items": chunk_result.pending_items,
        "processed_items": chunk_result.processed_items,
        "stale_runner": chunk_result.stale_runner,
    }
