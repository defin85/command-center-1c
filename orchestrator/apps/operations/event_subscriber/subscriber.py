"""
Event Subscriber for Redis Streams from Go services.

Implements a Consumer Group-based subscriber for Redis Streams, allowing
the orchestrator to receive events from Go services (worker).
"""

import json
import os
import signal
import sys
import time
from typing import Any, Dict, Optional

import redis
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .handlers_cluster import ClusterEventHandlersMixin
from .handlers_commands import CommandHandlersMixin
from .handlers_misc import MiscEventHandlersMixin
from .handlers_worker import WorkerEventHandlersMixin
from .metrics import (
    record_claimed_metric,
    record_duplicate_receipt_metric,
    record_event_metric,
    record_poison_metric,
)
from . import runtime
from .updates import TaskAndDatabaseUpdatesMixin
from apps.operations.models import StreamMessageReceipt


class EventSubscriber(
    ClusterEventHandlersMixin,
    WorkerEventHandlersMixin,
    MiscEventHandlersMixin,
    CommandHandlersMixin,
    TaskAndDatabaseUpdatesMixin,
):
    """
    Subscribes to Redis Streams from Go services using Redis Streams consumer groups.

    Supported streams:
    - events:worker:cluster-synced
    - events:worker:clusters-discovered
    - events:worker:completed
    - events:worker:failed
    - commands:worker:dlq
    - commands:orchestrator:get-cluster-info
    - commands:orchestrator:get-database-credentials
    """

    def __init__(self):
        redis_password = getattr(settings, "REDIS_PASSWORD", None)

        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=int(settings.REDIS_PORT),
            password=redis_password if redis_password else None,
            decode_responses=True,
        )

        self.consumer_group = "orchestrator-group"
        self.consumer_name = f"orchestrator-{os.getpid()}"
        self.running = True

        self.claim_idle_threshold_seconds = int(
            getattr(settings, "EVENT_SUBSCRIBER_CLAIM_IDLE_THRESHOLD_SECONDS", 5 * 60)
        )
        self.claim_check_interval_seconds = int(
            getattr(settings, "EVENT_SUBSCRIBER_CLAIM_CHECK_INTERVAL_SECONDS", 30)
        )
        self.max_pending_to_check = int(
            getattr(settings, "EVENT_SUBSCRIBER_MAX_PENDING_TO_CHECK", 100)
        )
        self._last_claim_check_at = 0.0

        self.streams = {
            "events:worker:cluster-synced": ">",
            "events:worker:clusters-discovered": ">",
            "events:worker:completed": ">",
            "events:worker:failed": ">",
            "commands:worker:dlq": ">",
            "commands:orchestrator:get-cluster-info": ">",
            "commands:orchestrator:get-database-credentials": ">",
        }

        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

        runtime.logger.info("EventSubscriber initialized: %s", self.consumer_name)

    def setup_consumer_groups(self):
        for stream in self.streams.keys():
            try:
                self.redis_client.xgroup_create(
                    stream,
                    self.consumer_group,
                    id="$",
                    mkstream=True,
                )
                runtime.logger.info(
                    "Created consumer group '%s' for stream '%s'",
                    self.consumer_group,
                    stream,
                )
            except redis.ResponseError as e:
                if "BUSYGROUP" in str(e):
                    runtime.logger.debug(
                        "Consumer group '%s' already exists for '%s'",
                        self.consumer_group,
                        stream,
                    )
                else:
                    runtime.logger.error(
                        "Error creating consumer group for '%s': %s", stream, e
                    )
                    raise

    def run_forever(self):
        runtime.logger.info("Event subscriber starting: %s", self.consumer_name)
        runtime.logger.info("Subscribed to %s streams", len(self.streams))

        self.setup_consumer_groups()

        while self.running:
            try:
                self._maybe_reclaim_pending()

                messages = self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    self.streams,
                    count=10,
                    block=1000,
                )

                for stream_name, stream_messages in messages:
                    for message_id, data in stream_messages:
                        self._handle_message(stream_name, message_id, data)

            except redis.ConnectionError as e:
                runtime.logger.error("Redis connection lost: %s, retrying in 5s...", e)
                time.sleep(5)
            except Exception as e:
                runtime.logger.error(
                    "Unexpected error in event loop: %s", e, exc_info=True
                )
                time.sleep(1)

        runtime.logger.info("Event subscriber stopped")

    def _maybe_reclaim_pending(self) -> None:
        now = time.time()
        if now - self._last_claim_check_at < self.claim_check_interval_seconds:
            return
        self._last_claim_check_at = now

        min_idle_time_ms = self.claim_idle_threshold_seconds * 1000

        for stream in self.streams.keys():
            try:
                pending_entries = self.redis_client.xpending_range(
                    stream,
                    self.consumer_group,
                    min="-",
                    max="+",
                    count=self.max_pending_to_check,
                    idle=min_idle_time_ms,
                )
            except Exception as e:
                runtime.logger.debug(
                    "Failed to query pending entries: stream=%s, group=%s, error=%s",
                    stream,
                    self.consumer_group,
                    e,
                )
                continue

            if not pending_entries:
                continue

            message_ids: list[str] = []
            for entry in pending_entries:
                # redis-py returns dicts with message_id in newer versions; keep fallback for safety.
                msg_id = entry.get("message_id") or entry.get("id")
                if msg_id:
                    message_ids.append(msg_id)

            if not message_ids:
                continue

            try:
                claimed = self.redis_client.xclaim(
                    stream,
                    self.consumer_group,
                    self.consumer_name,
                    min_idle_time_ms,
                    message_ids,
                )
            except Exception as e:
                runtime.logger.debug(
                    "Failed to claim pending entries: stream=%s, group=%s, error=%s",
                    stream,
                    self.consumer_group,
                    e,
                )
                continue

            for claimed_message_id, claimed_data in claimed:
                runtime.logger.info(
                    "Claimed pending message: stream=%s, group=%s, message_id=%s",
                    stream,
                    self.consumer_group,
                    claimed_message_id,
                )
                record_claimed_metric(stream, self.consumer_group, 1)
                self._handle_message(stream, claimed_message_id, claimed_data)

    def _handle_message(self, stream: str, message_id: str, data: Dict[str, str]) -> None:
        runtime.close_old_connections()

        event_type = data.get("event_type", "unknown")
        correlation_id = data.get("correlation_id", "unknown")
        handler = self._handler_name_for_stream(stream)

        processed_ok = False
        try:
            # Long-lived consumer processes sometimes retain a closed psycopg connection
            # wrapper, causing OperationalError("the connection is closed") mid-flight.
            # Retry once after forcing a connection refresh.
            for attempt in range(2):
                try:
                    with transaction.atomic():
                        StreamMessageReceipt.objects.create(
                            stream=stream,
                            group=self.consumer_group,
                            message_id=message_id,
                            event_type=event_type,
                            correlation_id=correlation_id,
                            handler=handler,
                        )
                        self._dispatch_message(stream, message_id, data)
                    processed_ok = True
                    break
                except Exception as e:
                    if attempt == 0 and "the connection is closed" in str(e).lower():
                        runtime.logger.warning(
                            "DB connection closed while handling message, retrying once: stream=%s, group=%s, message_id=%s",
                            stream,
                            self.consumer_group,
                            message_id,
                        )
                        runtime.close_old_connections()
                        continue
                    raise

        except IntegrityError:
            runtime.logger.debug(
                "Duplicate stream message receipt, ACK without side effects: stream=%s, group=%s, message_id=%s",
                stream,
                self.consumer_group,
                message_id,
            )
            record_duplicate_receipt_metric(stream, self.consumer_group, 1)
            self.redis_client.xack(stream, self.consumer_group, message_id)
            return

        except Exception as e:
            if self._is_poison_exception(e):
                runtime.logger.error(
                    "Poison message detected, ACKing to avoid pending growth: stream=%s, group=%s, message_id=%s",
                    stream,
                    self.consumer_group,
                    message_id,
                    exc_info=True,
                )
                self._record_poison_message(
                    stream=stream,
                    message_id=message_id,
                    data=data,
                    event_type=event_type,
                    correlation_id=correlation_id,
                    handler=handler,
                    reason=f"exception_{type(e).__name__}",
                    error=str(e),
                )
                try:
                    with transaction.atomic():
                        StreamMessageReceipt.objects.create(
                            stream=stream,
                            group=self.consumer_group,
                            message_id=message_id,
                            event_type=event_type,
                            correlation_id=correlation_id,
                            handler=handler,
                        )
                except IntegrityError:
                    pass
                self.redis_client.xack(stream, self.consumer_group, message_id)
                return

            runtime.logger.error(
                "Error processing message %s from %s: %s",
                message_id,
                stream,
                e,
                exc_info=True,
            )
            # Don't ACK - message will be retried later (pending/claim)
            return

        if not processed_ok:
            return

        # ACK only after DB transaction is committed successfully.
        try:
            self.redis_client.xack(stream, self.consumer_group, message_id)
        except Exception as e:
            runtime.logger.error(
                "Failed to ACK message %s from %s: %s",
                message_id,
                stream,
                e,
                exc_info=True,
            )

    def process_message(self, stream: str, message_id: str, data: Dict[str, str]):
        runtime.close_old_connections()
        self._dispatch_message(stream, message_id, data)

    def _dispatch_message(self, stream: str, message_id: str, data: Dict[str, str]) -> None:
        event_type = data.get("event_type", "unknown")
        correlation_id = data.get("correlation_id", "unknown")

        payload_str = data.get("payload", "{}")
        try:
            payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
        except json.JSONDecodeError as e:
            runtime.logger.error("Invalid JSON payload in message %s: %s", message_id, e)
            self._record_poison_message(
                stream=stream,
                message_id=message_id,
                data=data,
                event_type=event_type,
                correlation_id=correlation_id,
                handler=self._handler_name_for_stream(stream),
                reason="invalid_json_payload",
                error=str(e),
            )
            return

        runtime.logger.info(
            "Processing event: %s (stream=%s, correlation_id=%s, msg_id=%s)",
            event_type,
            stream,
            correlation_id,
            message_id,
        )

        record_event_metric(event_type, stream)

        if "cluster-synced" in stream:
            self.handle_cluster_synced(payload, correlation_id)
        elif "clusters-discovered" in stream:
            self.handle_clusters_discovered(payload, correlation_id)
        elif "worker:completed" in stream:
            self.handle_worker_completed(data, correlation_id)
        elif "worker:failed" in stream:
            self.handle_worker_failed(data, correlation_id)
        elif "worker:dlq" in stream:
            self.handle_dlq_message(data, correlation_id)
        elif "get-cluster-info" in stream:
            self.handle_get_cluster_info(data, correlation_id)
        elif "get-database-credentials" in stream:
            self.handle_get_database_credentials(data, correlation_id)
        else:
            runtime.logger.warning("Unknown stream: %s", stream)
            self._record_poison_message(
                stream=stream,
                message_id=message_id,
                data=data,
                event_type=event_type,
                correlation_id=correlation_id,
                handler="",
                reason="unknown_stream",
                error="",
            )

    @staticmethod
    def _handler_name_for_stream(stream: str) -> str:
        if "cluster-synced" in stream:
            return "handle_cluster_synced"
        if "clusters-discovered" in stream:
            return "handle_clusters_discovered"
        if "worker:completed" in stream:
            return "handle_worker_completed"
        if "worker:failed" in stream:
            return "handle_worker_failed"
        if "worker:dlq" in stream:
            return "handle_dlq_message"
        if "get-cluster-info" in stream:
            return "handle_get_cluster_info"
        if "get-database-credentials" in stream:
            return "handle_get_database_credentials"
        return ""

    @staticmethod
    def _is_poison_exception(exc: BaseException) -> bool:
        return isinstance(exc, (json.JSONDecodeError, KeyError, TypeError, ValueError))

    def _record_poison_message(
        self,
        *,
        stream: str,
        message_id: str,
        data: Dict[str, str],
        event_type: str,
        correlation_id: str,
        handler: str,
        reason: str,
        error: str,
    ) -> None:
        """
        Persist poison message details for manual inspection.

        This intentionally ACKs poison messages so they do not remain pending forever.
        """
        from apps.operations.models import FailedEvent

        timestamp_str = data.get("timestamp") if isinstance(data.get("timestamp"), str) else None
        original_timestamp = parse_datetime(timestamp_str) if timestamp_str else None
        if original_timestamp is None:
            original_timestamp = timezone.now()
        elif timezone.is_naive(original_timestamp):
            original_timestamp = timezone.make_aware(original_timestamp)

        try:
            record_poison_metric(stream, self.consumer_group, reason, 1)
            FailedEvent.objects.create(
                channel=stream[:255],
                event_type=str(event_type or "unknown")[:100],
                correlation_id=str(correlation_id or "unknown")[:64],
                payload={
                    "stream": stream,
                    "group": self.consumer_group,
                    "message_id": message_id,
                    "handler": handler,
                    "reason": reason,
                    "data": data,
                    "error": error,
                },
                kind=FailedEvent.KIND_POISON_MESSAGE,
                source_service="event_subscriber",
                original_timestamp=original_timestamp,
                status=FailedEvent.STATUS_FAILED,
                retry_count=0,
                max_retries=0,
                last_error=str(error),
            )
        except Exception as e:
            runtime.logger.error(
                "Failed to record poison message: stream=%s, message_id=%s, error=%s",
                stream,
                message_id,
                e,
                exc_info=True,
            )

    def shutdown(self, signum, frame):
        runtime.logger.info(
            "Received signal %s, shutting down event subscriber...", signum
        )
        self.running = False
        sys.exit(0)
