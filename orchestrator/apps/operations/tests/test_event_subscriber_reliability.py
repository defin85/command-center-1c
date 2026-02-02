"""Unit tests for EventSubscriber reliability: receipts, reclaim pending, poison policy."""

import json
from unittest.mock import MagicMock, Mock, patch

from apps.operations.event_subscriber import EventSubscriber
from apps.operations.models import FailedEvent, StreamMessageReceipt

from ._event_subscriber_test_base import EventSubscriberBaseTestCase


class EventSubscriberReliabilityTest(EventSubscriberBaseTestCase):
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
