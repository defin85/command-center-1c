"""
Event Subscriber for Redis Streams from Go services.

This module implements a Consumer Group-based subscriber for Redis Streams,
allowing Django Orchestrator to receive events from Go services (worker).

Architecture:
- Uses Redis Streams (NOT Pub/Sub) for guaranteed delivery
- Consumer Groups for at-least-once processing
- Graceful shutdown with signal handlers
- Automatic reconnection on Redis connection loss
"""

import json
import signal
import sys
import time
import os
import uuid
from typing import Dict, Any, Optional
import redis
from django.conf import settings
from django.db import transaction, close_old_connections
from django.utils import timezone
import logging

from apps.operations.models import Task
from apps.operations.redis_client import redis_client as operations_redis_client

logger = logging.getLogger(__name__)

# Import Prometheus metrics with availability flag
try:
    from .prometheus_metrics import record_redis_event_received, record_batch_operation
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    record_redis_event_received = None
    record_batch_operation = None


def _record_event_metric(event_type: str, channel: str):
    """
    Helper function to record received event metric.

    Args:
        event_type: Type of event (e.g., 'operation.completed')
        channel: Redis channel/stream name
    """
    if METRICS_AVAILABLE:
        try:
            record_redis_event_received(event_type, channel)
        except Exception as metric_err:
            logger.debug(f"Failed to record redis event received metric: {metric_err}")


def _record_batch_metric(operation_type: str, status: str):
    """
    Helper function to record batch operation metric.

    Args:
        operation_type: Type of operation (e.g., 'sync_cluster')
        status: Status to record (e.g., 'completed', 'failed')
    """
    if METRICS_AVAILABLE:
        try:
            record_batch_operation(operation_type, status)
        except Exception as metric_err:
            logger.debug(f"Failed to record batch operation metric: {metric_err}")


def _default_flow_path(operation_type: str) -> list[str]:
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
    if operation_type == "designer_cli":
        return ["frontend", "api-gateway", "orchestrator", "worker"]
    if operation_type in {"query", "health_check"}:
        return ["frontend", "api-gateway", "orchestrator", "worker"]
    if operation_type == "execute_workflow":
        return ["frontend", "api-gateway", "orchestrator", "worker"]
    return ["frontend", "api-gateway", "orchestrator", "worker"]


def _publish_completion_flow(
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
            path=_default_flow_path(operation_type),
            metadata=metadata or {},
        )
    except Exception:
        pass


def _get_workflow_metadata(batch_op) -> Dict[str, Any]:
    metadata = batch_op.metadata or {}
    result: Dict[str, Any] = {}
    for key in ("workflow_execution_id", "node_id", "trace_id"):
        value = metadata.get(key)
        if value:
            result[key] = value
    return result


class EventSubscriber:
    """
    Subscribes to Redis Streams from Go services.

    Uses Redis Streams with Consumer Groups for guaranteed delivery of events.

    Supported Stream Events:
    - worker:cluster-synced
    - worker:clusters-discovered
    - worker:completed
    - worker:failed
    - commands:worker:dlq (Dead Letter Queue)
    """

    def __init__(self):
        """Initialize Redis connection and consumer group settings."""
        redis_password = getattr(settings, 'REDIS_PASSWORD', None)

        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=int(settings.REDIS_PORT),
            password=redis_password if redis_password else None,
            decode_responses=True
        )

        self.consumer_group = "orchestrator-group"
        self.consumer_name = f"orchestrator-{os.getpid()}"
        self.running = True

        # Streams to subscribe to (stream_name: last_id)
        # '>' means read only new messages
        self.streams = {
            'events:worker:cluster-synced': '>',
            'events:worker:clusters-discovered': '>',
            'events:worker:completed': '>',
            'events:worker:failed': '>',
            'commands:worker:dlq': '>',  # Dead Letter Queue (Error Feedback Phase 1)
            # Commands from Worker (Request-Response pattern)
            'commands:orchestrator:get-cluster-info': '>',  # Cluster info requests from Worker
            'commands:orchestrator:get-database-credentials': '>',  # Credentials requests from Worker
        }

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

        logger.info(f"EventSubscriber initialized: {self.consumer_name}")

    def setup_consumer_groups(self):
        """
        Create consumer groups for all streams if they don't exist.

        Consumer groups allow multiple consumers to process messages in parallel,
        with each message delivered to only one consumer in the group.
        """
        for stream in self.streams.keys():
            try:
                # Create consumer group starting from the end of the stream ($)
                # mkstream=True creates the stream if it doesn't exist
                self.redis_client.xgroup_create(
                    stream,
                    self.consumer_group,
                    id='$',
                    mkstream=True
                )
                logger.info(f"Created consumer group '{self.consumer_group}' for stream '{stream}'")
            except redis.ResponseError as e:
                if "BUSYGROUP" in str(e):
                    # Group already exists, this is normal
                    logger.debug(f"Consumer group '{self.consumer_group}' already exists for '{stream}'")
                else:
                    logger.error(f"Error creating consumer group for '{stream}': {e}")
                    raise

    def run_forever(self):
        """
        Main event loop - read and process messages from Redis Streams.

        This method blocks indefinitely, reading messages in batches and
        processing them. It handles Redis connection errors gracefully
        by retrying with exponential backoff.
        """
        logger.info(f"Event subscriber starting: {self.consumer_name}")
        logger.info(f"Subscribed to {len(self.streams)} streams")

        # Setup consumer groups
        self.setup_consumer_groups()

        # Main loop
        while self.running:
            try:
                # Read messages from all streams
                # count=10: read up to 10 messages per stream
                # block=1000: block for up to 1000ms waiting for messages
                messages = self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    self.streams,
                    count=10,
                    block=1000
                )

                # Process each message
                for stream_name, stream_messages in messages:
                    for message_id, data in stream_messages:
                        try:
                            self.process_message(stream_name, message_id, data)

                            # Acknowledge message as processed
                            self.redis_client.xack(stream_name, self.consumer_group, message_id)

                        except Exception as e:
                            logger.error(
                                f"Error processing message {message_id} from {stream_name}: {e}",
                                exc_info=True
                            )
                            # Don't ACK - message will be retried later

            except redis.ConnectionError as e:
                logger.error(f"Redis connection lost: {e}, retrying in 5s...")
                time.sleep(5)

            except Exception as e:
                logger.error(f"Unexpected error in event loop: {e}", exc_info=True)
                time.sleep(1)

        logger.info("Event subscriber stopped")

    def process_message(self, stream: str, message_id: str, data: Dict[str, str]):
        """
        Process a single message from a stream.

        Args:
            stream: Stream name (e.g., 'events:worker:completed')
            message_id: Redis message ID (e.g., '1234567890123-0')
            data: Message data dict from Redis Stream

        Message format (Go Envelope):
            {
                'event_type': 'extension.installed',
                'correlation_id': 'batch-op-123',
                'timestamp': '2025-11-12T10:30:00Z',
                'payload': '{"database_id": "db-123", ...}'  # JSON string
            }
        """
        # Close stale DB connections in worker threads
        close_old_connections()
        # Extract envelope fields
        event_type = data.get('event_type', 'unknown')
        correlation_id = data.get('correlation_id', 'unknown')
        # timestamp_str available but not used: data.get('timestamp', '')

        # Parse payload (stored as JSON string in Redis Stream)
        payload_str = data.get('payload', '{}')

        try:
            if isinstance(payload_str, str):
                payload = json.loads(payload_str)
            else:
                payload = payload_str
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON payload in message {message_id}: {e}")
            return

        logger.info(
            f"Processing event: {event_type} "
            f"(stream={stream}, correlation_id={correlation_id}, msg_id={message_id})"
        )

        # Record Prometheus metric for received event
        _record_event_metric(event_type, stream)

        # Route to appropriate handler based on stream name
        if 'cluster-synced' in stream:
            self.handle_cluster_synced(payload, correlation_id)

        elif 'clusters-discovered' in stream:
            self.handle_clusters_discovered(payload, correlation_id)

        elif 'worker:completed' in stream:
            self.handle_worker_completed(data, correlation_id)

        elif 'worker:failed' in stream:
            self.handle_worker_failed(data, correlation_id)

        elif 'worker:dlq' in stream:
            self.handle_dlq_message(data, correlation_id)

        elif 'get-cluster-info' in stream:
            self.handle_get_cluster_info(data, correlation_id)

        elif 'get-database-credentials' in stream:
            self.handle_get_database_credentials(data, correlation_id)

        else:
            logger.warning(f"Unknown stream: {stream}")

    def handle_cluster_synced(self, payload: Dict[str, Any], correlation_id: str):
        """
        Handle cluster-synced event from Go Worker.

        This event is published when Worker completes sync_cluster operation.
        Handler imports discovered infobases into Database model.

        Payload example:
            {
                'operation_id': 'uuid',
                'cluster_id': 'uuid',
                'ras_cluster_uuid': 'uuid',  # May be resolved during sync
                'infobases': [
                    {
                        'uuid': 'infobase-uuid',
                        'name': 'TestBase',
                        'dbms': 'PostgreSQL',
                        'db_server': 'localhost',
                        'db_name': 'testbase',
                        'locale': 'ru_RU',
                        'sessions_deny': False,
                        'scheduled_jobs_deny': False
                    },
                    ...
                ],
                'success': True,
                'error': null
            }
        """
        from apps.databases.models import Cluster
        from apps.databases.services import ClusterService
        from apps.operations.models import BatchOperation

        from .redis_client import redis_client

        operation_id = payload.get('operation_id')
        cluster_id = payload.get('cluster_id')
        ras_cluster_uuid = payload.get('ras_cluster_uuid')
        infobases = payload.get('infobases', [])
        success = payload.get('success', False)
        error = payload.get('error')

        logger.info(
            f"Cluster synced event: cluster_id={cluster_id}, "
            f"operation_id={operation_id}, success={success}, "
            f"infobases_count={len(infobases)}, correlation_id={correlation_id}"
        )

        try:
            with transaction.atomic():
                # 1. Get Cluster from DB
                try:
                    cluster = Cluster.objects.select_for_update().get(id=cluster_id)
                except Cluster.DoesNotExist:
                    logger.error(f"Cluster not found: {cluster_id}")
                    return

                if success:
                    # 2. Update ras_cluster_uuid if it was resolved during sync
                    if ras_cluster_uuid and not cluster.ras_cluster_uuid:
                        cluster.ras_cluster_uuid = ras_cluster_uuid
                        cluster.save(update_fields=['ras_cluster_uuid', 'updated_at'])
                        logger.info(
                            f"Updated ras_cluster_uuid for cluster {cluster.name}: "
                            f"{ras_cluster_uuid}"
                        )

                    # 3. Import infobases into Database model
                    if infobases:
                        created, updated, errors = ClusterService.import_infobases_from_dict(
                            cluster=cluster,
                            infobases=infobases
                        )
                        logger.info(
                            f"Imported infobases for cluster {cluster.name}: "
                            f"created={created}, updated={updated}, errors={errors}"
                        )

                    # 4. Mark cluster sync as successful
                    cluster.mark_sync(success=True)

                else:
                    # Mark cluster sync as failed
                    error_msg = error or "Unknown error from Worker"
                    cluster.mark_sync(success=False, error_message=error_msg)
                    logger.error(
                        f"Cluster sync failed: cluster={cluster.name}, error={error_msg}"
                    )

                # 5. Update BatchOperation status if exists
                if operation_id:
                    try:
                        batch_op = BatchOperation.objects.get(id=operation_id)
                        if success:
                            batch_op.status = BatchOperation.STATUS_COMPLETED
                            batch_op.metadata['sync_result'] = {
                                'infobases_count': len(infobases),
                                'ras_cluster_uuid': ras_cluster_uuid,
                            }
                        else:
                            batch_op.status = BatchOperation.STATUS_FAILED
                            batch_op.metadata['error'] = error
                        batch_op.save(update_fields=['status', 'metadata', 'updated_at'])
                        workflow_metadata = _get_workflow_metadata(batch_op)
                        try:
                            operations_redis_client.add_timeline_event(
                                operation_id,
                                event="operation.completed" if success else "operation.failed",
                                service="event-subscriber",
                                metadata={
                                    "status": batch_op.status,
                                    "cluster_id": str(cluster_id),
                                    "error": error if not success else None,
                                    **workflow_metadata,
                                },
                            )
                        except Exception:
                            pass
                        _publish_completion_flow(
                            operation_id=operation_id,
                            operation_type=batch_op.operation_type,
                            operation_name=batch_op.name,
                            status="completed" if success else "failed",
                            message="Cluster sync completed" if success else "Cluster sync failed",
                            metadata={
                                "cluster_id": str(cluster_id),
                                "error": error if not success else None,
                                **workflow_metadata,
                            },
                        )
                        logger.info(
                            f"Updated BatchOperation {operation_id} status: {batch_op.status}"
                        )
                    except BatchOperation.DoesNotExist:
                        logger.debug(
                            f"BatchOperation not found: {operation_id} "
                            f"(may be direct sync without BatchOperation)"
                        )

        except Exception as e:
            logger.error(
                f"Error handling cluster-synced event: {e}",
                exc_info=True
            )
        finally:
            # Always release the sync lock to allow new sync operations
            if cluster_id:
                sync_lock_key = f"sync_cluster:{cluster_id}"
                redis_client.release_lock(sync_lock_key)
                logger.debug(f"Released sync lock for cluster {cluster_id}")

    def handle_clusters_discovered(self, payload: Dict[str, Any], correlation_id: str):
        """
        Handle clusters-discovered event from Go Worker.

        Creates or updates Cluster records in DB for all discovered clusters.

        Payload example:
            {
                'operation_id': 'uuid',
                'ras_server': 'localhost:1545',
                'clusters': [
                    {
                        'uuid': 'cluster-uuid',
                        'name': 'Cluster Name',
                        'host': 'server1',
                        'port': 1541,
                        'expiration_timeout': 0,
                        'lifetime_limit': 0,
                        'max_memory_size': 0,
                        'max_memory_time_limit': 0,
                        'security_level': 0,
                        'session_fault_tolerance_level': 0,
                        'load_balancing_mode': 0,
                        'errors_count_threshold': 0,
                        'kill_problem_processes': False
                    },
                    ...
                ],
                'success': True,
                'error': null
            }
        """
        from apps.databases.models import Cluster
        from apps.operations.models import BatchOperation
        from .redis_client import redis_client

        operation_id = payload.get('operation_id')
        ras_server = payload.get('ras_server')
        clusters_data = payload.get('clusters', [])
        success = payload.get('success', False)
        error = payload.get('error')

        logger.info(
            f"Clusters discovered event: ras_server={ras_server}, "
            f"operation_id={operation_id}, success={success}, "
            f"clusters_count={len(clusters_data)}, correlation_id={correlation_id}"
        )

        created = 0
        updated = 0

        try:
            def _parse_host_port(value: str):
                if not value:
                    return "", None
                if ":" not in value:
                    return value, None
                host, port_str = value.rsplit(":", 1)
                try:
                    port = int(port_str)
                except (ValueError, TypeError):
                    port = None
                return host, port

            ras_host, ras_port = _parse_host_port(ras_server or "")
            ras_port = ras_port or 1545
            with transaction.atomic():
                if success and clusters_data:
                    for cluster_data in clusters_data:
                        cluster_uuid = cluster_data.get('uuid')
                        cluster_name = cluster_data.get('name', 'Unknown')

                        # Try to find existing cluster by ras_cluster_uuid
                        cluster_service_url = f"http://{ras_server}" if ras_server else "http://localhost"
                        rmngr_host = (cluster_data.get('host') or ras_host or "").strip()
                        rmngr_port = cluster_data.get('port') or 1541
                        ragent_host = rmngr_host or ras_host or ""

                        cluster, is_new = Cluster.objects.get_or_create(
                            ras_cluster_uuid=cluster_uuid,
                            defaults={
                                'name': cluster_name,
                                'ras_server': ras_server,
                                'ras_host': ras_host,
                                'ras_port': ras_port,
                                'rmngr_host': rmngr_host,
                                'rmngr_port': rmngr_port,
                                'ragent_host': ragent_host,
                                'ragent_port': 1540,
                                'rphost_port_from': 1560,
                                'rphost_port_to': 1591,
                                'cluster_service_url': cluster_service_url,
                                'status': 'active',
                                'metadata': cluster_data,
                            }
                        )

                        if not is_new:
                            updates = {
                                'name': cluster_name,
                                'ras_server': ras_server,
                                'ras_host': ras_host,
                                'ras_port': ras_port,
                                'cluster_service_url': cluster_service_url,
                                'status': 'active',
                                'metadata': cluster_data,
                            }
                            if not cluster.rmngr_host and rmngr_host:
                                updates['rmngr_host'] = rmngr_host
                            if not cluster.rmngr_port and rmngr_port:
                                updates['rmngr_port'] = rmngr_port
                            if not cluster.ragent_host and ragent_host:
                                updates['ragent_host'] = ragent_host
                            if not cluster.ragent_port:
                                updates['ragent_port'] = 1540
                            if not cluster.rphost_port_from:
                                updates['rphost_port_from'] = 1560
                            if not cluster.rphost_port_to:
                                updates['rphost_port_to'] = 1591
                            Cluster.objects.filter(pk=cluster.pk).update(**updates)

                        if is_new:
                            created += 1
                            logger.info(
                                f"Created new cluster: {cluster_name} "
                                f"(uuid={cluster_uuid}, ras_server={ras_server})"
                            )
                        else:
                            updated += 1
                            logger.info(
                                f"Updated cluster: {cluster_name} "
                                f"(uuid={cluster_uuid}, ras_server={ras_server})"
                            )

                # Update BatchOperation status if exists
                if operation_id:
                    try:
                        batch_op = BatchOperation.objects.get(id=operation_id)
                        if success:
                            batch_op.status = BatchOperation.STATUS_COMPLETED
                            batch_op.metadata['discovery_result'] = {
                                'clusters_found': len(clusters_data),
                                'created': created,
                                'updated': updated,
                            }
                        else:
                            batch_op.status = BatchOperation.STATUS_FAILED
                            batch_op.metadata['error'] = error
                        batch_op.save(update_fields=['status', 'metadata', 'updated_at'])
                        workflow_metadata = _get_workflow_metadata(batch_op)
                        try:
                            operations_redis_client.add_timeline_event(
                                operation_id,
                                event="operation.completed" if success else "operation.failed",
                                service="event-subscriber",
                                metadata={
                                    "status": batch_op.status,
                                    "ras_server": ras_server,
                                    "clusters_found": len(clusters_data),
                                    "created": created,
                                    "updated": updated,
                                    "error": error if not success else None,
                                    **workflow_metadata,
                                },
                            )
                        except Exception:
                            pass
                        _publish_completion_flow(
                            operation_id=operation_id,
                            operation_type=batch_op.operation_type,
                            operation_name=batch_op.name,
                            status="completed" if success else "failed",
                            message="Clusters discovery completed" if success else "Clusters discovery failed",
                            metadata={
                                "ras_server": ras_server,
                                "clusters_found": len(clusters_data),
                                "error": error if not success else None,
                                **workflow_metadata,
                            },
                        )
                        logger.info(
                            f"Updated BatchOperation {operation_id} status: {batch_op.status}"
                        )
                    except BatchOperation.DoesNotExist:
                        logger.debug(
                            f"BatchOperation not found: {operation_id}"
                        )

        except Exception as e:
            logger.error(
                f"Error handling clusters-discovered event: {e}",
                exc_info=True
            )
        finally:
            # Always release the discovery lock to allow new discovery operations
            if ras_server:
                discover_lock_key = f"discover_clusters:{ras_server}"
                redis_client.release_lock(discover_lock_key)
                logger.debug(f"Released discover lock for ras_server {ras_server}")

    def handle_worker_completed(self, data: Dict[str, Any], correlation_id: str):
        """
        Handle operation completed event from Worker via Streams.

        Data format (nested envelope):
            {
                'data': '{"version": "1.0", "payload": {...}, ...}'  # JSON string
            }
        """
        from apps.operations.models import BatchOperation

        # Parse nested envelope if data contains 'data' field
        envelope_str = data.get('data', '')
        envelope = {}
        if envelope_str:
            try:
                envelope = json.loads(envelope_str)
                payload_str = envelope.get('payload', '{}')
                if isinstance(payload_str, str):
                    payload = json.loads(payload_str)
                else:
                    payload = payload_str
            except json.JSONDecodeError as e:
                logger.error(f"Invalid envelope JSON: {e}")
                return
        else:
            payload = data

        operation_id = payload.get('operation_id')
        if not operation_id:
            # Try from envelope metadata
            metadata = envelope.get('metadata', {}) if envelope_str else {}
            operation_id = metadata.get('operation_id')

        if not operation_id:
            logger.warning(f"No operation_id in worker:completed event: {data}")
            return

        logger.info(f"Worker completed event: operation_id={operation_id}")

        try:
            close_old_connections()
            batch_op = BatchOperation.objects.get(id=operation_id)

            # Extract summary from payload
            summary = payload.get('summary', {})
            results = payload.get('results', [])
            workflow_metadata = _get_workflow_metadata(batch_op)
            now = timezone.now()

            completed_tasks = summary.get("succeeded", 0)
            failed_tasks = summary.get("failed", 0)
            if results:
                for result in results:
                    database_id = result.get("database_id")
                    if not database_id:
                        continue

                    status = Task.STATUS_COMPLETED if result.get("success") else Task.STATUS_FAILED
                    duration_seconds = result.get("duration_seconds")
                    update_fields = {
                        "status": status,
                        "completed_at": now,
                        "updated_at": now,
                        "duration_seconds": duration_seconds,
                    }
                    if status == Task.STATUS_COMPLETED:
                        update_fields["result"] = result.get("data")
                        update_fields["error_message"] = ""
                        update_fields["error_code"] = ""
                    else:
                        update_fields["error_message"] = result.get("error") or "Unknown error"
                        update_fields["error_code"] = result.get("error_code") or "UNKNOWN_ERROR"
                        update_fields["result"] = None

                    Task.objects.filter(
                        batch_operation=batch_op,
                        database_id=database_id
                    ).update(**update_fields)

                successful = sum(1 for result in results if result.get("success"))
                failed = len(results) - successful
                total = summary.get("total") or batch_op.total_tasks or len(results)
                completed_tasks = summary.get("succeeded", successful)
                failed_tasks = summary.get("failed", failed)
                batch_op.total_tasks = total
                batch_op.completed_tasks = completed_tasks
                batch_op.failed_tasks = failed_tasks

            payload_status = str(payload.get("status") or "").lower()
            if payload_status == "failed":
                batch_op.status = BatchOperation.STATUS_FAILED
            elif payload_status == "timeout":
                batch_op.status = BatchOperation.STATUS_FAILED
            elif summary:
                if failed_tasks > 0 and completed_tasks == 0:
                    batch_op.status = BatchOperation.STATUS_FAILED
                else:
                    batch_op.status = BatchOperation.STATUS_COMPLETED
            else:
                batch_op.status = BatchOperation.STATUS_COMPLETED
            batch_op.progress = 100
            if not batch_op.completed_at:
                batch_op.completed_at = now

            batch_op.metadata['worker_result'] = {
                'summary': summary,
                'results_count': len(results),
            }
            batch_op.save(update_fields=[
                'status',
                'progress',
                'completed_at',
                'metadata',
                'total_tasks',
                'completed_tasks',
                'failed_tasks',
                'updated_at',
            ])
            try:
                operations_redis_client.add_timeline_event(
                    operation_id,
                    event="operation.completed",
                    service="event-subscriber",
                    metadata={
                        "status": batch_op.status,
                        "results_count": len(results),
                        **workflow_metadata,
                    },
                )
            except Exception:
                pass

            logger.info(f"Updated BatchOperation {operation_id} to COMPLETED via Stream")

            # Record Prometheus metric for completed operation
            _record_batch_metric(batch_op.operation_type, 'completed')

            _publish_completion_flow(
                operation_id=operation_id,
                operation_type=batch_op.operation_type,
                operation_name=batch_op.name,
                status="completed",
                message="Worker completed",
                metadata={"summary": summary, "results_count": len(results), **workflow_metadata},
            )

            self._update_database_restrictions(batch_op, results)
            self._update_database_health(batch_op, results)

        except BatchOperation.DoesNotExist:
            logger.warning(f"BatchOperation not found: {operation_id}")
        except Exception as e:
            logger.error(f"Error handling worker:completed: {e}", exc_info=True)

    def handle_worker_failed(self, data: Dict[str, Any], correlation_id: str):
        """
        Handle operation failed event from Worker via Streams.
        """
        from apps.operations.models import BatchOperation

        # Parse nested envelope
        envelope_str = data.get('data', '')
        envelope = {}
        if envelope_str:
            try:
                envelope = json.loads(envelope_str)
                payload_str = envelope.get('payload', '{}')
                if isinstance(payload_str, str):
                    payload = json.loads(payload_str)
                else:
                    payload = payload_str
            except json.JSONDecodeError as e:
                logger.error(f"Invalid envelope JSON: {e}")
                return
        else:
            payload = data

        operation_id = payload.get('operation_id')
        error_msg = payload.get('error', 'Unknown error')

        if not operation_id:
            metadata = envelope.get('metadata', {}) if envelope_str else {}
            operation_id = metadata.get('operation_id')

        if not operation_id:
            logger.warning(f"No operation_id in worker:failed event: {data}")
            return

        logger.info(f"Worker failed event: operation_id={operation_id}, error={error_msg}")

        try:
            close_old_connections()
            batch_op = BatchOperation.objects.get(id=operation_id)

            batch_op.status = BatchOperation.STATUS_FAILED
            batch_op.progress = 100
            if not batch_op.completed_at:
                from django.utils import timezone
                batch_op.completed_at = timezone.now()

            batch_op.metadata['error'] = error_msg
            batch_op.save(update_fields=['status', 'progress', 'completed_at', 'metadata', 'updated_at'])
            workflow_metadata = _get_workflow_metadata(batch_op)
            try:
                operations_redis_client.add_timeline_event(
                    operation_id,
                    event="operation.failed",
                    service="event-subscriber",
                    metadata={
                        "status": batch_op.status,
                        "error": error_msg,
                        **workflow_metadata,
                    },
                )
            except Exception:
                pass

            logger.info(f"Updated BatchOperation {operation_id} to FAILED via Stream")

            # Record Prometheus metric for failed operation
            _record_batch_metric(batch_op.operation_type, 'failed')

            _publish_completion_flow(
                operation_id=operation_id,
                operation_type=batch_op.operation_type,
                operation_name=batch_op.name,
                status="failed",
                message=error_msg or "Worker failed",
                metadata={"error": error_msg, **workflow_metadata},
            )

        except BatchOperation.DoesNotExist:
            logger.warning(f"BatchOperation not found: {operation_id}")
        except Exception as e:
            logger.error(f"Error handling worker:failed: {e}", exc_info=True)

    def handle_infobase_locked(self, payload: Dict[str, Any], correlation_id: str) -> None:
        """
        Handle infobase locked events.

        Currently informational: logs and attempts to update task status if correlation_id matches.
        """
        cluster_id = payload.get("cluster_id")
        infobase_id = payload.get("infobase_id")
        reason = payload.get("reason")
        logger.info(
            "Infobase locked event: cluster_id=%s, infobase_id=%s, reason=%s, correlation_id=%s",
            cluster_id,
            infobase_id,
            reason,
            correlation_id,
        )
        self._update_task_status_from_correlation_id(
            correlation_id=correlation_id,
            status=Task.STATUS_COMPLETED,
            result=payload,
        )

    def handle_sessions_closed(self, payload: Dict[str, Any], correlation_id: str) -> None:
        """
        Handle sessions closed events.

        Currently informational: logs and attempts to update task status if correlation_id matches.
        """
        cluster_id = payload.get("cluster_id")
        infobase_id = payload.get("infobase_id")
        sessions_closed = payload.get("sessions_closed")
        duration_seconds = payload.get("duration_seconds")
        logger.info(
            "Sessions closed event: cluster_id=%s, infobase_id=%s, sessions_closed=%s, "
            "duration_seconds=%s, correlation_id=%s",
            cluster_id,
            infobase_id,
            sessions_closed,
            duration_seconds,
            correlation_id,
        )
        self._update_task_status_from_correlation_id(
            correlation_id=correlation_id,
            status=Task.STATUS_COMPLETED,
            result=payload,
        )

    def _update_database_restrictions(self, batch_op, results: list[Dict[str, Any]]) -> None:
        if batch_op.operation_type not in {
            "lock_scheduled_jobs",
            "unlock_scheduled_jobs",
            "block_sessions",
            "unblock_sessions",
        }:
            return

        config = {}
        if isinstance(batch_op.payload, dict):
            config = batch_op.payload.get("data") or {}
        if not isinstance(config, dict):
            config = {}

        success_ids = [
            result.get("database_id")
            for result in results
            if result.get("success") and result.get("database_id")
        ]
        if not success_ids:
            return

        def set_metadata_value(metadata: dict, key: str, value: Optional[str]) -> None:
            if value:
                metadata[key] = value
            else:
                metadata.pop(key, None)

        from apps.databases.models import Database

        for database in Database.objects.filter(id__in=success_ids):
            metadata = database.metadata or {}
            if not isinstance(metadata, dict):
                metadata = {}

            if batch_op.operation_type == "lock_scheduled_jobs":
                metadata["scheduled_jobs_deny"] = True
            elif batch_op.operation_type == "unlock_scheduled_jobs":
                metadata["scheduled_jobs_deny"] = False
            elif batch_op.operation_type == "block_sessions":
                metadata["sessions_deny"] = True
                set_metadata_value(metadata, "denied_from", config.get("denied_from"))
                set_metadata_value(metadata, "denied_to", config.get("denied_to"))
                set_metadata_value(metadata, "denied_message", config.get("message"))
                set_metadata_value(metadata, "permission_code", config.get("permission_code"))
                set_metadata_value(metadata, "denied_parameter", config.get("parameter"))
            elif batch_op.operation_type == "unblock_sessions":
                metadata["sessions_deny"] = False
                for key in (
                    "denied_from",
                    "denied_to",
                    "denied_message",
                    "permission_code",
                    "denied_parameter",
                ):
                    metadata.pop(key, None)

            database.metadata = metadata
            database.save(update_fields=["metadata", "updated_at"])

    def _update_database_health(self, batch_op, results: list[Dict[str, Any]]) -> None:
        if batch_op.operation_type != "health_check":
            return

        if not results:
            return

        from apps.databases.models import Database

        def parse_response_time(value: Any) -> Optional[float]:
            if value is None:
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        for result in results:
            database_id = result.get("database_id")
            if not database_id:
                continue

            try:
                database = Database.objects.get(id=database_id)
            except Database.DoesNotExist:
                continue

            data = result.get("data") or {}
            response_time_ms = parse_response_time(data.get("response_time_ms"))
            success = bool(result.get("success"))

            database.mark_health_check(success=success, response_time=response_time_ms)

            metadata = database.metadata if isinstance(database.metadata, dict) else {}
            metadata_updated = False

            if success:
                for key in ("last_health_error", "last_health_error_code"):
                    if key in metadata:
                        metadata.pop(key, None)
                        metadata_updated = True
            else:
                error_message = result.get("error")
                error_code = result.get("error_code")

                if error_message:
                    metadata["last_health_error"] = error_message
                    metadata_updated = True
                elif "last_health_error" in metadata:
                    metadata.pop("last_health_error", None)
                    metadata_updated = True

                if error_code:
                    metadata["last_health_error_code"] = error_code
                    metadata_updated = True
                elif "last_health_error_code" in metadata:
                    metadata.pop("last_health_error_code", None)
                    metadata_updated = True

            if metadata_updated:
                database.metadata = metadata
                database.save(update_fields=["metadata", "updated_at"])

    def _update_task_status_from_correlation_id(
        self,
        correlation_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        error_code: Optional[str] = None
    ):
        """
        Update Task status based on correlation_id.

        Correlation ID format: "batch-<batch_op_id>-<task_id>"
        Example: "batch-batch-123-task-456" where batch_op_id="batch-123", task_id="task-456"

        Args:
            correlation_id: Correlation ID from event
            status: New task status (Task.STATUS_*)
            result: Task result data (for success)
            error_message: Error message (for failure)
            error_code: Error code (for failure)
        """
        try:
            # Parse correlation_id to extract task_id
            # Expected format: "batch-<batch_op_id>-<task_id>"
            # Since batch_op_id and task_id may contain hyphens, we need to find the last occurrence
            # that matches the pattern "task-<uuid>"

            if not correlation_id.startswith('batch-'):
                logger.warning(f"Invalid correlation_id format (missing batch- prefix): {correlation_id}")
                return

            # Remove "batch-" prefix
            remainder = correlation_id[6:]  # Skip "batch-"

            # Find the last occurrence of a task ID pattern (starts with "task-")
            task_prefix_index = remainder.rfind('-task-')
            if task_prefix_index == -1:
                logger.warning(f"Invalid correlation_id format (no task- found): {correlation_id}")
                return

            # Extract task_id (everything after the last "-task-" including "task-")
            task_id = remainder[task_prefix_index + 1:]  # Skip leading '-'

            # Use atomic transaction with select_for_update to prevent race conditions
            # when multiple event subscribers process the same task concurrently
            with transaction.atomic():
                # Find task with row-level lock
                try:
                    task = Task.objects.select_for_update().get(id=task_id)
                except Task.DoesNotExist:
                    logger.warning(f"Task not found: {task_id} (correlation_id={correlation_id})")
                    return

                # Update task based on status
                if status == Task.STATUS_COMPLETED:
                    task.mark_completed(result=result)
                    logger.info(f"Task {task_id} marked as completed")

                elif status == Task.STATUS_FAILED:
                    task.mark_failed(
                        error_message=error_message or "Unknown error",
                        error_code=error_code,
                        should_retry=True
                    )
                    logger.info(f"Task {task_id} marked as failed: {error_message}")

                else:
                    # For other statuses, update directly
                    task.status = status
                    task.save(update_fields=['status', 'updated_at'])
                    logger.info(f"Task {task_id} status updated to {status}")

        except Exception as e:
            logger.error(f"Error updating task from correlation_id {correlation_id}: {e}", exc_info=True)

    def handle_dlq_message(self, data: Dict[str, Any], correlation_id: str):
        """
        Handle Dead Letter Queue message from Go Worker.

        DLQ messages are created when:
        1. Envelope parsing fails but fallback IDs are available
        2. Error publishing to failed stream fails

        DLQ message structure:
            {
                'original_message_id': 'redis-msg-id',
                'correlation_id': 'uuid',
                'operation_id': 'uuid',
                'event_type': 'operation.created',
                'error_code': 'ENVELOPE_PARSE_ERROR',
                'error_message': 'failed to parse envelope: ...',
                'worker_id': 'worker-1',
                'failed_at': '2025-12-12T10:30:00Z'
            }
        """
        from apps.operations.models import BatchOperation

        # DLQ messages come directly as fields (not nested envelope)
        original_message_id = data.get('original_message_id', 'unknown')
        operation_id = data.get('operation_id', '')
        error_code = data.get('error_code', 'UNKNOWN')
        error_message = data.get('error_message', 'Unknown error')
        worker_id = data.get('worker_id', '')
        failed_at = data.get('failed_at', '')

        logger.error(
            f"DLQ message received: operation_id={operation_id}, "
            f"error_code={error_code}, error={error_message}, "
            f"worker_id={worker_id}, original_msg_id={original_message_id}, "
            f"failed_at={failed_at}, correlation_id={correlation_id}"
        )

        # Try to update BatchOperation if operation_id is known
        if operation_id:
            try:
                close_old_connections()

                # FIX #7 + #9: Use select_for_update() with atomic transaction
                # and deduplication check INSIDE transaction to prevent race condition
                terminal_states = [
                    BatchOperation.STATUS_COMPLETED,
                    BatchOperation.STATUS_FAILED,
                    BatchOperation.STATUS_CANCELLED
                ]
                dlq_dedup_key = f"dlq:processed:{operation_id}"

                with transaction.atomic():
                    # FIX #9 (MINOR #1): Check deduplication INSIDE transaction
                    # to prevent race condition where two threads pass sismember simultaneously
                    if self.redis_client.sismember(dlq_dedup_key, original_message_id):
                        logger.debug(
                            f"DLQ message already processed: operation_id={operation_id}, "
                            f"original_msg_id={original_message_id}"
                        )
                        return

                    batch_op = BatchOperation.objects.select_for_update().get(id=operation_id)

                    # Only update if not already in terminal state
                    if batch_op.status not in terminal_states:
                        from django.utils import timezone
                        batch_op.status = BatchOperation.STATUS_FAILED
                        batch_op.progress = 100
                        batch_op.completed_at = timezone.now()
                        batch_op.metadata['dlq_error'] = {
                            'error_code': error_code,
                            'error_message': error_message,
                            'worker_id': worker_id,
                            'original_message_id': original_message_id,
                            'failed_at': failed_at,
                        }
                        batch_op.save(update_fields=[
                            'status', 'progress', 'completed_at', 'metadata', 'updated_at'
                        ])
                        logger.info(
                            f"Updated BatchOperation {operation_id} to FAILED from DLQ"
                        )
                    else:
                        logger.debug(
                            f"BatchOperation {operation_id} already in terminal state: "
                            f"{batch_op.status}, skipping DLQ update"
                        )

                    # Mark as processed INSIDE transaction (FIX #9 MINOR #1)
                    # This ensures atomicity with the deduplication check
                    self.redis_client.sadd(dlq_dedup_key, original_message_id)
                    self.redis_client.expire(dlq_dedup_key, 86400)  # 24h TTL

            except BatchOperation.DoesNotExist:
                logger.warning(
                    f"BatchOperation not found for DLQ message: {operation_id}"
                )
            except Exception as e:
                logger.error(
                    f"Error updating BatchOperation from DLQ: {e}",
                    exc_info=True
                )
        else:
            logger.warning(
                f"DLQ message without operation_id, cannot update BatchOperation: "
                f"original_msg_id={original_message_id}, error_code={error_code}"
            )

    def handle_get_cluster_info(self, data: Dict[str, Any], correlation_id: str):
        """
        Handle get-cluster-info command from Go Worker.

        This implements the Request-Response pattern over Redis Streams.
        Worker sends a request with correlation_id, and we respond with
        cluster info (or error) to the response stream.

        Request data format:
            {
                'correlation_id': 'uuid',
                'database_id': '123',
                'timestamp': '2025-12-15T...'
            }

        Response format (published to events:orchestrator:cluster-info-response):
            {
                'correlation_id': 'uuid',
                'database_id': '123',
                'cluster_id': 'uuid',  # UUID in RAS
                'ras_server': 'localhost:1545',
                'ras_cluster_uuid': 'uuid',  # UUID in RAS
                'infobase_id': 'uuid',  # UUID in RAS
                'success': True/False,
                'error': null or 'error message'
            }
        """
        from apps.databases.models import Database

        # Extract request fields (flat format from Redis Stream)
        request_correlation_id = data.get('correlation_id', correlation_id)
        database_id = data.get('database_id', '')
        # timestamp available but not used: data.get('timestamp', '')

        logger.info(
            f"Processing get-cluster-info request: database_id={database_id}, "
            f"correlation_id={request_correlation_id}"
        )

        # Prepare response
        response = {
            'correlation_id': request_correlation_id,
            'database_id': database_id,
            'cluster_id': '',
            'ras_server': '',
            'ras_cluster_uuid': '',
            'infobase_id': '',
            'success': 'false',  # Redis stores as string
            'error': '',
        }

        try:
            # Note: close_old_connections() is called in the main run_forever loop
            # between message processing, so we don't need to call it here.
            # This allows the handler to work correctly in both production
            # (long-running process) and test environments.

            # Lookup database with cluster relation
            try:
                database = Database.objects.select_related('cluster').get(pk=database_id)
            except Database.DoesNotExist:
                response['error'] = f'Database {database_id} not found'
                logger.warning(f"Database not found: {database_id}")
                self._publish_cluster_info_response(response)
                return

            # Check if cluster is configured
            if not database.cluster:
                response['error'] = f'Database {database_id} has no cluster configured'
                logger.warning(f"No cluster for database: {database_id}")
                self._publish_cluster_info_response(response)
                return

            cluster = database.cluster

            # Check if cluster has RAS configuration
            ras_cluster_uuid = cluster.ras_cluster_uuid or database.ras_cluster_id
            if not ras_cluster_uuid:
                response['error'] = (
                    f'Cluster {cluster.name} has no ras_cluster_uuid configured. '
                    f'Run sync_cluster first or set manually in admin.'
                )
                logger.warning(
                    f"No ras_cluster_uuid for cluster {cluster.name} "
                    f"(database: {database_id})"
                )
                self._publish_cluster_info_response(response)
                return

            # Check if database has infobase UUID
            infobase_uuid = database.ras_infobase_id
            if not infobase_uuid:
                try:
                    infobase_uuid = uuid.UUID(str(database.id))
                except (ValueError, TypeError, AttributeError):
                    infobase_uuid = None
            if not infobase_uuid:
                response['error'] = (
                    f'Database {database_id} has no ras_infobase_id configured. '
                    f'Run sync_cluster first.'
                )
                logger.warning(
                    f"No ras_infobase_id for database {database_id}"
                )
                self._publish_cluster_info_response(response)
                return

            # Success - populate response
            response['cluster_id'] = str(ras_cluster_uuid)
            response['ras_server'] = cluster.ras_server or ''
            response['ras_cluster_uuid'] = str(ras_cluster_uuid)
            response['infobase_id'] = str(infobase_uuid)
            response['success'] = 'true'
            response['error'] = ''

            logger.info(
                f"Cluster info resolved: database_id={database_id}, "
                f"ras_cluster_uuid={ras_cluster_uuid}, "
                f"infobase_id={infobase_uuid}"
            )

        except Exception as e:
            response['error'] = f'Internal error: {str(e)}'
            logger.error(
                f"Error handling get-cluster-info: {e}",
                exc_info=True
            )

        # Publish response
        self._publish_cluster_info_response(response)

    def _publish_cluster_info_response(self, response: Dict[str, str]):
        """
        Publish cluster info response to the response stream.

        Args:
            response: Response dict with correlation_id, database_id, etc.
        """
        response_stream = 'events:orchestrator:cluster-info-response'

        try:
            self.redis_client.xadd(response_stream, response)
            logger.debug(
                f"Published cluster-info response: correlation_id={response.get('correlation_id')}, "
                f"success={response.get('success')}"
            )
        except Exception as e:
            logger.error(
                f"Failed to publish cluster-info response: {e}",
                exc_info=True
            )

    def handle_get_database_credentials(self, data: Dict[str, Any], correlation_id: str):
        """
        Handle get-database-credentials command from Go Worker.

        Request fields (flat Redis Stream):
            - correlation_id (required)
            - database_id (required)

        Response is published to events:orchestrator:database-credentials-response.
        Credentials payload is encrypted via apps.databases.encryption.encrypt_credentials_for_transport.
        """
        from django.contrib.auth import get_user_model
        from apps.databases.models import Database, InfobaseUserMapping
        from apps.databases.encryption import encrypt_credentials_for_transport

        request_correlation_id = data.get('correlation_id', correlation_id)
        database_id = data.get('database_id', '')
        created_by = (data.get('created_by') or '').strip()

        logger.info(
            f"Processing get-database-credentials request: database_id={database_id}, "
            f"correlation_id={request_correlation_id}"
        )

        response = {
            'correlation_id': request_correlation_id,
            'database_id': database_id,
            'success': 'false',
            'error': '',
            'encrypted_data': '',
            'nonce': '',
            'expires_at': '',
            'encryption_version': '',
        }

        try:
            try:
                database = Database.objects.select_related('cluster').get(id=database_id)
            except Database.DoesNotExist:
                response['error'] = f'Database {database_id} not found'
                logger.warning(f"Database not found: {database_id}")
                self._publish_database_credentials_response(response)
                return

            ib_username = ''
            ib_password = ''
            if created_by:
                user_model = get_user_model()
                user = user_model.objects.filter(username=created_by).first()
                if user:
                    mapping = InfobaseUserMapping.objects.filter(database=database, user=user).first()
                    if mapping:
                        ib_username = mapping.ib_username
                        ib_password = mapping.ib_password

            if not database.cluster:
                response['error'] = 'Database cluster is not configured'
                logger.warning(
                    f"Database {database_id} has no cluster configured for DESIGNER credentials"
                )
                self._publish_database_credentials_response(response)
                return

            cluster = database.cluster
            rmngr_host = (cluster.rmngr_host or '').strip()
            rmngr_port = cluster.rmngr_port or 0
            if not rmngr_host or not rmngr_port:
                response['error'] = 'Cluster RMNGR host/port is not configured'
                logger.warning(
                    f"Cluster {cluster.id} has no RMNGR host/port configured"
                )
                self._publish_database_credentials_response(response)
                return

            credentials_dict = {
                "database_id": str(database.id),
                "odata_url": database.odata_url,
                "username": database.username,
                "password": database.password,  # EncryptedCharField auto-decrypts
                "ib_username": ib_username,
                "ib_password": ib_password,
                "host": database.host,
                "port": database.port,
                "base_name": database.base_name,
                "server_address": rmngr_host,
                "server_port": rmngr_port,
                "infobase_name": database.infobase_name or database.name,
            }

            encrypted_payload = encrypt_credentials_for_transport(credentials_dict)

            response['success'] = 'true'
            response['error'] = ''
            response['encrypted_data'] = encrypted_payload.get('encrypted_data', '')
            response['nonce'] = encrypted_payload.get('nonce', '')
            response['expires_at'] = encrypted_payload.get('expires_at', '')
            response['encryption_version'] = encrypted_payload.get('encryption_version', '')

        except Exception as e:
            response['error'] = f'Internal error: {str(e)}'
            logger.error(
                f"Error handling get-database-credentials: {e}",
                exc_info=True
            )

        self._publish_database_credentials_response(response)

    def _publish_database_credentials_response(self, response: Dict[str, str]):
        """Publish database credentials response to Redis Streams."""
        response_stream = 'events:orchestrator:database-credentials-response'

        try:
            self.redis_client.xadd(response_stream, response)
            logger.debug(
                f"Published database-credentials response: correlation_id={response.get('correlation_id')}, "
                f"success={response.get('success')}"
            )
        except Exception as e:
            logger.error(
                f"Failed to publish database-credentials response: {e}",
                exc_info=True
            )

    def shutdown(self, signum, frame):
        """
        Graceful shutdown handler.

        Called when SIGINT (Ctrl+C) or SIGTERM is received.
        """
        logger.info(f"Received signal {signum}, shutting down event subscriber...")
        self.running = False
        sys.exit(0)
