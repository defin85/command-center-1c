"""
Event Subscriber for Redis Streams from Go services.

This module implements a Consumer Group-based subscriber for Redis Streams,
allowing Django Orchestrator to receive events from Go services (batch-service, cluster-service).

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
import threading
from typing import Dict, Any, Optional
import redis
from django.conf import settings
from django.db import transaction, close_old_connections
import logging

from apps.operations.models import Task

logger = logging.getLogger(__name__)


class EventSubscriber:
    """
    Subscribes to Redis Streams and Pub/Sub from Go services.

    Uses two mechanisms:
    1. Redis Streams with Consumer Groups - for guaranteed delivery of events
    2. Redis Pub/Sub - for real-time operation status updates

    Supported Stream Events:
    - batch-service:extension:installed
    - batch-service:extension:install-failed
    - cluster-service:infobase:locked
    - cluster-service:infobase:unlocked
    - cluster-service:sessions:closed
    - worker:cluster-synced
    - worker:clusters-discovered

    Supported Pub/Sub Patterns:
    - operation:*:events - Real-time operation status updates from Go Worker
      (states: PROCESSING, SUCCESS, FAILED)
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

        # Pub/Sub client for operation events from Go Worker
        self.pubsub_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=int(settings.REDIS_PORT),
            password=redis_password if redis_password else None,
            decode_responses=True
        )
        self.pubsub = None
        self.pubsub_thread = None

        # Streams to subscribe to (stream_name: last_id)
        # '>' means read only new messages
        self.streams = {
            'events:batch-service:extension:installed': '>',
            'events:batch-service:extension:install-failed': '>',
            'events:cluster-service:infobase:locked': '>',
            'events:cluster-service:infobase:unlocked': '>',
            'events:cluster-service:sessions:closed': '>',
            'events:worker:cluster-synced': '>',
            'events:worker:clusters-discovered': '>',
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

        # Start Pub/Sub listener for operation events in separate thread
        self._start_pubsub_listener()

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

        # Stop Pub/Sub listener
        self._stop_pubsub_listener()

    def _start_pubsub_listener(self):
        """
        Start Pub/Sub listener for operation events in a separate thread.

        Subscribes to pattern `operation:*:events` to receive real-time
        status updates from Go Worker.
        """
        try:
            self.pubsub = self.pubsub_client.pubsub()
            self.pubsub.psubscribe(**{'operation:*:events': self._pubsub_message_handler})

            # Start listener thread
            self.pubsub_thread = threading.Thread(
                target=self._run_pubsub_listener,
                name="pubsub-operation-listener",
                daemon=True
            )
            self.pubsub_thread.start()
            logger.info("Pub/Sub listener started for pattern 'operation:*:events'")

        except Exception as e:
            logger.error(f"Failed to start Pub/Sub listener: {e}", exc_info=True)

    def _stop_pubsub_listener(self):
        """Stop Pub/Sub listener and cleanup resources."""
        try:
            if self.pubsub:
                self.pubsub.punsubscribe()
                self.pubsub.close()
                logger.info("Pub/Sub listener stopped")
        except Exception as e:
            logger.error(f"Error stopping Pub/Sub listener: {e}")

    def _run_pubsub_listener(self):
        """
        Run Pub/Sub listener loop in separate thread.

        Reads messages from subscribed patterns and dispatches to handlers.
        Reconnects automatically on connection errors.
        """
        logger.info("Pub/Sub listener thread started")

        while self.running:
            try:
                # get_message() with timeout to allow graceful shutdown
                message = self.pubsub.get_message(timeout=1.0)
                if message is None:
                    continue

                # Skip subscribe/unsubscribe confirmation messages
                if message['type'] in ('psubscribe', 'punsubscribe'):
                    continue

                # Pattern messages have type 'pmessage'
                if message['type'] == 'pmessage':
                    # Already handled by _pubsub_message_handler via callback
                    pass

            except redis.ConnectionError as e:
                logger.error(f"Pub/Sub connection lost: {e}, reconnecting in 5s...")
                time.sleep(5)
                try:
                    self._reconnect_pubsub()
                except Exception as re:
                    logger.error(f"Pub/Sub reconnection failed: {re}")

            except Exception as e:
                logger.error(f"Error in Pub/Sub listener: {e}", exc_info=True)
                time.sleep(1)

        logger.info("Pub/Sub listener thread stopped")

    def _reconnect_pubsub(self):
        """Reconnect Pub/Sub after connection loss."""
        try:
            if self.pubsub:
                self.pubsub.close()
        except Exception:
            pass

        redis_password = getattr(settings, 'REDIS_PASSWORD', None)
        self.pubsub_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=int(settings.REDIS_PORT),
            password=redis_password if redis_password else None,
            decode_responses=True
        )
        self.pubsub = self.pubsub_client.pubsub()
        self.pubsub.psubscribe(**{'operation:*:events': self._pubsub_message_handler})
        logger.info("Pub/Sub reconnected successfully")

    def _pubsub_message_handler(self, message: dict):
        """
        Callback handler for Pub/Sub messages.

        Called by redis-py for each message matching subscribed pattern.

        Args:
            message: Dict with keys: type, pattern, channel, data
        """
        channel = message.get('channel', '')
        data_str = message.get('data', '')

        logger.debug(f"Pub/Sub message received: channel={channel}")

        try:
            # Parse JSON data
            if isinstance(data_str, str) and data_str:
                data = json.loads(data_str)
            else:
                logger.warning(f"Empty or invalid Pub/Sub data from {channel}")
                return

            # Handle the operation event
            self.handle_operation_pubsub_event(channel, data)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in Pub/Sub message from {channel}: {e}")
        except Exception as e:
            logger.error(f"Error handling Pub/Sub message from {channel}: {e}", exc_info=True)

    def handle_operation_pubsub_event(self, channel: str, data: Dict[str, Any]):
        """
        Handle operation event from Go Worker via Pub/Sub.

        Updates BatchOperation status based on event state.

        Channel format: operation:{operation_id}:events
        Data format:
            {
                "version": "1.0",
                "operation_id": "uuid",
                "timestamp": "2025-12-10T...",
                "state": "PROCESSING|SUCCESS|FAILED",
                "microservice": "worker",
                "message": "...",
                "metadata": {...}
            }

        Args:
            channel: Redis Pub/Sub channel name
            data: Parsed event data dict
        """
        from apps.operations.models import BatchOperation

        operation_id = data.get('operation_id')
        state = data.get('state')
        message = data.get('message', '')
        metadata = data.get('metadata', {})
        # timestamp available but not used currently: data.get('timestamp', '')

        if not operation_id or not state:
            logger.warning(f"Invalid Pub/Sub event - missing operation_id or state: {data}")
            return

        logger.info(
            f"Processing Pub/Sub event: operation_id={operation_id}, "
            f"state={state}, message={message[:100] if message else ''}"
        )

        try:
            # Close old Django DB connections in this thread
            close_old_connections()

            batch_op = BatchOperation.objects.get(id=operation_id)

            # Map Go Worker state to BatchOperation status
            if state == 'PROCESSING':
                batch_op.status = BatchOperation.STATUS_PROCESSING
                if not batch_op.started_at:
                    from django.utils import timezone
                    batch_op.started_at = timezone.now()
                update_fields = ['status', 'started_at', 'updated_at']

            elif state == 'SUCCESS':
                batch_op.status = BatchOperation.STATUS_COMPLETED
                batch_op.progress = 100
                if not batch_op.completed_at:
                    from django.utils import timezone
                    batch_op.completed_at = timezone.now()

                # Store success metadata
                if metadata:
                    batch_op.metadata['worker_result'] = metadata
                if message:
                    batch_op.metadata['worker_message'] = message

                update_fields = ['status', 'progress', 'completed_at', 'metadata', 'updated_at']

            elif state == 'FAILED':
                batch_op.status = BatchOperation.STATUS_FAILED
                if not batch_op.completed_at:
                    from django.utils import timezone
                    batch_op.completed_at = timezone.now()

                # Store error info
                batch_op.metadata['error'] = message
                if metadata:
                    batch_op.metadata['error_details'] = metadata

                update_fields = ['status', 'completed_at', 'metadata', 'updated_at']

            else:
                logger.warning(f"Unknown state '{state}' for operation {operation_id}")
                return

            batch_op.save(update_fields=update_fields)
            logger.info(f"Updated BatchOperation {operation_id} status to {batch_op.status}")

        except BatchOperation.DoesNotExist:
            logger.warning(f"BatchOperation not found: {operation_id}")
        except Exception as e:
            logger.error(
                f"Error updating BatchOperation {operation_id}: {e}",
                exc_info=True
            )

    def process_message(self, stream: str, message_id: str, data: Dict[str, str]):
        """
        Process a single message from a stream.

        Args:
            stream: Stream name (e.g., 'events:batch-service:extension:installed')
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

        # Route to appropriate handler based on stream name
        if 'extension:installed' in stream:
            self.handle_extension_installed(payload, correlation_id)

        elif 'extension:install-failed' in stream:
            self.handle_extension_failed(payload, correlation_id)

        elif 'infobase:locked' in stream:
            self.handle_infobase_locked(payload, correlation_id)

        elif 'infobase:unlocked' in stream:
            self.handle_infobase_unlocked(payload, correlation_id)

        elif 'sessions:closed' in stream:
            self.handle_sessions_closed(payload, correlation_id)

        elif 'cluster-synced' in stream:
            self.handle_cluster_synced(payload, correlation_id)

        elif 'clusters-discovered' in stream:
            self.handle_clusters_discovered(payload, correlation_id)

        else:
            logger.warning(f"Unknown stream: {stream}")

    def handle_extension_installed(self, payload: Dict[str, Any], correlation_id: str):
        """
        Handle extension installed event from batch-service.

        Payload example:
            {
                'database_id': 'db-123',
                'extension_name': 'TestExtension',
                'extension_version': '1.0.0',
                'duration_seconds': 45.2,
                'output': 'Extension installed successfully'
            }
        """
        database_id = payload.get('database_id')
        extension_name = payload.get('extension_name', 'unknown')
        duration = payload.get('duration_seconds', 0)

        logger.info(
            f"Extension installed: database={database_id}, "
            f"name={extension_name}, duration={duration:.2f}s, "
            f"correlation_id={correlation_id}"
        )

        # Update Task status if we can find it by correlation_id
        # correlation_id format: "batch-<batch_op_id>-<task_id>"
        self._update_task_status_from_correlation_id(
            correlation_id=correlation_id,
            status=Task.STATUS_COMPLETED,
            result=payload
        )

    def handle_extension_failed(self, payload: Dict[str, Any], correlation_id: str):
        """
        Handle extension install failed event from batch-service.

        Payload example:
            {
                'database_id': 'db-123',
                'extension_name': 'TestExtension',
                'error': 'Connection timeout',
                'error_code': 'TIMEOUT',
                'duration_seconds': 30.0
            }
        """
        database_id = payload.get('database_id')
        error = payload.get('error', 'Unknown error')
        error_code = payload.get('error_code', 'UNKNOWN')

        logger.error(
            f"Extension install failed: database={database_id}, "
            f"error={error}, code={error_code}, correlation_id={correlation_id}"
        )

        # Update Task status
        self._update_task_status_from_correlation_id(
            correlation_id=correlation_id,
            status=Task.STATUS_FAILED,
            error_message=error,
            error_code=error_code
        )

    def handle_infobase_locked(self, payload: Dict[str, Any], correlation_id: str):
        """
        Handle infobase locked event from cluster-service.

        Payload example:
            {
                'cluster_id': 'cluster-uuid',
                'infobase_id': 'infobase-uuid',
                'reason': 'maintenance'
            }
        """
        infobase_id = payload.get('infobase_id')
        reason = payload.get('reason', 'unknown')

        logger.info(
            f"Infobase locked: infobase={infobase_id}, "
            f"reason={reason}, correlation_id={correlation_id}"
        )

        # TODO: Update Database model status when implemented
        # Database.objects.filter(infobase_uuid=infobase_id).update(
        #     status='locked',
        #     lock_reason=reason,
        #     updated_at=timezone.now()
        # )

    def handle_infobase_unlocked(self, payload: Dict[str, Any], correlation_id: str):
        """
        Handle infobase unlocked event from cluster-service.

        Payload example:
            {
                'cluster_id': 'cluster-uuid',
                'infobase_id': 'infobase-uuid'
            }
        """
        infobase_id = payload.get('infobase_id')

        logger.info(
            f"Infobase unlocked: infobase={infobase_id}, "
            f"correlation_id={correlation_id}"
        )

        # TODO: Update Database model status when implemented
        # Database.objects.filter(infobase_uuid=infobase_id).update(
        #     status='active',
        #     lock_reason='',
        #     updated_at=timezone.now()
        # )

    def handle_sessions_closed(self, payload: Dict[str, Any], correlation_id: str):
        """
        Handle sessions closed event from cluster-service.

        Payload example:
            {
                'cluster_id': 'cluster-uuid',
                'infobase_id': 'infobase-uuid',
                'sessions_closed': 5,
                'duration_seconds': 2.3
            }
        """
        infobase_id = payload.get('infobase_id')
        sessions_closed = payload.get('sessions_closed', 0)
        duration = payload.get('duration_seconds', 0)

        logger.info(
            f"Sessions closed: infobase={infobase_id}, "
            f"count={sessions_closed}, duration={duration:.2f}s, "
            f"correlation_id={correlation_id}"
        )

        # TODO: Log to monitoring/audit system when implemented

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
            with transaction.atomic():
                if success and clusters_data:
                    for cluster_data in clusters_data:
                        cluster_uuid = cluster_data.get('uuid')
                        cluster_name = cluster_data.get('name', 'Unknown')

                        # Try to find existing cluster by ras_cluster_uuid
                        # cluster_service_url points to RAS Adapter
                        from django.conf import settings
                        adapter_url = getattr(
                            settings, 'RAS_ADAPTER_URL', 'http://localhost:8188'
                        )
                        cluster, is_new = Cluster.objects.update_or_create(
                            ras_cluster_uuid=cluster_uuid,
                            defaults={
                                'name': cluster_name,
                                'ras_server': ras_server,
                                'cluster_service_url': adapter_url,
                                'status': 'active',
                                'metadata': cluster_data,
                            }
                        )

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

    def shutdown(self, signum, frame):
        """
        Graceful shutdown handler.

        Called when SIGINT (Ctrl+C) or SIGTERM is received.
        """
        logger.info(f"Received signal {signum}, shutting down event subscriber...")
        self.running = False
        sys.exit(0)
