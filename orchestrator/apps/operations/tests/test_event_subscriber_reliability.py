"""Unit tests for EventSubscriber reliability: receipts, reclaim pending, poison policy."""

import json
from unittest.mock import MagicMock, Mock, patch

from apps.operations.event_subscriber import EventSubscriber
from apps.operations.models import FailedEvent, StreamMessageReceipt

from ._event_subscriber_test_base import EventSubscriberBaseTestCase


class EventSubscriberReliabilityTest(EventSubscriberBaseTestCase):
    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_backfill_worker_results_processes_only_inflight_operations(self, mock_redis_class):
        from apps.operations.models import BatchOperation, StreamMessageReceipt, Task

        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        # Operation still stuck in QUEUED - should be considered for backfill.
        op = BatchOperation.objects.create(
            id="op-backfill-1",
            name="op",
            operation_type=BatchOperation.TYPE_IBCMD_CLI,
            target_entity="Infobase",
            status=BatchOperation.STATUS_QUEUED,
            metadata={"command_id": "infobase.extension.list", "snapshot_kinds": ["extensions"]},
        )
        Task.objects.create(
            id="task-backfill-1",
            batch_operation=op,
            database=None,
            status=Task.STATUS_QUEUED,
        )

        # Completed operation - must be skipped.
        BatchOperation.objects.create(
            id="op-done-1",
            name="done",
            operation_type=BatchOperation.TYPE_IBCMD_CLI,
            target_entity="Infobase",
            status=BatchOperation.STATUS_COMPLETED,
        )

        msg_ok = "100-0"
        data_ok = {"data": json.dumps({"payload": {"operation_id": "op-backfill-1"}})}
        msg_done = "101-0"
        data_done = {"data": json.dumps({"payload": {"operation_id": "op-done-1"}})}

        def xrevrange_side_effect(stream, *_args, **_kwargs):
            if stream == "events:worker:completed":
                return [(msg_done, data_done), (msg_ok, data_ok)]
            if stream == "events:worker:failed":
                return []
            return []

        mock_redis.xrevrange.side_effect = xrevrange_side_effect

        subscriber = EventSubscriber()
        subscriber._handle_message = Mock()

        processed = subscriber.backfill_worker_results(max_messages=10)
        assert processed == 1
        subscriber._handle_message.assert_called_once()
        args = subscriber._handle_message.call_args.args
        assert args[0] == "events:worker:completed"
        assert args[1] == msg_ok
        assert args[2] == data_ok

        # Receipt must still be absent because _handle_message is mocked.
        assert not StreamMessageReceipt.objects.filter(
            stream="events:worker:completed",
            group=subscriber.consumer_group,
            message_id=msg_ok,
        ).exists()

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_duplicate_delivery_does_not_duplicate_side_effects(self, mock_redis_class):
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()
        subscriber.handle_cluster_synced = Mock()

        stream = "events:worker:cluster-synced"
        message_id = "1702389123456-0"
        data = {
            "event_type": "cluster.synced",
            "correlation_id": "corr-123",
            "payload": json.dumps({"ok": True}),
        }

        subscriber._handle_message(stream, message_id, data)
        subscriber._handle_message(stream, message_id, data)

        assert subscriber.handle_cluster_synced.call_count == 1
        assert mock_redis.xack.call_count == 2

        assert StreamMessageReceipt.objects.filter(
            stream=stream,
            group=subscriber.consumer_group,
            message_id=message_id,
        ).count() == 1

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_reclaim_pending_claims_and_processes_messages(self, mock_redis_class):
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()
        subscriber.claim_check_interval_seconds = 0
        subscriber.max_pending_to_check = 10
        subscriber._handle_message = Mock()

        stream_with_pending = "events:worker:completed"
        pending_message_id = "1702389123457-0"

        def xpending_range_side_effect(stream, group, min, max, count, idle):  # noqa: A002
            if stream == stream_with_pending:
                return [{"message_id": pending_message_id}]
            return []

        mock_redis.xpending_range.side_effect = xpending_range_side_effect
        mock_redis.xclaim.return_value = [
            (pending_message_id, {"event_type": "worker.completed", "correlation_id": "corr-1", "payload": "{}"})
        ]

        subscriber._maybe_reclaim_pending()

        mock_redis.xclaim.assert_called()
        subscriber._handle_message.assert_called_once()
        args = subscriber._handle_message.call_args.args
        assert args[0] == stream_with_pending
        assert args[1] == pending_message_id

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_reclaim_pending_redis6_fallback_without_idle_kwarg(self, mock_redis_class):
        import redis as redis_module

        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()
        subscriber.claim_check_interval_seconds = 0
        subscriber.max_pending_to_check = 10
        subscriber.claim_idle_threshold_seconds = 300
        subscriber._handle_message = Mock()

        stream_with_pending = "events:worker:completed"
        stale_message_id = "1702389123461-0"
        fresh_message_id = "1702389123462-0"

        def xpending_range_side_effect(stream, group, min, max, count, idle=None):  # noqa: A002
            if stream != stream_with_pending:
                return []
            if idle is not None:
                raise redis_module.ResponseError("syntax error")
            return [
                {
                    "message_id": stale_message_id,
                    "time_since_delivered": 301000,
                },
                {
                    "message_id": fresh_message_id,
                    "time_since_delivered": 1000,
                },
            ]

        mock_redis.xpending_range.side_effect = xpending_range_side_effect
        mock_redis.xclaim.return_value = [
            (stale_message_id, {"event_type": "worker.completed", "correlation_id": "corr-2", "payload": "{}"})
        ]

        subscriber._maybe_reclaim_pending()

        mock_redis.xclaim.assert_called_once()
        xclaim_args = mock_redis.xclaim.call_args.args
        assert xclaim_args[0] == stream_with_pending
        assert xclaim_args[4] == [stale_message_id]
        subscriber._handle_message.assert_called_once()
        args = subscriber._handle_message.call_args.args
        assert args[0] == stream_with_pending
        assert args[1] == stale_message_id

    @patch("apps.operations.event_subscriber.subscriber.runtime.logger.debug")
    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_query_pending_entries_logs_fallback_once_per_stream_and_reason(
        self,
        mock_redis_class,
        mock_logger_debug,
    ):
        import redis as redis_module

        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()

        def xpending_range_side_effect(stream, group, min, max, count, idle=None):  # noqa: A002
            if idle is not None:
                raise redis_module.ResponseError("syntax error")
            return []

        mock_redis.xpending_range.side_effect = xpending_range_side_effect

        subscriber._query_pending_entries("events:worker:completed", min_idle_time_ms=300000)
        subscriber._query_pending_entries("events:worker:completed", min_idle_time_ms=300000)

        mock_logger_debug.assert_called_once_with(
            "XPENDING IDLE unsupported, fallback scan enabled: stream=%s, group=%s",
            "events:worker:completed",
            subscriber.consumer_group,
        )

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_poison_invalid_json_is_acked_and_recorded(self, mock_redis_class):
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()

        stream = "events:worker:cluster-synced"
        message_id = "1702389123458-0"
        data = {
            "event_type": "cluster.synced",
            "correlation_id": "corr-poison",
            "payload": "invalid-json{",
        }

        subscriber._handle_message(stream, message_id, data)

        mock_redis.xack.assert_called_once_with(stream, subscriber.consumer_group, message_id)
        assert FailedEvent.objects.filter(
            channel=stream,
            correlation_id="corr-poison",
            kind=FailedEvent.KIND_POISON_MESSAGE,
        ).exists()

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_poison_exception_is_acked_and_receipted(self, mock_redis_class):
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()
        subscriber.handle_cluster_synced = Mock(side_effect=ValueError("bad payload"))

        stream = "events:worker:cluster-synced"
        message_id = "1702389123459-0"
        data = {
            "event_type": "cluster.synced",
            "correlation_id": "corr-exc",
            "payload": json.dumps({"ok": True}),
        }

        subscriber._handle_message(stream, message_id, data)

        mock_redis.xack.assert_called_once_with(stream, subscriber.consumer_group, message_id)
        assert FailedEvent.objects.filter(
            channel=stream,
            correlation_id="corr-exc",
            kind=FailedEvent.KIND_POISON_MESSAGE,
        ).exists()
        assert StreamMessageReceipt.objects.filter(
            stream=stream,
            group=subscriber.consumer_group,
            message_id=message_id,
        ).exists()

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_connection_closed_retries_once_and_acks(self, mock_redis_class):
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()

        # Fail first attempt after receipt creation (transaction will rollback),
        # then succeed on retry.
        subscriber._dispatch_message = Mock(
            side_effect=[
                Exception("the connection is closed"),
                None,
            ]
        )

        stream = "events:worker:cluster-synced"
        message_id = "1702389123460-0"
        data = {
            "event_type": "cluster.synced",
            "correlation_id": "corr-closed",
            "payload": json.dumps({"ok": True}),
        }

        with patch("apps.operations.event_subscriber.runtime.close_old_connections") as mock_close:
            subscriber._handle_message(stream, message_id, data)

            # 1) initial call at start of _handle_message
            # 2) retry call after detecting "the connection is closed"
            assert mock_close.call_count == 2

        assert subscriber._dispatch_message.call_count == 2
        mock_redis.xack.assert_called_once_with(stream, subscriber.consumer_group, message_id)
        assert StreamMessageReceipt.objects.filter(
            stream=stream,
            group=subscriber.consumer_group,
            message_id=message_id,
        ).exists()
