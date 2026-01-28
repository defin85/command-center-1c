from __future__ import annotations

import uuid
from typing import Optional

from django.utils import timezone

from ...events import event_publisher, flow_publisher
from ...redis_client import redis_client
from .types import EnqueueResult, logger


class OperationsServiceDiscoveryMixin:
    @classmethod
    def enqueue_discover_clusters(
        cls,
        ras_server: str,
        operation_id: Optional[str] = None,
        cluster_user: str = "",
        cluster_pwd: str = "",
        created_by: str = "system",
    ) -> EnqueueResult:
        """
        Enqueue cluster discovery operation.

        Discovers all clusters available on the RAS server.

        Args:
            ras_server: RAS server address (host:port)
            operation_id: Optional existing operation ID
            cluster_user: Cluster admin username (optional)
            cluster_pwd: Cluster admin password (optional)
            created_by: User who initiated the operation

        Returns:
            EnqueueResult with operation_id
        """
        op_id = operation_id or str(uuid.uuid4())

        # Idempotency check - prevent concurrent discovery for same RAS server
        discover_lock_key = f"discover_clusters:{ras_server}"
        lock_acquired = redis_client.acquire_lock(task_id=discover_lock_key, ttl_seconds=300)  # 5 minutes

        if not lock_acquired:
            logger.warning(f"Cluster discovery for {ras_server} already in progress")
            return EnqueueResult(
                success=False,
                operation_id=op_id,
                status="duplicate",
                error=f"Cluster discovery for {ras_server} already in progress",
            )

        # Build payload for Worker
        discover_data = {
            "ras_server": ras_server,
            "cluster_user": cluster_user,
            "cluster_pwd": cluster_pwd,
        }

        message = {
            "version": cls.VERSION,
            "operation_id": op_id,
            "batch_id": None,
            "operation_type": "discover_clusters",
            "entity": "Cluster",
            "target_databases": [],  # Discovery finds clusters
            "payload": {"data": discover_data, "filters": {}, "options": {}},
            "execution_config": {
                "batch_size": 1,
                "timeout_seconds": 60,
                "retry_count": 3,
                "priority": "normal",
                "idempotency_key": op_id,
            },
            "metadata": {
                "created_by": created_by,
                "created_at": timezone.now().isoformat(),
                "template_id": None,
                "tags": ["cluster", "discover"],
            },
        }

        enqueue_success = False
        try:
            # Acquire enqueue lock (separate from Worker's task lock)
            redis_client.acquire_enqueue_lock(task_id=op_id, ttl_seconds=3600)  # 1 hour

            redis_client.enqueue_operation(message)

            event_publisher.publish(
                operation_id=op_id,
                state="QUEUED",
                microservice="orchestrator",
                queue=cls.QUEUE_KEY,
                ras_server=ras_server,
            )

            # Publish flow event for Service Mesh visualization
            flow_publisher.publish_flow(
                operation_id=op_id,
                current_service="orchestrator",
                status="processing",
                message=f"Discover clusters queued: {ras_server}",
                operation_type="discover_clusters",
                operation_name=f"Discover {ras_server}",
                path=["frontend", "api-gateway", "orchestrator", "worker"],
                metadata={"ras_server": ras_server, "queue": cls.QUEUE_KEY},
            )

            logger.info(
                f"Discover clusters operation {op_id} enqueued",
                extra={"operation_id": op_id, "ras_server": ras_server},
            )

            enqueue_success = True
            return EnqueueResult(
                success=True,
                operation_id=op_id,
                status="queued",
                metadata={"ras_server": ras_server},
            )

        except Exception as exc:
            logger.error(f"Error enqueueing discover clusters: {exc}", exc_info=True)
            return EnqueueResult(
                success=False,
                operation_id=op_id,
                status="error",
                error=str(exc),
            )
        finally:
            # Release idempotency lock on error (Worker will release on success)
            if not enqueue_success:
                redis_client.release_lock(discover_lock_key)
