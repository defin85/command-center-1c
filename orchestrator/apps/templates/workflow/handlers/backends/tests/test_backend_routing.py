"""
Tests for backend routing in OperationHandler.

Tests cover:
- Backend selection based on operation_type
- Unknown operation type handling
- Backend priority and fallback
"""

import pytest
from uuid import uuid4

from apps.templates.workflow.handlers.operation import OperationHandler
from apps.templates.workflow.handlers.backends import (
    IBCMDBackend,
    ODataBackend,
    RASBackend,
    AbstractOperationBackend,
)


class TestBackendRouting:
    """Tests for operation handler backend routing."""

    def test_get_backend_returns_ras_for_lock_scheduled_jobs(self):
        """Test that lock_scheduled_jobs operation routes to RASBackend."""
        handler = OperationHandler()
        backend = handler._get_backend('lock_scheduled_jobs')

        assert isinstance(backend, RASBackend)
        assert not isinstance(backend, ODataBackend)

    def test_get_backend_returns_ras_for_unlock_scheduled_jobs(self):
        """Test that unlock_scheduled_jobs operation routes to RASBackend."""
        handler = OperationHandler()
        backend = handler._get_backend('unlock_scheduled_jobs')

        assert isinstance(backend, RASBackend)

    def test_get_backend_returns_ras_for_terminate_sessions(self):
        """Test that terminate_sessions operation routes to RASBackend."""
        handler = OperationHandler()
        backend = handler._get_backend('terminate_sessions')

        assert isinstance(backend, RASBackend)

    def test_get_backend_returns_ras_for_block_sessions(self):
        """Test that block_sessions operation routes to RASBackend."""
        handler = OperationHandler()
        backend = handler._get_backend('block_sessions')

        assert isinstance(backend, RASBackend)

    def test_get_backend_returns_ras_for_unblock_sessions(self):
        """Test that unblock_sessions operation routes to RASBackend."""
        handler = OperationHandler()
        backend = handler._get_backend('unblock_sessions')

        assert isinstance(backend, RASBackend)

    def test_get_backend_returns_odata_for_create(self):
        """Test that create operation routes to ODataBackend."""
        handler = OperationHandler()
        backend = handler._get_backend('create')

        assert isinstance(backend, ODataBackend)
        assert not isinstance(backend, RASBackend)

    def test_get_backend_returns_odata_for_update(self):
        """Test that update operation routes to ODataBackend."""
        handler = OperationHandler()
        backend = handler._get_backend('update')

        assert isinstance(backend, ODataBackend)

    def test_get_backend_returns_odata_for_delete(self):
        """Test that delete operation routes to ODataBackend."""
        handler = OperationHandler()
        backend = handler._get_backend('delete')

        assert isinstance(backend, ODataBackend)

    def test_get_backend_returns_odata_for_query(self):
        """Test that query operation routes to ODataBackend."""
        handler = OperationHandler()
        backend = handler._get_backend('query')

        assert isinstance(backend, ODataBackend)

    def test_get_backend_returns_odata_for_install_extension(self):
        """Test that install_extension operation routes to ODataBackend."""
        handler = OperationHandler()
        backend = handler._get_backend('install_extension')

        assert isinstance(backend, ODataBackend)

    def test_get_backend_returns_ibcmd_for_backup(self):
        """Test that ibcmd_backup operation routes to IBCMDBackend."""
        handler = OperationHandler()
        backend = handler._get_backend('ibcmd_backup')

        assert isinstance(backend, IBCMDBackend)

    def test_get_backend_raises_for_unknown_operation_type(self):
        """Test that unknown operation type raises ValueError."""
        handler = OperationHandler()

        with pytest.raises(ValueError, match="No backend supports operation type"):
            handler._get_backend('unknown_operation')

    def test_get_backend_raises_with_helpful_message(self):
        """Test error message includes available types."""
        handler = OperationHandler()

        with pytest.raises(ValueError) as exc_info:
            handler._get_backend('unknown_operation')

        error_msg = str(exc_info.value)
        assert 'unknown_operation' in error_msg
        assert 'OData' in error_msg
        assert 'RAS' in error_msg
        assert 'IBCMD' in error_msg

    def test_get_backend_returns_abstract_backend_interface(self):
        """Test that returned backends implement AbstractOperationBackend."""
        handler = OperationHandler()

        for op_type in ['create', 'lock_scheduled_jobs', 'query', 'block_sessions', 'ibcmd_backup']:
            backend = handler._get_backend(op_type)
            assert isinstance(backend, AbstractOperationBackend)

    def test_backend_priority_ras_before_odata(self):
        """Test that RASBackend is checked before others."""
        handler = OperationHandler()

        # RASBackend should be first in the list
        assert isinstance(handler._backends[0], RASBackend)
        assert isinstance(handler._backends[1], IBCMDBackend)
        assert isinstance(handler._backends[2], ODataBackend)

    def test_get_all_supported_types(self):
        """Test get_all_supported_types returns grouped operation types."""
        all_types = OperationHandler.get_all_supported_types()

        assert 'odata' in all_types
        assert 'ras' in all_types
        assert 'ibcmd' in all_types

        # Check OData types
        odata_types = all_types['odata']
        assert 'create' in odata_types
        assert 'update' in odata_types
        assert 'delete' in odata_types
        assert 'query' in odata_types
        assert 'install_extension' in odata_types

        # Check RAS types
        ras_types = all_types['ras']
        assert 'lock_scheduled_jobs' in ras_types
        assert 'unlock_scheduled_jobs' in ras_types
        assert 'terminate_sessions' in ras_types
        assert 'block_sessions' in ras_types
        assert 'unblock_sessions' in ras_types

        # Check IBCMD types
        ibcmd_types = all_types['ibcmd']
        assert 'ibcmd_backup' in ibcmd_types
        assert 'ibcmd_restore' in ibcmd_types
        assert 'ibcmd_replicate' in ibcmd_types
        assert 'ibcmd_create' in ibcmd_types

    def test_backend_supports_operation_type_method(self):
        """Test backend support checking via supports_operation_type."""
        ras_backend = RASBackend()
        odata_backend = ODataBackend()
        ibcmd_backend = IBCMDBackend()

        # RAS should support RAS types
        assert ras_backend.supports_operation_type('lock_scheduled_jobs') is True
        assert ras_backend.supports_operation_type('create') is False

        # OData should support OData types
        assert odata_backend.supports_operation_type('create') is True
        assert odata_backend.supports_operation_type('lock_scheduled_jobs') is False

        # IBCMD should support ibcmd types
        assert ibcmd_backend.supports_operation_type('ibcmd_backup') is True
        assert ibcmd_backend.supports_operation_type('create') is False

    def test_backend_get_supported_types_class_method(self):
        """Test get_supported_types class method on backends."""
        ras_types = RASBackend.get_supported_types()
        odata_types = ODataBackend.get_supported_types()
        ibcmd_types = IBCMDBackend.get_supported_types()

        # Both should return non-empty sets
        assert isinstance(ras_types, set)
        assert isinstance(odata_types, set)
        assert isinstance(ibcmd_types, set)
        assert len(ras_types) > 0
        assert len(odata_types) > 0
        assert len(ibcmd_types) > 0

        # Sets should not overlap
        assert len(ras_types & odata_types) == 0
        assert len(ras_types & ibcmd_types) == 0
        assert len(odata_types & ibcmd_types) == 0

    def test_backend_instance_caching(self):
        """Test that handler maintains backend instances."""
        handler1 = OperationHandler()
        handler2 = OperationHandler()

        # Different OperationHandler instances should have different backend instances
        assert handler1._backends[0] is not handler2._backends[0]

        # But same handler should reuse backends
        backend1 = handler1._get_backend('create')
        backend2 = handler1._get_backend('update')
        assert backend1 is backend2  # Same ODataBackend instance

    def test_operation_type_case_sensitive(self):
        """Test that operation type matching is case-sensitive."""
        handler = OperationHandler()

        # Should work with correct case
        assert handler._get_backend('create') is not None

        # Should fail with wrong case
        with pytest.raises(ValueError):
            handler._get_backend('CREATE')

    def test_empty_operation_type_raises_error(self):
        """Test that empty operation type raises error."""
        handler = OperationHandler()

        with pytest.raises(ValueError):
            handler._get_backend('')


class TestBackendRoutingIntegration:
    """Integration tests for backend routing."""

    @pytest.mark.django_db
    def test_operation_handler_complete_flow_with_ras(
        self,
        database,
        workflow_execution
    ):
        """Test complete flow: OperationHandler -> RASBackend."""
        from apps.templates.models import OperationTemplate
        from apps.templates.workflow.models import WorkflowNode
        from unittest.mock import patch, MagicMock

        # Create RAS operation template
        template = OperationTemplate.objects.create(
            id=str(uuid4()),
            name="Test Lock",
            operation_type='lock_scheduled_jobs',
            target_entity="Infobase",
            template_data={}
        )

        node = WorkflowNode(
            id="op1",
            name="Lock Operation",
            type="operation",
            template_id=str(template.id)
        )

        handler = OperationHandler()

        # Mock RASBackend.execute
        with patch.object(RASBackend, 'execute') as mock_execute:
            mock_execute.return_value = MagicMock(success=True)

            handler.execute(
                node=node,
                context={'target_databases': [str(database.id)], 'user_id': 'test'},
                execution=workflow_execution,
                mode=None
            )

            # Verify RASBackend.execute was called
            assert mock_execute.called
            call_args = mock_execute.call_args
            assert call_args[1]['template'].operation_type == 'lock_scheduled_jobs'

    @pytest.mark.django_db
    def test_operation_handler_complete_flow_with_odata(
        self,
        database,
        workflow_execution
    ):
        """Test complete flow: OperationHandler -> ODataBackend."""
        from apps.templates.models import OperationTemplate
        from apps.templates.workflow.models import WorkflowNode
        from unittest.mock import patch, MagicMock

        # Create OData operation template
        template = OperationTemplate.objects.create(
            id=str(uuid4()),
            name="Test Create",
            operation_type='create',
            target_entity="Users",
            template_data={}
        )

        node = WorkflowNode(
            id="op2",
            name="Create Operation",
            type="operation",
            template_id=str(template.id)
        )

        handler = OperationHandler()

        # Mock ODataBackend.execute
        with patch.object(ODataBackend, 'execute') as mock_execute:
            mock_execute.return_value = MagicMock(success=True)

            handler.execute(
                node=node,
                context={'target_databases': [str(database.id)], 'user_id': 'test'},
                execution=workflow_execution,
                mode=None
            )

            # Verify ODataBackend.execute was called
            assert mock_execute.called
            call_args = mock_execute.call_args
            assert call_args[1]['template'].operation_type == 'create'
