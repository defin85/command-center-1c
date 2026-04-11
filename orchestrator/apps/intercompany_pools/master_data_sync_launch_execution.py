from __future__ import annotations

from typing import Any, Mapping

from .master_data_sync_launch_service import (
    mark_pool_master_data_sync_launch_request_failed,
    run_pool_master_data_sync_launch_request_fanout,
    serialize_pool_master_data_sync_launch_request,
)
from .master_data_sync_launch_workflow_contract import (
    validate_master_data_sync_launch_workflow_input_context,
)


def execute_pool_master_data_sync_launch_step(
    *,
    input_context: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_context = validate_master_data_sync_launch_workflow_input_context(
        input_context=input_context
    )
    launch_request_id = str(normalized_context["launch_request_id"])
    try:
        launch_request = run_pool_master_data_sync_launch_request_fanout(
            launch_request_id=launch_request_id
        )
    except Exception as exc:  # noqa: BLE001
        error_code = str(getattr(exc, "code", "SYNC_LAUNCH_FANOUT_FAILED") or "SYNC_LAUNCH_FANOUT_FAILED")
        error_detail = str(getattr(exc, "detail", exc) or error_code)
        mark_pool_master_data_sync_launch_request_failed(
            launch_request_id=launch_request_id,
            error_code=error_code,
            error_detail=error_detail,
        )
        raise

    serialized = serialize_pool_master_data_sync_launch_request(
        launch_request=launch_request,
        include_items=False,
    )
    return {
        "step": "master_data_sync.launch",
        "launch_request_id": launch_request_id,
        "status": serialized["status"],
        "aggregate_counters": serialized["aggregate_counters"],
        "progress": serialized["progress"],
        "child_job_status_counts": serialized["child_job_status_counts"],
    }
