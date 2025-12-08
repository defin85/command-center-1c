"""
OperationsService - Direct Redis queue operations (Celery replacement).

This service provides direct Redis queue operations for sending operations
to Go Workers, replacing Celery tasks for better performance and control.

Message Protocol v2.0 compliance - see go-services/shared/models/operation_v2.go
"""
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from django.conf import settings
from django.utils import timezone

from ..models import BatchOperation
from ..redis_client import redis_client
from ..events import event_publisher

logger = logging.getLogger(__name__)


@dataclass
class EnqueueResult:
    """Result of enqueue operation."""
    success: bool
    operation_id: str
    status: str  # queued|duplicate|error
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class OperationsService:
    """
    Service for sending operations directly to Redis queue.

    Replaces Celery tasks for operation enqueueing with direct Redis LPUSH.
    Maintains Message Protocol v2.0 compatibility with Go Workers.
    """

    QUEUE_KEY = "cc1c:operations:v1"
    VERSION = "2.0"

    @classmethod
    def is_celery_enabled(cls) -> bool:
        """Check if Celery fallback is enabled."""
        return getattr(settings, 'CELERY_ENABLED', True)

    @classmethod
    def enqueue_operation(cls, operation_id: str) -> EnqueueResult:
        """
        Enqueue operation to Redis queue for Go Worker processing.

        Args:
            operation_id: BatchOperation ID (UUID string)

        Returns:
            EnqueueResult with status and metadata
        """
        logger.info(f"Enqueuing operation {operation_id}")

        try:
            # 1. Get operation from DB
            operation = BatchOperation.objects.get(id=operation_id)

            # 2. Idempotency check - acquire lock
            lock_acquired = redis_client.acquire_lock(
                task_id=operation_id,
                ttl_seconds=3600  # 1 hour
            )

            if not lock_acquired:
                logger.warning(
                    f"Operation {operation_id} already locked (duplicate submission)"
                )
                return EnqueueResult(
                    success=False,
                    operation_id=operation_id,
                    status="duplicate",
                    error="Operation already in progress"
                )

            # 3. Build Message Protocol v2.0 message
            message = cls._build_message(operation)

            # 4. Enqueue to Redis
            redis_client.enqueue_operation(message)

            # 5. Publish QUEUED event for real-time tracking
            event_publisher.publish(
                operation_id=str(operation_id),
                state='QUEUED',
                microservice='orchestrator',
                queue=cls.QUEUE_KEY,
                target_databases_count=len(message["target_databases"])
            )

            # 6. Update operation status
            operation.status = BatchOperation.STATUS_QUEUED
            operation.save(update_fields=["status", "updated_at"])

            logger.info(
                f"Operation {operation_id} enqueued successfully",
                extra={
                    "operation_id": operation_id,
                    "operation_type": operation.operation_type,
                    "target_databases_count": len(message["target_databases"])
                }
            )

            return EnqueueResult(
                success=True,
                operation_id=operation_id,
                status="queued",
                metadata={
                    "queue": cls.QUEUE_KEY,
                    "target_databases_count": len(message["target_databases"])
                }
            )

        except BatchOperation.DoesNotExist:
            logger.error(f"Operation {operation_id} not found in database")
            return EnqueueResult(
                success=False,
                operation_id=operation_id,
                status="error",
                error=f"Operation {operation_id} not found"
            )

        except Exception as exc:
            logger.error(
                f"Error enqueueing operation {operation_id}: {exc}",
                exc_info=True
            )

            # Release lock on error
            redis_client.release_lock(operation_id)

            return EnqueueResult(
                success=False,
                operation_id=operation_id,
                status="error",
                error=str(exc)
            )

    @classmethod
    def enqueue_extension_install(
        cls,
        database_ids: list[str],
        extension_config: dict,
        created_by: str = "system"
    ) -> EnqueueResult:
        """
        Enqueue extension installation operation.

        Args:
            database_ids: List of database UUIDs to install extension on
            extension_config: Extension configuration dict with:
                - extension_id: UUID of stored extension
                - version: Extension version
                - options: Installation options (safe_mode, etc.)
            created_by: User who initiated the operation

        Returns:
            EnqueueResult with generated operation_id
        """
        operation_id = str(uuid.uuid4())

        message = {
            "version": cls.VERSION,
            "operation_id": operation_id,
            "batch_id": None,
            "operation_type": "install_extension",
            "entity": "Extension",
            "target_databases": database_ids,
            "payload": {
                "data": extension_config,
                "filters": {},
                "options": extension_config.get("options", {})
            },
            "execution_config": {
                "batch_size": 1,  # Install one at a time
                "timeout_seconds": 180,  # 3 minutes per install
                "retry_count": 2,
                "priority": "normal",
                "idempotency_key": operation_id
            },
            "metadata": {
                "created_by": created_by,
                "created_at": timezone.now().isoformat(),
                "template_id": None,
                "tags": ["extension", "install"]
            }
        }

        try:
            redis_client.enqueue_operation(message)

            event_publisher.publish(
                operation_id=operation_id,
                state='QUEUED',
                microservice='orchestrator',
                queue=cls.QUEUE_KEY,
                target_databases_count=len(database_ids)
            )

            logger.info(
                f"Extension install operation {operation_id} enqueued",
                extra={
                    "operation_id": operation_id,
                    "database_count": len(database_ids),
                    "extension_id": extension_config.get("extension_id")
                }
            )

            return EnqueueResult(
                success=True,
                operation_id=operation_id,
                status="queued",
                metadata={"database_count": len(database_ids)}
            )

        except Exception as exc:
            logger.error(f"Error enqueueing extension install: {exc}", exc_info=True)
            return EnqueueResult(
                success=False,
                operation_id=operation_id,
                status="error",
                error=str(exc)
            )

    @classmethod
    def enqueue_workflow_execution(
        cls,
        execution_id: str,
        workflow_config: Optional[dict] = None
    ) -> EnqueueResult:
        """
        Enqueue workflow execution operation.

        Args:
            execution_id: WorkflowExecution ID
            workflow_config: Optional workflow configuration override

        Returns:
            EnqueueResult with execution_id
        """
        message = {
            "version": cls.VERSION,
            "operation_id": execution_id,
            "batch_id": None,
            "operation_type": "execute_workflow",
            "entity": "Workflow",
            "target_databases": [],  # Workflow determines targets
            "payload": {
                "data": workflow_config or {},
                "filters": {},
                "options": {}
            },
            "execution_config": {
                "batch_size": 100,
                "timeout_seconds": 300,  # 5 minutes for workflow
                "retry_count": 1,
                "priority": "normal",
                "idempotency_key": execution_id
            },
            "metadata": {
                "created_by": "workflow_engine",
                "created_at": timezone.now().isoformat(),
                "template_id": None,
                "tags": ["workflow"]
            }
        }

        try:
            redis_client.enqueue_operation(message)

            event_publisher.publish(
                operation_id=execution_id,
                state='QUEUED',
                microservice='orchestrator',
                queue=cls.QUEUE_KEY
            )

            logger.info(f"Workflow execution {execution_id} enqueued")

            return EnqueueResult(
                success=True,
                operation_id=execution_id,
                status="queued"
            )

        except Exception as exc:
            logger.error(f"Error enqueueing workflow: {exc}", exc_info=True)
            return EnqueueResult(
                success=False,
                operation_id=execution_id,
                status="error",
                error=str(exc)
            )

    @classmethod
    def enqueue_cluster_sync(
        cls,
        cluster_id: str,
        operation_id: Optional[str] = None,
        created_by: str = "system"
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
            - cluster_service_url: URL of RAS Adapter
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
                error=f"Cluster {cluster_id} not found"
            )

        # Idempotency check - prevent concurrent sync for same cluster
        sync_lock_key = f"sync_cluster:{cluster_id}"
        lock_acquired = redis_client.acquire_lock(
            task_id=sync_lock_key,
            ttl_seconds=300  # 5 minutes - sync should complete within this time
        )

        if not lock_acquired:
            logger.warning(
                f"Cluster {cluster_id} sync already in progress (duplicate submission)"
            )
            return EnqueueResult(
                success=False,
                operation_id=op_id,
                status="duplicate",
                error=f"Cluster {cluster.name} sync already in progress"
            )

        # Build payload with full cluster data for Worker
        cluster_data = {
            "cluster_id": str(cluster.id),
            "cluster_name": cluster.name,
            "ras_server": cluster.ras_server,
            "ras_cluster_uuid": str(cluster.ras_cluster_uuid) if cluster.ras_cluster_uuid else "",
            "cluster_service_url": cluster.cluster_service_url,
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
            "payload": {
                "data": cluster_data,
                "filters": {},
                "options": {}
            },
            "execution_config": {
                "batch_size": 50,
                "timeout_seconds": 60,
                "retry_count": 3,
                "priority": "normal",
                "idempotency_key": op_id
            },
            "metadata": {
                "created_by": created_by,
                "created_at": timezone.now().isoformat(),
                "template_id": None,
                "tags": ["cluster", "sync"]
            }
        }

        try:
            # Acquire task lock for Worker (separate from idempotency lock)
            redis_client.acquire_lock(
                task_id=op_id,
                ttl_seconds=3600  # 1 hour
            )

            redis_client.enqueue_operation(message)

            event_publisher.publish(
                operation_id=op_id,
                state='QUEUED',
                microservice='orchestrator',
                queue=cls.QUEUE_KEY,
                cluster_id=cluster_id
            )

            logger.info(
                f"Cluster sync operation {op_id} enqueued",
                extra={
                    "operation_id": op_id,
                    "cluster_id": cluster_id,
                    "cluster_name": cluster.name,
                    "ras_server": cluster.ras_server
                }
            )

            return EnqueueResult(
                success=True,
                operation_id=op_id,
                status="queued",
                metadata={
                    "cluster_id": cluster_id,
                    "cluster_name": cluster.name
                }
            )

        except Exception as exc:
            logger.error(f"Error enqueueing cluster sync: {exc}", exc_info=True)
            return EnqueueResult(
                success=False,
                operation_id=op_id,
                status="error",
                error=str(exc)
            )

    @classmethod
    def _build_message(cls, operation: BatchOperation) -> dict[str, Any]:
        """
        Build Message Protocol v2.0 message from BatchOperation.

        Args:
            operation: BatchOperation model instance

        Returns:
            dict conforming to Message Protocol v2.0
        """
        return {
            "version": cls.VERSION,
            "operation_id": str(operation.id),
            "batch_id": None,  # TODO: Implement batch grouping in Phase 2
            "operation_type": operation.operation_type,
            "entity": operation.target_entity,
            "target_databases": [
                str(db.id) for db in operation.target_databases.all()
            ],
            "payload": {
                "data": operation.payload.get("data", {}),
                "filters": operation.payload.get("filters", {}),
                "options": operation.payload.get("options", {})
            },
            "execution_config": {
                "batch_size": operation.config.get("batch_size", 100),
                "timeout_seconds": operation.config.get("timeout_seconds", 30),
                "retry_count": operation.config.get("retry_count", 3),
                "priority": operation.config.get("priority", "normal"),
                "idempotency_key": str(operation.id)
            },
            "metadata": {
                "created_by": operation.created_by or "system",
                "created_at": operation.created_at.isoformat(),
                "template_id": str(operation.template.id) if operation.template else None,
                "tags": operation.metadata.get("tags", [])
            }
        }

    @classmethod
    def enqueue_health_check(
        cls,
        database_ids: list[str],
        created_by: str = "system"
    ) -> EnqueueResult:
        """
        Enqueue health check operation for multiple databases.

        Args:
            database_ids: List of database UUIDs to check
            created_by: User who initiated the operation

        Returns:
            EnqueueResult with generated operation_id
        """
        operation_id = str(uuid.uuid4())

        message = {
            "version": cls.VERSION,
            "operation_id": operation_id,
            "batch_id": None,
            "operation_type": "health_check",
            "entity": "Database",
            "target_databases": database_ids,
            "payload": {
                "data": {},
                "filters": {},
                "options": {"check_odata": True}
            },
            "execution_config": {
                "batch_size": 50,  # Check 50 at a time
                "timeout_seconds": 30,  # 30 seconds per database
                "retry_count": 1,
                "priority": "low",
                "idempotency_key": operation_id
            },
            "metadata": {
                "created_by": created_by,
                "created_at": timezone.now().isoformat(),
                "template_id": None,
                "tags": ["health_check", "monitoring"]
            }
        }

        try:
            redis_client.enqueue_operation(message)

            event_publisher.publish(
                operation_id=operation_id,
                state='QUEUED',
                microservice='orchestrator',
                queue=cls.QUEUE_KEY,
                target_databases_count=len(database_ids)
            )

            logger.info(
                f"Health check operation {operation_id} enqueued",
                extra={
                    "operation_id": operation_id,
                    "database_count": len(database_ids)
                }
            )

            return EnqueueResult(
                success=True,
                operation_id=operation_id,
                status="queued",
                metadata={"database_count": len(database_ids)}
            )

        except Exception as exc:
            logger.error(f"Error enqueueing health check: {exc}", exc_info=True)
            return EnqueueResult(
                success=False,
                operation_id=operation_id,
                status="error",
                error=str(exc)
            )

    @classmethod
    def enqueue_discover_clusters(
        cls,
        ras_server: str,
        operation_id: Optional[str] = None,
        cluster_user: str = "",
        cluster_pwd: str = "",
        created_by: str = "system"
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
        lock_acquired = redis_client.acquire_lock(
            task_id=discover_lock_key,
            ttl_seconds=300  # 5 minutes
        )

        if not lock_acquired:
            logger.warning(
                f"Cluster discovery for {ras_server} already in progress"
            )
            return EnqueueResult(
                success=False,
                operation_id=op_id,
                status="duplicate",
                error=f"Cluster discovery for {ras_server} already in progress"
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
            "payload": {
                "data": discover_data,
                "filters": {},
                "options": {}
            },
            "execution_config": {
                "batch_size": 1,
                "timeout_seconds": 60,
                "retry_count": 3,
                "priority": "normal",
                "idempotency_key": op_id
            },
            "metadata": {
                "created_by": created_by,
                "created_at": timezone.now().isoformat(),
                "template_id": None,
                "tags": ["cluster", "discover"]
            }
        }

        enqueue_success = False
        try:
            # Acquire task lock for Worker
            redis_client.acquire_lock(
                task_id=op_id,
                ttl_seconds=3600  # 1 hour
            )

            redis_client.enqueue_operation(message)

            event_publisher.publish(
                operation_id=op_id,
                state='QUEUED',
                microservice='orchestrator',
                queue=cls.QUEUE_KEY,
                ras_server=ras_server
            )

            logger.info(
                f"Discover clusters operation {op_id} enqueued",
                extra={
                    "operation_id": op_id,
                    "ras_server": ras_server
                }
            )

            enqueue_success = True
            return EnqueueResult(
                success=True,
                operation_id=op_id,
                status="queued",
                metadata={
                    "ras_server": ras_server
                }
            )

        except Exception as exc:
            logger.error(f"Error enqueueing discover clusters: {exc}", exc_info=True)
            return EnqueueResult(
                success=False,
                operation_id=op_id,
                status="error",
                error=str(exc)
            )
        finally:
            # Release idempotency lock on error (Worker will release on success)
            if not enqueue_success:
                redis_client.release_lock(discover_lock_key)

    @classmethod
    def get_queue_depth(cls) -> int:
        """Get current operations queue depth."""
        return redis_client.get_queue_depth(cls.QUEUE_KEY)
