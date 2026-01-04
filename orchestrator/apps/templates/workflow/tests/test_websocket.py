"""
Tests for WebSocket consumer (Django Channels).

Tests:
- Consumer connection lifecycle
- Message handling (workflow_update, node_update, etc.)
- Broadcast helper functions
- Error handling
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.test import TestCase

from apps.templates.consumers import (
    WorkflowExecutionConsumer,
    broadcast_workflow_update,
    broadcast_node_update,
    broadcast_execution_completed,
)


# ============================================================================
# Test fixtures
# ============================================================================

@pytest.fixture
def execution_id():
    """Generate a valid UUID for testing."""
    return str(uuid4())


@pytest.fixture
def invalid_execution_id():
    """Generate an invalid UUID string."""
    return "not-a-valid-uuid"


@pytest.fixture
def mock_execution(execution_id):
    """Create a mock WorkflowExecution."""
    mock = MagicMock()
    mock.id = execution_id
    mock.status = 'running'
    mock.progress_percent = 50
    mock.current_node_id = 'node_1'
    mock.trace_id = 'trace-123'
    mock.error_message = None
    mock.node_statuses = {'node_1': {'status': 'completed'}}
    mock.started_at = MagicMock()
    mock.started_at.isoformat.return_value = '2025-01-01T00:00:00Z'
    mock.completed_at = None
    return mock


# ============================================================================
# Consumer Unit Tests
# ============================================================================

class TestWorkflowExecutionConsumerUnit(TestCase):
    """Unit tests for WorkflowExecutionConsumer."""

    def test_group_prefix(self):
        """Test that GROUP_PREFIX is set correctly."""
        self.assertEqual(
            WorkflowExecutionConsumer.GROUP_PREFIX,
            "workflow_execution_"
        )

    def test_consumer_initialization(self):
        """Test consumer initializes with correct defaults."""
        consumer = WorkflowExecutionConsumer()
        self.assertIsNone(consumer.execution_id)
        self.assertIsNone(consumer.group_name)
        self.assertEqual(consumer.subscribed_nodes, set())


# ============================================================================
# Consumer Integration Tests (with channels testing)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestWorkflowExecutionConsumerIntegration:
    """Integration tests for WorkflowExecutionConsumer."""

    @pytest.fixture(autouse=True)
    def setup_method(self, execution_id, mock_execution):
        """Set up test fixtures."""
        self.execution_id = execution_id
        self.mock_execution = mock_execution

    async def test_connect_with_valid_execution_id(self, execution_id, mock_execution):
        """Test WebSocket connects with valid execution ID."""
        with patch.object(
            WorkflowExecutionConsumer,
            '_get_execution',
            new_callable=AsyncMock,
            return_value=mock_execution
        ):
            communicator = WebsocketCommunicator(
                WorkflowExecutionConsumer.as_asgi(),
                f"/ws/workflow/{execution_id}/"
            )
            communicator.scope["url_route"] = {"kwargs": {"execution_id": execution_id}}

            connected, _ = await communicator.connect()
            assert connected is True

            await communicator.disconnect()

    async def test_connect_with_invalid_uuid_format(self, invalid_execution_id):
        """Test WebSocket rejects connection with invalid UUID format."""
        communicator = WebsocketCommunicator(
            WorkflowExecutionConsumer.as_asgi(),
            f"/ws/workflow/{invalid_execution_id}/"
        )
        communicator.scope["url_route"] = {"kwargs": {"execution_id": invalid_execution_id}}

        connected, close_code = await communicator.connect()
        # Should close with code 4001 for invalid format
        assert connected is False or close_code == 4001

    async def test_connect_with_missing_execution_id(self):
        """Test WebSocket rejects connection with missing execution ID."""
        communicator = WebsocketCommunicator(
            WorkflowExecutionConsumer.as_asgi(),
            "/ws/workflow//"
        )
        communicator.scope["url_route"] = {"kwargs": {}}

        connected, close_code = await communicator.connect()
        # Should close with code 4000 for missing ID
        assert connected is False or close_code == 4000

    async def test_connect_with_nonexistent_execution(self, execution_id):
        """Test WebSocket rejects connection for non-existent execution."""
        with patch.object(
            WorkflowExecutionConsumer,
            '_get_execution',
            new_callable=AsyncMock,
            return_value=None
        ):
            communicator = WebsocketCommunicator(
                WorkflowExecutionConsumer.as_asgi(),
                f"/ws/workflow/{execution_id}/"
            )
            communicator.scope["url_route"] = {"kwargs": {"execution_id": execution_id}}

            connected, close_code = await communicator.connect()
            # Should close with code 4004 for not found
            assert connected is False or close_code == 4004

    async def test_receive_get_status_action(self, execution_id, mock_execution):
        """Test receiving get_status action returns current status."""
        with patch.object(
            WorkflowExecutionConsumer,
            '_get_execution',
            new_callable=AsyncMock,
            return_value=mock_execution
        ):
            communicator = WebsocketCommunicator(
                WorkflowExecutionConsumer.as_asgi(),
                f"/ws/workflow/{execution_id}/"
            )
            communicator.scope["url_route"] = {"kwargs": {"execution_id": execution_id}}

            await communicator.connect()

            # Clear initial status message
            await communicator.receive_json_from()

            # Send get_status action
            await communicator.send_json_to({"action": "get_status"})

            # Receive response
            response = await communicator.receive_json_from()
            assert response["type"] == "workflow_status"
            assert response["status"] == "running"

            await communicator.disconnect()

    async def test_receive_ping_action(self, execution_id, mock_execution):
        """Test ping action returns pong."""
        with patch.object(
            WorkflowExecutionConsumer,
            '_get_execution',
            new_callable=AsyncMock,
            return_value=mock_execution
        ):
            communicator = WebsocketCommunicator(
                WorkflowExecutionConsumer.as_asgi(),
                f"/ws/workflow/{execution_id}/"
            )
            communicator.scope["url_route"] = {"kwargs": {"execution_id": execution_id}}

            await communicator.connect()

            # Clear initial status message
            await communicator.receive_json_from()

            # Send ping
            await communicator.send_json_to({"action": "ping"})

            # Receive pong
            response = await communicator.receive_json_from()
            assert response["type"] == "pong"

            await communicator.disconnect()

    async def test_receive_subscribe_nodes_action(self, execution_id, mock_execution):
        """Test subscribe_nodes action updates subscriptions."""
        with patch.object(
            WorkflowExecutionConsumer,
            '_get_execution',
            new_callable=AsyncMock,
            return_value=mock_execution
        ):
            communicator = WebsocketCommunicator(
                WorkflowExecutionConsumer.as_asgi(),
                f"/ws/workflow/{execution_id}/"
            )
            communicator.scope["url_route"] = {"kwargs": {"execution_id": execution_id}}

            await communicator.connect()

            # Clear initial status message
            await communicator.receive_json_from()

            # Subscribe to nodes
            await communicator.send_json_to({
                "action": "subscribe_nodes",
                "node_ids": ["node_1", "node_2"]
            })

            # Receive subscription confirmation
            response = await communicator.receive_json_from()
            assert response["type"] == "subscription_update"
            assert set(response["subscribed_nodes"]) == {"node_1", "node_2"}

            await communicator.disconnect()

    async def test_receive_unknown_action(self, execution_id, mock_execution):
        """Test unknown action returns error."""
        with patch.object(
            WorkflowExecutionConsumer,
            '_get_execution',
            new_callable=AsyncMock,
            return_value=mock_execution
        ):
            communicator = WebsocketCommunicator(
                WorkflowExecutionConsumer.as_asgi(),
                f"/ws/workflow/{execution_id}/"
            )
            communicator.scope["url_route"] = {"kwargs": {"execution_id": execution_id}}

            await communicator.connect()

            # Clear initial status message
            await communicator.receive_json_from()

            # Send unknown action
            await communicator.send_json_to({"action": "unknown_action"})

            # Receive error
            response = await communicator.receive_json_from()
            assert response["type"] == "error"
            assert response["code"] == "unknown_action"

            await communicator.disconnect()

    async def test_receive_missing_action(self, execution_id, mock_execution):
        """Test message without action returns error."""
        with patch.object(
            WorkflowExecutionConsumer,
            '_get_execution',
            new_callable=AsyncMock,
            return_value=mock_execution
        ):
            communicator = WebsocketCommunicator(
                WorkflowExecutionConsumer.as_asgi(),
                f"/ws/workflow/{execution_id}/"
            )
            communicator.scope["url_route"] = {"kwargs": {"execution_id": execution_id}}

            await communicator.connect()

            # Clear initial status message
            await communicator.receive_json_from()

            # Send message without action
            await communicator.send_json_to({"data": "some_data"})

            # Receive error
            response = await communicator.receive_json_from()
            assert response["type"] == "error"
            assert response["code"] == "missing_action"

            await communicator.disconnect()


# ============================================================================
# Broadcast Helper Tests
# ============================================================================

@pytest.mark.asyncio
class TestBroadcastHelpers:
    """Tests for broadcast helper functions."""

    async def test_broadcast_workflow_update_without_channel_layer(self):
        """Test broadcast_workflow_update handles missing channel layer."""
        with patch('channels.layers.get_channel_layer', return_value=None):
            # Should not raise
            await broadcast_workflow_update(
                execution_id=str(uuid4()),
                status='running',
                progress=0.5
            )

    async def test_broadcast_node_update_without_channel_layer(self):
        """Test broadcast_node_update handles missing channel layer."""
        with patch('channels.layers.get_channel_layer', return_value=None):
            # Should not raise
            await broadcast_node_update(
                execution_id=str(uuid4()),
                node_id='node_1',
                status='completed'
            )

    async def test_broadcast_execution_completed_without_channel_layer(self):
        """Test broadcast_execution_completed handles missing channel layer."""
        with patch('channels.layers.get_channel_layer', return_value=None):
            # Should not raise
            await broadcast_execution_completed(
                execution_id=str(uuid4()),
                status='completed'
            )

    async def test_broadcast_workflow_update_with_mock_channel_layer(self):
        """Test broadcast_workflow_update sends correct message."""
        mock_channel_layer = MagicMock()
        mock_channel_layer.group_send = AsyncMock()

        execution_id = str(uuid4())

        with patch('channels.layers.get_channel_layer', return_value=mock_channel_layer):
            await broadcast_workflow_update(
                execution_id=execution_id,
                status='running',
                progress=0.5,
                current_node_id='node_1',
                trace_id='trace-123'
            )

        mock_channel_layer.group_send.assert_called_once()
        call_args = mock_channel_layer.group_send.call_args

        assert call_args[0][0] == f"workflow_execution_{execution_id}"
        assert call_args[0][1]["type"] == "workflow_update"
        assert call_args[0][1]["status"] == "running"
        assert call_args[0][1]["progress"] == 0.5
        assert call_args[0][1]["current_node_id"] == "node_1"

    async def test_broadcast_node_update_with_mock_channel_layer(self):
        """Test broadcast_node_update sends correct message."""
        mock_channel_layer = MagicMock()
        mock_channel_layer.group_send = AsyncMock()

        execution_id = str(uuid4())

        with patch('channels.layers.get_channel_layer', return_value=mock_channel_layer):
            await broadcast_node_update(
                execution_id=execution_id,
                node_id='node_1',
                status='completed',
                output={'result': 'success'},
                duration_ms=150
            )

        mock_channel_layer.group_send.assert_called_once()
        call_args = mock_channel_layer.group_send.call_args

        assert call_args[0][0] == f"workflow_execution_{execution_id}"
        assert call_args[0][1]["type"] == "node_update"
        assert call_args[0][1]["node_id"] == "node_1"
        assert call_args[0][1]["status"] == "completed"
        assert call_args[0][1]["output"] == {'result': 'success'}
        assert call_args[0][1]["duration_ms"] == 150

    async def test_broadcast_execution_completed_with_mock_channel_layer(self):
        """Test broadcast_execution_completed sends correct message."""
        mock_channel_layer = MagicMock()
        mock_channel_layer.group_send = AsyncMock()

        execution_id = str(uuid4())

        with patch('channels.layers.get_channel_layer', return_value=mock_channel_layer):
            await broadcast_execution_completed(
                execution_id=execution_id,
                status='completed',
                result={'output': 'data'},
                duration_ms=5000
            )

        mock_channel_layer.group_send.assert_called_once()
        call_args = mock_channel_layer.group_send.call_args

        assert call_args[0][0] == f"workflow_execution_{execution_id}"
        assert call_args[0][1]["type"] == "execution_completed"
        assert call_args[0][1]["status"] == "completed"
        assert call_args[0][1]["result"] == {'output': 'data'}
        assert call_args[0][1]["duration_ms"] == 5000


# ============================================================================
# Consumer Handler Tests
# ============================================================================

@pytest.mark.asyncio
class TestConsumerHandlers:
    """Tests for consumer event handlers."""

    async def test_workflow_update_handler(self, execution_id, mock_execution):
        """Test workflow_update handler sends correct message to client."""
        with patch.object(
            WorkflowExecutionConsumer,
            '_get_execution',
            new_callable=AsyncMock,
            return_value=mock_execution
        ):
            communicator = WebsocketCommunicator(
                WorkflowExecutionConsumer.as_asgi(),
                f"/ws/workflow/{execution_id}/"
            )
            communicator.scope["url_route"] = {"kwargs": {"execution_id": execution_id}}

            await communicator.connect()

            # Clear initial status message
            await communicator.receive_json_from()

            # Get the consumer instance's channel layer
            channel_layer = get_channel_layer()
            group_name = f"workflow_execution_{execution_id}"

            # Simulate a workflow_update event
            await channel_layer.group_send(
                group_name,
                {
                    "type": "workflow_update",
                    "status": "running",
                    "progress": 0.75,
                    "current_node_id": "node_2",
                    "trace_id": "trace-456",
                    "updated_at": "2025-01-01T00:01:00Z"
                }
            )

            # Receive the message
            response = await communicator.receive_json_from()
            assert response["type"] == "workflow_status"
            assert response["status"] == "running"
            assert response["progress"] == 0.75
            assert response["current_node_id"] == "node_2"

            await communicator.disconnect()

    async def test_node_update_handler(self, execution_id, mock_execution):
        """Test node_update handler sends correct message to client."""
        with patch.object(
            WorkflowExecutionConsumer,
            '_get_execution',
            new_callable=AsyncMock,
            return_value=mock_execution
        ):
            communicator = WebsocketCommunicator(
                WorkflowExecutionConsumer.as_asgi(),
                f"/ws/workflow/{execution_id}/"
            )
            communicator.scope["url_route"] = {"kwargs": {"execution_id": execution_id}}

            await communicator.connect()

            # Clear initial status message
            await communicator.receive_json_from()

            # Get the consumer instance's channel layer
            channel_layer = get_channel_layer()
            group_name = f"workflow_execution_{execution_id}"

            # Simulate a node_update event
            await channel_layer.group_send(
                group_name,
                {
                    "type": "node_update",
                    "node_id": "node_3",
                    "status": "completed",
                    "output": {"key": "value"},
                    "duration_ms": 200,
                    "completed_at": "2025-01-01T00:01:00Z"
                }
            )

            # Receive the message
            response = await communicator.receive_json_from()
            assert response["type"] == "node_status"
            assert response["node_id"] == "node_3"
            assert response["status"] == "completed"
            assert response["output"] == {"key": "value"}

            await communicator.disconnect()

    async def test_execution_completed_handler(self, execution_id, mock_execution):
        """Test execution_completed handler sends correct message to client."""
        with patch.object(
            WorkflowExecutionConsumer,
            '_get_execution',
            new_callable=AsyncMock,
            return_value=mock_execution
        ):
            communicator = WebsocketCommunicator(
                WorkflowExecutionConsumer.as_asgi(),
                f"/ws/workflow/{execution_id}/"
            )
            communicator.scope["url_route"] = {"kwargs": {"execution_id": execution_id}}

            await communicator.connect()

            # Clear initial status message
            await communicator.receive_json_from()

            # Get the consumer instance's channel layer
            channel_layer = get_channel_layer()
            group_name = f"workflow_execution_{execution_id}"

            # Simulate an execution_completed event
            await channel_layer.group_send(
                group_name,
                {
                    "type": "execution_completed",
                    "status": "completed",
                    "result": {"final": "output"},
                    "duration_ms": 10000,
                    "completed_at": "2025-01-01T00:02:00Z"
                }
            )

            # Receive the message
            response = await communicator.receive_json_from()
            assert response["type"] == "execution_completed"
            assert response["status"] == "completed"
            assert response["result"] == {"final": "output"}
            assert response["duration_ms"] == 10000

            await communicator.disconnect()


# ============================================================================
# Node Subscription Filter Tests
# ============================================================================

@pytest.mark.asyncio
class TestNodeSubscriptionFiltering:
    """Tests for node subscription filtering."""

    async def test_node_update_filtered_when_subscribed(self, execution_id, mock_execution):
        """Test that node updates are filtered based on subscription."""
        with patch.object(
            WorkflowExecutionConsumer,
            '_get_execution',
            new_callable=AsyncMock,
            return_value=mock_execution
        ):
            communicator = WebsocketCommunicator(
                WorkflowExecutionConsumer.as_asgi(),
                f"/ws/workflow/{execution_id}/"
            )
            communicator.scope["url_route"] = {"kwargs": {"execution_id": execution_id}}

            await communicator.connect()

            # Clear initial status message
            await communicator.receive_json_from()

            # Subscribe to only node_1
            await communicator.send_json_to({
                "action": "subscribe_nodes",
                "node_ids": ["node_1"]
            })
            await communicator.receive_json_from()  # subscription confirmation

            # Get channel layer
            channel_layer = get_channel_layer()
            group_name = f"workflow_execution_{execution_id}"

            # Send update for subscribed node_1
            await channel_layer.group_send(
                group_name,
                {
                    "type": "node_update",
                    "node_id": "node_1",
                    "status": "completed"
                }
            )

            # Should receive this one
            response = await communicator.receive_json_from()
            assert response["type"] == "node_status"
            assert response["node_id"] == "node_1"

            # Send update for non-subscribed node_2
            await channel_layer.group_send(
                group_name,
                {
                    "type": "node_update",
                    "node_id": "node_2",
                    "status": "completed"
                }
            )

            # Should NOT receive this (filtered out)
            # Use timeout to check no message received
            import asyncio
            try:
                await asyncio.wait_for(
                    communicator.receive_json_from(),
                    timeout=0.5
                )
                # If we got here, we received a message when we shouldn't have
                assert False, "Should not have received node_2 update"
            except asyncio.TimeoutError:
                # Expected - no message received
                pass

            await communicator.disconnect()


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.asyncio
class TestErrorHandling:
    """Tests for error handling in consumer."""

    async def test_send_error_method(self, execution_id, mock_execution):
        """Test send_error sends correct error message."""
        with patch.object(
            WorkflowExecutionConsumer,
            '_get_execution',
            new_callable=AsyncMock,
            return_value=mock_execution
        ):
            communicator = WebsocketCommunicator(
                WorkflowExecutionConsumer.as_asgi(),
                f"/ws/workflow/{execution_id}/"
            )
            communicator.scope["url_route"] = {"kwargs": {"execution_id": execution_id}}

            await communicator.connect()

            # Clear initial status message
            await communicator.receive_json_from()

            # Trigger an error by sending invalid action
            await communicator.send_json_to({"action": "invalid"})

            response = await communicator.receive_json_from()
            assert response["type"] == "error"
            assert "code" in response
            assert "message" in response

            await communicator.disconnect()
