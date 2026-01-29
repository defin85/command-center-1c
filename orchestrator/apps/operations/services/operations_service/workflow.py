from __future__ import annotations

import uuid
from typing import Optional

from django.utils import timezone

from ...events import event_publisher, flow_publisher
from ...redis_client import redis_client
from .types import EnqueueResult, classify_enqueue_error_code, logger


class OperationsServiceWorkflowMixin:
    @classmethod
    def enqueue_extension_install(
        cls,
        database_ids: list[str],
        extension_config: dict,
        created_by: str = "system",
    ) -> EnqueueResult:
        """Deprecated: extension installation via install_extension is removed."""
        logger.warning(
            "install_extension is deprecated; use designer_cli workflow instead",
            extra={"created_by": created_by, "database_count": len(database_ids)},
        )
        return EnqueueResult(
            success=False,
            operation_id="",
            status="error",
            error="install_extension is deprecated; use designer_cli workflow",
            error_code="NOT_SUPPORTED",
        )

    @classmethod
    def enqueue_workflow_execution(
        cls,
        execution_id: str,
        workflow_config: Optional[dict] = None,
    ) -> EnqueueResult:
        """
        Enqueue workflow execution operation.

        Args:
            execution_id: WorkflowExecution ID
            workflow_config: Optional workflow configuration override

        Returns:
            EnqueueResult with execution_id
        """
        data = dict(workflow_config or {})
        data["execution_id"] = execution_id

        message = {
            "version": cls.VERSION,
            "operation_id": execution_id,
            "batch_id": None,
            "operation_type": "execute_workflow",
            "entity": "Workflow",
            "target_databases": [],  # Workflow determines targets
            "payload": {"data": data, "filters": {}, "options": {}},
            "execution_config": {
                "batch_size": 100,
                "timeout_seconds": 300,  # 5 minutes for workflow
                "retry_count": 1,
                "priority": "normal",
                "idempotency_key": execution_id,
            },
            "metadata": {
                "created_by": "workflow_engine",
                "created_at": timezone.now().isoformat(),
                "template_id": None,
                "tags": ["workflow"],
            },
        }

        try:
            msg_id = redis_client.enqueue_operation_stream(message)

            event_publisher.publish(
                operation_id=execution_id,
                state="QUEUED",
                microservice="orchestrator",
                queue=cls.QUEUE_KEY,
            )

            logger.info(f"Workflow execution {execution_id} enqueued")

            return EnqueueResult(
                success=True,
                operation_id=execution_id,
                status="queued",
                metadata={"stream_message_id": msg_id},
            )

        except Exception as exc:
            logger.error(f"Error enqueueing workflow: {exc}", exc_info=True)
            return EnqueueResult(
                success=False,
                operation_id=execution_id,
                status="error",
                error=str(exc),
                error_code=classify_enqueue_error_code(exc),
            )

    @classmethod
    def enqueue_cluster_sync(
        cls,
        cluster_id: str,
        operation_id: Optional[str] = None,
        created_by: str = "system",
    ) -> EnqueueResult:
        """
        Enqueue cluster synchronization operation.

        Args:
            cluster_id: Cluster UUID to sync
            operation_id: Optional existing operation ID
            created_by: User who initiated the sync

        Returns:
            EnqueueResult with operation_id

        Note:
            Payload includes full cluster data for Go Worker:
            - ras_server: RAS server address (host:port)
            - ras_cluster_uuid: UUID of cluster in RAS (may be empty)
            - cluster_name: Cluster name
            - cluster_user, cluster_pwd: Credentials (optional)
        """
        from apps.databases.models import Cluster

        op_id = operation_id or str(uuid.uuid4())

        # Get cluster from DB
        try:
            cluster = Cluster.objects.get(id=cluster_id)
        except Cluster.DoesNotExist:
            logger.error(f"Cluster not found: {cluster_id}")
            return EnqueueResult(
                success=False,
                operation_id=op_id,
                status="error",
                error=f"Cluster {cluster_id} not found",
                error_code="NOT_FOUND",
            )

        # Idempotency check - prevent concurrent sync for same cluster
        sync_lock_key = f"sync_cluster:{cluster_id}"
        lock_acquired = redis_client.acquire_lock(task_id=sync_lock_key, ttl_seconds=900)  # 15 minutes

        if not lock_acquired:
            logger.warning(f"Cluster {cluster_id} sync already in progress (duplicate submission)")
            return EnqueueResult(
                success=False,
                operation_id=op_id,
                status="duplicate",
                error=f"Cluster {cluster.name} sync already in progress",
                error_code="DUPLICATE",
            )

        # Build payload with full cluster data for Worker
        ras_server = str(cluster.ras_server or "").strip()
        if getattr(cluster, "ras_host", None):
            ras_host = str(cluster.ras_host or "").strip()
            ras_port = int(cluster.ras_port or 1545) if getattr(cluster, "ras_port", None) else 1545
            if ras_host:
                ras_server = f"{ras_host}:{ras_port}"

        cluster_data = {
            "cluster_id": str(cluster.id),
            "cluster_name": cluster.name,
            "ras_server": ras_server,
            "ras_cluster_uuid": str(cluster.ras_cluster_uuid) if cluster.ras_cluster_uuid else "",
            "cluster_user": cluster.cluster_user or "",
            "cluster_pwd": cluster.cluster_pwd or "",
        }

        message = {
            "version": cls.VERSION,
            "operation_id": op_id,
            "batch_id": None,
            "operation_type": "sync_cluster",
            "entity": "Cluster",
            "target_databases": [],  # Sync discovers databases
            "payload": {"data": cluster_data, "filters": {}, "options": {}},
            "execution_config": {
                "batch_size": 50,
                "timeout_seconds": 180,
                "retry_count": 3,
                "priority": "normal",
                "idempotency_key": op_id,
            },
            "metadata": {
                "created_by": created_by,
                "created_at": timezone.now().isoformat(),
                "template_id": None,
                "tags": ["cluster", "sync"],
            },
        }

        try:
            # Acquire enqueue lock (separate key from Worker's task lock)
            # This prevents duplicate enqueue, Worker handles processing idempotency
            redis_client.acquire_enqueue_lock(task_id=op_id, ttl_seconds=3600)  # 1 hour

            msg_id = redis_client.enqueue_operation_stream(message)

            event_publisher.publish(
                operation_id=op_id,
                state="QUEUED",
                microservice="orchestrator",
                queue=cls.QUEUE_KEY,
                cluster_id=cluster_id,
            )

            # Publish flow event for Service Mesh visualization
            flow_publisher.publish_flow(
                operation_id=op_id,
                current_service="orchestrator",
                status="processing",
                message=f"Cluster sync queued: {cluster.name}",
                operation_type="sync_cluster",
                operation_name=f"Sync {cluster.name}",
                path=["frontend", "api-gateway", "orchestrator", "worker"],
                metadata={
                    "cluster_id": cluster_id,
                    "cluster_name": cluster.name,
                    "queue": cls.QUEUE_KEY,
                },
            )

            logger.info(
                f"Cluster sync operation {op_id} enqueued",
                extra={
                    "operation_id": op_id,
                    "cluster_id": cluster_id,
                    "cluster_name": cluster.name,
                    "ras_server": cluster.ras_server,
                },
            )

            return EnqueueResult(
                success=True,
                operation_id=op_id,
                status="queued",
                metadata={
                    "cluster_id": cluster_id,
                    "cluster_name": cluster.name,
                    "stream_message_id": msg_id,
                },
            )

        except Exception as exc:
            logger.error(f"Error enqueueing cluster sync: {exc}", exc_info=True)

            # Best-effort cleanup: allow immediate retry after enqueue failure.
            try:
                redis_client.release_enqueue_lock(task_id=op_id)
            except Exception:
                pass
            try:
                redis_client.release_lock(task_id=sync_lock_key)
            except Exception:
                pass

            return EnqueueResult(
                success=False,
                operation_id=op_id,
                status="error",
                error=str(exc),
                error_code=classify_enqueue_error_code(exc),
            )
