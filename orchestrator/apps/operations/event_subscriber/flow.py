from typing import Any, Dict, Optional

from . import runtime


def default_flow_path(operation_type: str) -> list[str]:
    if operation_type in {
        "lock_scheduled_jobs",
        "unlock_scheduled_jobs",
        "block_sessions",
        "unblock_sessions",
        "terminate_sessions",
        "sync_cluster",
        "discover_clusters",
    }:
        return ["frontend", "api-gateway", "orchestrator", "worker"]
    if operation_type in {"designer_cli", "query", "health_check", "execute_workflow"}:
        return ["frontend", "api-gateway", "orchestrator", "worker"]
    return ["frontend", "api-gateway", "orchestrator", "worker"]


def publish_completion_flow(
    *,
    operation_id: str,
    operation_type: str,
    operation_name: str,
    status: str,
    message: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        from apps.operations.events import flow_publisher

        flow_publisher.publish_flow(
            operation_id=operation_id,
            current_service="worker",
            status=status,
            message=message,
            operation_type=operation_type,
            operation_name=operation_name,
            path=default_flow_path(operation_type),
            metadata=metadata or {},
        )
    except Exception:
        pass


def get_workflow_metadata(batch_op) -> Dict[str, Any]:
    metadata = batch_op.metadata or {}
    if not isinstance(metadata, dict):
        metadata = {}
    execution_consumer = str(metadata.get("execution_consumer") or "").strip() or "operations"
    lane = str(metadata.get("lane") or "").strip() or execution_consumer
    result: Dict[str, Any] = {}
    for key in ("workflow_execution_id", "node_id", "trace_id"):
        value = metadata.get(key)
        if value:
            result[key] = value
    result["root_operation_id"] = str(metadata.get("root_operation_id") or getattr(batch_op, "id", ""))
    result["execution_consumer"] = execution_consumer
    result["lane"] = lane
    return result


def release_idempotency_lock_for_operation(batch_op) -> None:
    operation_type = str(getattr(batch_op, "operation_type", "") or "").strip()
    payload = getattr(batch_op, "payload", None) or {}

    if operation_type == "sync_cluster":
        cluster_id = str(payload.get("cluster_id") or "").strip()
        if cluster_id:
            try:
                runtime.operations_redis_client.release_lock(f"sync_cluster:{cluster_id}")
            except Exception:
                pass
        return

    if operation_type == "discover_clusters":
        ras_server = str(payload.get("ras_server") or "").strip()
        if ras_server:
            try:
                runtime.operations_redis_client.release_lock(f"discover_clusters:{ras_server}")
            except Exception:
                pass
