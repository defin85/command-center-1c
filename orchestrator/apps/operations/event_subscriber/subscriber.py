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
from typing import Any, Dict

import redis
from django.conf import settings

from .handlers_cluster import ClusterEventHandlersMixin
from .handlers_commands import CommandHandlersMixin
from .handlers_misc import MiscEventHandlersMixin
from .handlers_worker import WorkerEventHandlersMixin
from .metrics import record_event_metric
from . import runtime
from .updates import TaskAndDatabaseUpdatesMixin


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
                messages = self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    self.streams,
                    count=10,
                    block=1000,
                )

                for stream_name, stream_messages in messages:
                    for message_id, data in stream_messages:
                        try:
                            self.process_message(stream_name, message_id, data)
                            self.redis_client.xack(
                                stream_name, self.consumer_group, message_id
                            )
                        except Exception as e:
                            runtime.logger.error(
                                "Error processing message %s from %s: %s",
                                message_id,
                                stream_name,
                                e,
                                exc_info=True,
                            )
                            # Don't ACK - message will be retried later

            except redis.ConnectionError as e:
                runtime.logger.error("Redis connection lost: %s, retrying in 5s...", e)
                time.sleep(5)
            except Exception as e:
                runtime.logger.error(
                    "Unexpected error in event loop: %s", e, exc_info=True
                )
                time.sleep(1)

        runtime.logger.info("Event subscriber stopped")

    def process_message(self, stream: str, message_id: str, data: Dict[str, str]):
        runtime.close_old_connections()

        event_type = data.get("event_type", "unknown")
        correlation_id = data.get("correlation_id", "unknown")

        payload_str = data.get("payload", "{}")
        try:
            payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
        except json.JSONDecodeError as e:
            runtime.logger.error("Invalid JSON payload in message %s: %s", message_id, e)
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

    def shutdown(self, signum, frame):
        runtime.logger.info(
            "Received signal %s, shutting down event subscriber...", signum
        )
        self.running = False
        sys.exit(0)
