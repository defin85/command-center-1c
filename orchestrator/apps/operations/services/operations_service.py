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
from ..events import event_publisher, flow_publisher

logger = logging.getLogger(__name__)

# Import Prometheus metrics with availability flag
try:
    from ..prometheus_metrics import record_batch_operation
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    record_batch_operation = None


def _record_batch_metric(operation_type: str, status: str):
    """
    Helper function to record batch operation metric.

    Args:
        operation_type: Type of operation (e.g., 'sync_cluster')
        status: Status to record (e.g., 'queued', 'completed', 'failed')
    """
    if METRICS_AVAILABLE:
        try:
            record_batch_operation(operation_type, status)
        except Exception as metric_err:
            logger.debug(f"Failed to record batch operation metric: {metric_err}")


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

    # Conflicting operation types - cannot run concurrently on same databases
    CONFLICTING_OPERATIONS = {
        'lock_scheduled_jobs': ['unlock_scheduled_jobs', 'lock_scheduled_jobs'],
        'unlock_scheduled_jobs': ['lock_scheduled_jobs', 'unlock_scheduled_jobs'],
        'block_sessions': ['unblock_sessions', 'block_sessions'],
        'unblock_sessions': ['block_sessions', 'unblock_sessions'],
        'terminate_sessions': ['terminate_sessions'],
    }

    @staticmethod
    def _get_workflow_metadata(operation: BatchOperation) -> dict[str, Any]:
        metadata = operation.metadata or {}
        result: dict[str, Any] = {}
        for key in ("workflow_execution_id", "node_id", "trace_id"):
            value = metadata.get(key)
            if value:
                result[key] = value
        return result

    @classmethod
    def check_conflicting_operations(
        cls,
        database_ids: list,
        operation_type: str,
        max_pending_age_minutes: int = 10
    ) -> tuple[bool, str]:
        """
        Check for active/pending operations on the same databases.

        Args:
            database_ids: List of database UUIDs
            operation_type: Type of operation to execute
            max_pending_age_minutes: Ignore pending ops older than this (stuck operations)

        Returns:
            (has_conflict: bool, error_message: str)
        """
        from django.utils import timezone
        from datetime import timedelta

        conflicting_types = cls.CONFLICTING_OPERATIONS.get(
            operation_type,
            [operation_type]
        )

        # Calculate cutoff time for "stuck" operations
        cutoff_time = timezone.now() - timedelta(minutes=max_pending_age_minutes)

        # Find active operations on same databases with conflicting types
        active_ops = BatchOperation.objects.filter(
            status__in=[
                BatchOperation.STATUS_PENDING,
                BatchOperation.STATUS_QUEUED,
                BatchOperation.STATUS_PROCESSING,
            ],
            operation_type__in=conflicting_types,
            target_databases__id__in=database_ids,
            created_at__gte=cutoff_time,  # Ignore old stuck operations
        ).distinct().first()

        if active_ops:
            return (
                True,
                f"Conflicting operation '{active_ops.operation_type}' "
                f"(id: {active_ops.id}) is already in progress"
            )

        return (False, "")

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

            # 2. Idempotency check - acquire enqueue lock (separate from Worker's task lock)
            lock_acquired = redis_client.acquire_enqueue_lock(
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

            workflow_metadata = cls._get_workflow_metadata(operation)

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
                target_databases_count=len(message["target_databases"]),
                **workflow_metadata
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

            # Record Prometheus metric for queued batch operation
            _record_batch_metric(operation.operation_type, 'queued')

            # Publish flow event for Service Mesh visualization
            flow_publisher.publish_flow(
                operation_id=str(operation_id),
                current_service="orchestrator",
                status="processing",
                message=f"Operation queued: {operation.operation_type}",
                operation_type=operation.operation_type,
                operation_name=operation.name or operation.operation_type,
                path=["frontend", "api-gateway", "orchestrator", "worker"],
                metadata={
                    "target_databases_count": len(message["target_databases"]),
                    "queue": cls.QUEUE_KEY,
                    **workflow_metadata
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
            # Record error metric
            _record_batch_metric('unknown', 'error')
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

            # Release enqueue lock on error
            redis_client.release_enqueue_lock(operation_id)

            # Record error metric (use operation type if available from local scope)
            try:
                op_type = operation.operation_type if 'operation' in locals() else 'unknown'
                _record_batch_metric(op_type, 'error')
            except Exception:
                _record_batch_metric('unknown', 'error')

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
        from apps.databases.models import Database

        operation_id = str(uuid.uuid4())

        # Load database objects for unified format
        databases = Database.objects.filter(id__in=database_ids)

        message = {
            "version": cls.VERSION,
            "operation_id": operation_id,
            "batch_id": None,
            "operation_type": "install_extension",
            "entity": "Extension",
            "target_databases": [
                cls._build_target_database_data(db) for db in databases
            ],
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

            database_count = databases.count()

            event_publisher.publish(
                operation_id=operation_id,
                state='QUEUED',
                microservice='orchestrator',
                queue=cls.QUEUE_KEY,
                target_databases_count=database_count
            )

            logger.info(
                f"Extension install operation {operation_id} enqueued",
                extra={
                    "operation_id": operation_id,
                    "database_count": database_count,
                    "extension_id": extension_config.get("extension_id")
                }
            )

            return EnqueueResult(
                success=True,
                operation_id=operation_id,
                status="queued",
                metadata={"database_count": database_count}
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
            ttl_seconds=900  # 15 minutes - large clusters may take longer
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
                "timeout_seconds": 180,
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
            # Acquire enqueue lock (separate key from Worker's task lock)
            # This prevents duplicate enqueue, Worker handles processing idempotency
            redis_client.acquire_enqueue_lock(
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
                    "queue": cls.QUEUE_KEY
                }
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

    @staticmethod
    def _build_target_database_data(db) -> dict[str, str]:
        """
        Build target database data for operation message.

        Args:
            db: Database model instance

        Returns:
            dict with id, name, cluster_id, ras_infobase_id
        """
        return {
            "id": str(db.id),
            "name": db.name,
            "cluster_id": str(db.cluster_id) if db.cluster_id else "",
            "ras_infobase_id": (
                str(db.ras_infobase_id)
                if hasattr(db, 'ras_infobase_id') and db.ras_infobase_id
                else str(db.id)
            )
        }

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
                cls._build_target_database_data(db)
                for db in operation.target_databases.all()
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
                "tags": operation.metadata.get("tags", []),
                "workflow_execution_id": operation.metadata.get("workflow_execution_id"),
                "node_id": operation.metadata.get("node_id"),
                "trace_id": operation.metadata.get("trace_id"),
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
        from apps.databases.models import Database

        from apps.operations.models import Task

        databases = list(Database.objects.filter(id__in=database_ids))
        if not databases:
            return EnqueueResult(
                success=False,
                operation_id="",
                status="error",
                error="No valid databases found for the provided IDs",
            )

        operation_id = str(uuid.uuid4())

        batch_operation = BatchOperation.objects.create(
            id=operation_id,
            name=f"health_check - {len(databases)} databases",
            operation_type="health_check",
            target_entity="Database",
            status=BatchOperation.STATUS_PENDING,
            payload={"data": {}, "filters": {}, "options": {"check_odata": True}},
            config={
                "batch_size": 50,
                "timeout_seconds": 30,
                "retry_count": 1,
                "priority": "low",
            },
            total_tasks=len(databases),
            created_by=created_by,
        )
        batch_operation.target_databases.set(databases)
        workflow_metadata = cls._get_workflow_metadata(batch_operation)
        workflow_metadata = cls._get_workflow_metadata(batch_operation)
        workflow_metadata = cls._get_workflow_metadata(batch_operation)

        tasks = [
            Task(
                id=str(uuid.uuid4()),
                batch_operation=batch_operation,
                database=db,
                status=Task.STATUS_PENDING,
            )
            for db in databases
        ]
        Task.objects.bulk_create(tasks)

        try:
            redis_client.add_timeline_event(
                operation_id,
                event="operation.created",
                service="orchestrator",
                metadata={
                    "operation_type": "health_check",
                    "target_databases_count": len(databases),
                    "created_by": created_by,
                    **workflow_metadata,
                },
            )
        except Exception:
            pass

        message = {
            "version": cls.VERSION,
            "operation_id": operation_id,
            "batch_id": None,
            "operation_type": "health_check",
            "entity": "Database",
            "target_databases": [
                cls._build_target_database_data(db) for db in databases
            ],
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
            redis_client.acquire_enqueue_lock(
                task_id=operation_id,
                ttl_seconds=3600
            )
            redis_client.enqueue_operation(message)

            try:
                redis_client.add_timeline_event(
                    operation_id,
                    event="operation.queued",
                    service="orchestrator",
                    metadata={"queue": cls.QUEUE_KEY, **workflow_metadata},
                )
            except Exception:
                pass

            database_count = len(databases)

            event_publisher.publish(
                operation_id=operation_id,
                state='QUEUED',
                microservice='orchestrator',
                queue=cls.QUEUE_KEY,
                target_databases_count=database_count,
                **workflow_metadata
            )

            flow_publisher.publish_flow(
                operation_id=operation_id,
                current_service="orchestrator",
                status="processing",
                message="Health check queued",
                operation_type="health_check",
                operation_name=batch_operation.name,
                path=["frontend", "api-gateway", "orchestrator", "worker"],
                metadata={
                    "target_databases_count": database_count,
                    "queue": cls.QUEUE_KEY,
                    **workflow_metadata
                }
            )

            batch_operation.status = BatchOperation.STATUS_QUEUED
            batch_operation.save(update_fields=['status', 'updated_at'])

            logger.info(
                f"Health check operation {operation_id} enqueued",
                extra={
                    "operation_id": operation_id,
                    "database_count": database_count
                }
            )

            _record_batch_metric("health_check", "queued")

            return EnqueueResult(
                success=True,
                operation_id=operation_id,
                status="queued",
                metadata={"database_count": database_count}
            )

        except Exception as exc:
            logger.error(f"Error enqueueing health check: {exc}", exc_info=True)
            batch_operation.status = BatchOperation.STATUS_FAILED
            batch_operation.save(update_fields=['status', 'updated_at'])
            _record_batch_metric("health_check", "error")
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
            # Acquire enqueue lock (separate from Worker's task lock)
            redis_client.acquire_enqueue_lock(
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

            # Publish flow event for Service Mesh visualization
            flow_publisher.publish_flow(
                operation_id=op_id,
                current_service="orchestrator",
                status="processing",
                message=f"Discover clusters queued: {ras_server}",
                operation_type="discover_clusters",
                operation_name=f"Discover {ras_server}",
                path=["frontend", "api-gateway", "orchestrator", "worker"],
                metadata={
                    "ras_server": ras_server,
                    "queue": cls.QUEUE_KEY
                }
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

    @classmethod
    def enqueue_ras_operation(
        cls,
        operation_type: str,
        database_ids: list,
        config: dict,
        user,
    ) -> "BatchOperation":
        """
        Create BatchOperation for RAS operation and enqueue to Redis.

        Args:
            operation_type: lock_scheduled_jobs, unlock_scheduled_jobs,
                           block_sessions, unblock_sessions, terminate_sessions
            database_ids: List of database UUIDs
            config: Operation-specific config (message, permission_code for block_sessions)
            user: User who initiated the operation

        Returns:
            BatchOperation instance

        Raises:
            ValueError: If no valid databases found
        """
        from apps.databases.models import Database
        from apps.operations.models import Task

        # Check for conflicting operations
        has_conflict, error_msg = cls.check_conflicting_operations(
            database_ids,
            operation_type
        )
        if has_conflict:
            raise ValueError(error_msg)

        # Get databases with cluster data
        databases = list(Database.objects.filter(
            id__in=database_ids
        ).select_related('cluster'))

        if not databases:
            raise ValueError("No valid databases found for the provided IDs")

        # Generate operation ID
        operation_id = str(uuid.uuid4())

        # Create BatchOperation
        batch_operation = BatchOperation.objects.create(
            id=operation_id,
            name=f"{operation_type} - {len(databases)} databases",
            operation_type=operation_type,
            target_entity="Infobase",
            status=BatchOperation.STATUS_PENDING,
            payload={"data": config, "filters": {}, "options": {}},
            config={
                "batch_size": 1,
                "timeout_seconds": 60,
                "retry_count": 3,
                "priority": "normal",
            },
            total_tasks=len(databases),
            created_by=user.username if user else "system",
        )
        batch_operation.target_databases.set(databases)

        # Timeline: operation created (best-effort)
        try:
            redis_client.add_timeline_event(
                operation_id,
                event="operation.created",
                service="orchestrator",
                metadata={
                    "operation_type": operation_type,
                    "target_databases_count": len(databases),
                    "created_by": user.username if user else "system",
                    **workflow_metadata,
                },
            )
        except Exception:
            pass

        # Create Tasks for each database
        tasks = [
            Task(
                id=str(uuid.uuid4()),
                batch_operation=batch_operation,
                database=db,
                status=Task.STATUS_PENDING,
            )
            for db in databases
        ]
        Task.objects.bulk_create(tasks)

        # Build Message Protocol v2.0 message
        message = {
            "version": cls.VERSION,
            "operation_id": operation_id,
            "batch_id": None,
            "operation_type": operation_type,
            "entity": "Infobase",
            "target_databases": [
                cls._build_target_database_data(db) for db in databases
            ],
            "payload": {
                "data": config,
                "filters": {},
                "options": {}
            },
            "execution_config": {
                "batch_size": 1,
                "timeout_seconds": 60,
                "retry_count": 3,
                "priority": "normal",
                "idempotency_key": operation_id
            },
            "metadata": {
                "created_by": user.username if user else "system",
                "created_at": timezone.now().isoformat(),
                "template_id": None,
                "tags": ["ras", operation_type]
            }
        }

        try:
            # Acquire enqueue lock (separate key from Worker's task lock)
            # This prevents duplicate enqueue, Worker handles processing idempotency
            redis_client.acquire_enqueue_lock(
                task_id=operation_id,
                ttl_seconds=3600  # 1 hour
            )

            # Enqueue to Redis
            redis_client.enqueue_operation(message)

            # Timeline: operation queued (best-effort)
            try:
                redis_client.add_timeline_event(
                    operation_id,
                    event="operation.queued",
                    service="orchestrator",
                    metadata={"queue": cls.QUEUE_KEY, **workflow_metadata},
                )
            except Exception:
                pass

            # Publish QUEUED event
            event_publisher.publish(
                operation_id=operation_id,
                state='QUEUED',
                microservice='orchestrator',
                queue=cls.QUEUE_KEY,
                target_databases_count=len(databases),
                **workflow_metadata
            )

            # Publish flow event for Service Mesh visualization
            flow_publisher.publish_flow(
                operation_id=operation_id,
                current_service="orchestrator",
                status="processing",
                message=f"Operation queued: {operation_type}",
                operation_type=operation_type,
                operation_name=batch_operation.name,
                path=["frontend", "api-gateway", "orchestrator", "worker"],
                metadata={
                    "target_databases_count": len(databases),
                    "queue": cls.QUEUE_KEY,
                    **workflow_metadata
                }
            )

            # Update status to QUEUED
            batch_operation.status = BatchOperation.STATUS_QUEUED
            batch_operation.save(update_fields=['status', 'updated_at'])

            logger.info(
                f"RAS operation {operation_id} enqueued",
                extra={
                    "operation_id": operation_id,
                    "operation_type": operation_type,
                    "database_count": len(databases)
                }
            )

            # Record Prometheus metric for queued batch operation
            _record_batch_metric(operation_type, 'queued')

            return batch_operation

        except Exception as exc:
            logger.error(f"Error enqueueing RAS operation: {exc}", exc_info=True)
            # Mark operation as failed
            batch_operation.status = BatchOperation.STATUS_FAILED
            batch_operation.save(update_fields=['status', 'updated_at'])
            # Record error metric
            _record_batch_metric(operation_type, 'error')
            raise

    @classmethod
    def enqueue_ibcmd_operation(
        cls,
        operation_type: str,
        database_ids: list,
        config: dict,
        user,
    ) -> "BatchOperation":
        """
        Create BatchOperation for IBCMD operation and enqueue to Redis.

        Args:
            operation_type: ibcmd_backup, ibcmd_restore, ibcmd_replicate, ibcmd_create
            database_ids: List of database UUIDs
            config: Operation-specific config (dbms, db_server, db_name, etc.)
            user: User who initiated the operation

        Returns:
            BatchOperation instance

        Raises:
            ValueError: If no valid databases found
        """
        from apps.databases.models import Database
        from apps.operations.models import Task

        databases = list(Database.objects.filter(id__in=database_ids))
        if not databases:
            raise ValueError("No valid databases found for the provided IDs")

        operation_id = str(uuid.uuid4())

        batch_operation = BatchOperation.objects.create(
            id=operation_id,
            name=f"{operation_type} - {len(databases)} databases",
            operation_type=operation_type,
            target_entity="Infobase",
            status=BatchOperation.STATUS_PENDING,
            payload={"data": config, "filters": {}, "options": {}},
            config={
                "batch_size": 1,
                "timeout_seconds": 900,
                "retry_count": 1,
                "priority": "normal",
            },
            total_tasks=len(databases),
            created_by=user.username if user else "system",
        )
        batch_operation.target_databases.set(databases)

        tasks = [
            Task(
                id=str(uuid.uuid4()),
                batch_operation=batch_operation,
                database=db,
                status=Task.STATUS_PENDING,
            )
            for db in databases
        ]
        Task.objects.bulk_create(tasks)

        message = {
            "version": cls.VERSION,
            "operation_id": operation_id,
            "batch_id": None,
            "operation_type": operation_type,
            "entity": "Infobase",
            "target_databases": [
                cls._build_target_database_data(db) for db in databases
            ],
            "payload": {
                "data": config,
                "filters": {},
                "options": {}
            },
            "execution_config": {
                "batch_size": 1,
                "timeout_seconds": 900,
                "retry_count": 1,
                "priority": "normal",
                "idempotency_key": operation_id
            },
            "metadata": {
                "created_by": user.username if user else "system",
                "created_at": timezone.now().isoformat(),
                "template_id": None,
                "tags": ["ibcmd", operation_type]
            }
        }

        try:
            redis_client.acquire_enqueue_lock(
                task_id=operation_id,
                ttl_seconds=3600
            )
            redis_client.enqueue_operation(message)

            try:
                redis_client.add_timeline_event(
                    operation_id,
                    event="operation.queued",
                    service="orchestrator",
                    metadata={"queue": cls.QUEUE_KEY, **workflow_metadata},
                )
            except Exception:
                pass

            event_publisher.publish(
                operation_id=operation_id,
                state='QUEUED',
                microservice='orchestrator',
                queue=cls.QUEUE_KEY,
                target_databases_count=len(databases),
                **workflow_metadata
            )

            flow_publisher.publish_flow(
                operation_id=operation_id,
                current_service="orchestrator",
                status="processing",
                message=f"Operation queued: {operation_type}",
                operation_type=operation_type,
                operation_name=batch_operation.name,
                path=["frontend", "api-gateway", "orchestrator", "worker"],
                metadata={
                    "target_databases_count": len(databases),
                    "queue": cls.QUEUE_KEY,
                    **workflow_metadata
                }
            )

            batch_operation.status = BatchOperation.STATUS_QUEUED
            batch_operation.save(update_fields=['status', 'updated_at'])

            _record_batch_metric(operation_type, 'queued')

            return batch_operation

        except Exception:
            redis_client.release_enqueue_lock(operation_id)
            _record_batch_metric(operation_type, 'error')
            raise
