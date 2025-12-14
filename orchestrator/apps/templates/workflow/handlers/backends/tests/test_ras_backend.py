"""
Unit tests for RASBackend.

Tests cover:
- Operation type support checks
- RAS operation execution (lock, unlock, terminate, block, unblock)
- Error handling (missing cluster_id, network errors, etc.)
- Response processing
- Timeout handling
"""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from apps.templates.workflow.handlers.backends.ras import (
    RASBackend,
    RASBackendError,
)
from apps.templates.workflow.handlers.base import NodeExecutionMode

# Operation type string constants (previously TYPE_* module constants)
TYPE_LOCK_SCHEDULED_JOBS = 'lock_scheduled_jobs'
TYPE_UNLOCK_SCHEDULED_JOBS = 'unlock_scheduled_jobs'
TYPE_TERMINATE_SESSIONS = 'terminate_sessions'
TYPE_BLOCK_SESSIONS = 'block_sessions'
TYPE_UNBLOCK_SESSIONS = 'unblock_sessions'


class TestRASBackendOperationTypeSupport:
    """Tests for RAS operation type support."""

    def test_supports_lock_scheduled_jobs(self):
        """Test RASBackend supports lock_scheduled_jobs."""
        backend = RASBackend()
        assert backend.supports_operation_type(TYPE_LOCK_SCHEDULED_JOBS) is True

    def test_supports_unlock_scheduled_jobs(self):
        """Test RASBackend supports unlock_scheduled_jobs."""
        backend = RASBackend()
        assert backend.supports_operation_type(TYPE_UNLOCK_SCHEDULED_JOBS) is True

    def test_supports_terminate_sessions(self):
        """Test RASBackend supports terminate_sessions."""
        backend = RASBackend()
        assert backend.supports_operation_type(TYPE_TERMINATE_SESSIONS) is True

    def test_supports_block_sessions(self):
        """Test RASBackend supports block_sessions."""
        backend = RASBackend()
        assert backend.supports_operation_type(TYPE_BLOCK_SESSIONS) is True

    def test_supports_unblock_sessions(self):
        """Test RASBackend supports unblock_sessions."""
        backend = RASBackend()
        assert backend.supports_operation_type(TYPE_UNBLOCK_SESSIONS) is True

    def test_does_not_support_create(self):
        """Test RASBackend does not support OData create."""
        backend = RASBackend()
        assert backend.supports_operation_type('create') is False

    def test_does_not_support_update(self):
        """Test RASBackend does not support OData update."""
        backend = RASBackend()
        assert backend.supports_operation_type('update') is False

    def test_does_not_support_delete(self):
        """Test RASBackend does not support OData delete."""
        backend = RASBackend()
        assert backend.supports_operation_type('delete') is False

    def test_does_not_support_query(self):
        """Test RASBackend does not support OData query."""
        backend = RASBackend()
        assert backend.supports_operation_type('query') is False

    def test_does_not_support_install_extension(self):
        """Test RASBackend does not support install_extension."""
        backend = RASBackend()
        assert backend.supports_operation_type('install_extension') is False

    def test_get_supported_types(self):
        """Test get_supported_types returns all RAS operation types."""
        supported_types = RASBackend.get_supported_types()

        assert TYPE_LOCK_SCHEDULED_JOBS in supported_types
        assert TYPE_UNLOCK_SCHEDULED_JOBS in supported_types
        assert TYPE_TERMINATE_SESSIONS in supported_types
        assert TYPE_BLOCK_SESSIONS in supported_types
        assert TYPE_UNBLOCK_SESSIONS in supported_types

        # Should not contain OData types
        assert 'create' not in supported_types
        assert 'update' not in supported_types
        assert 'delete' not in supported_types
        assert 'query' not in supported_types


class TestRASBackendExecution:
    """Tests for RAS operation execution."""

    @pytest.mark.django_db
    def test_execute_lock_success(
        self,
        database,
        lock_operation_template,
        workflow_execution,
        mock_success_response
    ):
        """Test successful lock_scheduled_jobs execution."""
        backend = RASBackend()

        with patch.object(backend, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            with patch('apps.templates.workflow.handlers.backends.ras.lock_infobase_v2') as mock_lock:
                mock_lock.sync.return_value = mock_success_response

                result = backend.execute(
                    template=lock_operation_template,
                    rendered_data={},
                    target_databases=[str(database.id)],
                    context={'user_id': 'test_user'},
                    execution=workflow_execution,
                    mode=NodeExecutionMode.SYNC
                )

        assert result.success is True
        assert result.output['backend'] == 'ras'
        assert result.output['operation_type'] == TYPE_LOCK_SCHEDULED_JOBS
        assert result.output['total'] == 1
        assert result.output['completed'] == 1
        assert result.output['failed'] == 0
        assert result.mode == NodeExecutionMode.SYNC
        assert result.duration_seconds is not None

    @pytest.mark.django_db
    def test_execute_unlock_success(
        self,
        database,
        unlock_operation_template,
        workflow_execution,
        mock_success_response
    ):
        """Test successful unlock_scheduled_jobs execution."""
        backend = RASBackend()

        with patch.object(backend, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            with patch('apps.templates.workflow.handlers.backends.ras.unlock_infobase_v2') as mock_unlock:
                mock_unlock.sync.return_value = mock_success_response

                result = backend.execute(
                    template=unlock_operation_template,
                    rendered_data={},
                    target_databases=[str(database.id)],
                    context={'user_id': 'test_user'},
                    execution=workflow_execution,
                    mode=NodeExecutionMode.SYNC
                )

        assert result.success is True
        assert result.output['operation_type'] == TYPE_UNLOCK_SCHEDULED_JOBS

    @pytest.mark.django_db
    def test_execute_terminate_sessions_success(
        self,
        database,
        workflow_execution,
        mock_terminate_sessions_response
    ):
        """Test successful terminate_sessions execution."""
        from apps.templates.models import OperationTemplate

        template = OperationTemplate.objects.create(
            id=str(uuid4()),
            name="Terminate Sessions",
            operation_type=TYPE_TERMINATE_SESSIONS,
            target_entity="Infobase",
            template_data={}
        )

        backend = RASBackend()

        with patch.object(backend, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            with patch('apps.templates.workflow.handlers.backends.ras.terminate_sessions_v2') as mock_term:
                mock_term.sync.return_value = mock_terminate_sessions_response

                result = backend.execute(
                    template=template,
                    rendered_data={},
                    target_databases=[str(database.id)],
                    context={'user_id': 'test_user'},
                    execution=workflow_execution,
                    mode=NodeExecutionMode.SYNC
                )

        assert result.success is True
        assert result.output['operation_type'] == TYPE_TERMINATE_SESSIONS

    @pytest.mark.django_db
    def test_execute_with_credentials_in_rendered_data(
        self,
        database,
        lock_operation_template,
        workflow_execution,
        mock_success_response
    ):
        """Test execution with credentials from rendered_data."""
        backend = RASBackend()

        rendered_data = {
            'db_user': 'custom_user',
            'db_password': 'custom_password'
        }

        with patch.object(backend, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            with patch('apps.templates.workflow.handlers.backends.ras.lock_infobase_v2') as mock_lock:
                mock_lock.sync.return_value = mock_success_response

                result = backend.execute(
                    template=lock_operation_template,
                    rendered_data=rendered_data,
                    target_databases=[str(database.id)],
                    context={'user_id': 'test_user'},
                    execution=workflow_execution,
                    mode=NodeExecutionMode.SYNC
                )

        assert result.success is True

    @pytest.mark.django_db
    def test_execute_multiple_databases(
        self,
        database,
        cluster,
        lock_operation_template,
        workflow_execution,
        mock_success_response
    ):
        """Test execution across multiple target databases."""
        # Create second database
        db2 = database
        from apps.databases.models import Database
        db3 = Database.objects.create(
            id=str(uuid4()),
            name="TestDB2",
            cluster=cluster,
            ras_cluster_id=cluster.ras_cluster_uuid,
            ras_infobase_id=uuid4(),
            username="admin",
            password="password",
            is_active=True
        )

        backend = RASBackend()

        with patch.object(backend, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            with patch('apps.templates.workflow.handlers.backends.ras.lock_infobase_v2') as mock_lock:
                mock_lock.sync.return_value = mock_success_response

                result = backend.execute(
                    template=lock_operation_template,
                    rendered_data={},
                    target_databases=[str(db2.id), str(db3.id)],
                    context={'user_id': 'test_user'},
                    execution=workflow_execution,
                    mode=NodeExecutionMode.SYNC
                )

        assert result.success is True
        assert result.output['total'] == 2
        assert result.output['completed'] == 2
        assert result.output['failed'] == 0

    @pytest.mark.django_db
    def test_execute_with_async_mode_falls_back_to_sync(
        self,
        database,
        lock_operation_template,
        workflow_execution,
        mock_success_response
    ):
        """Test that ASYNC mode is not supported and falls back to SYNC."""
        backend = RASBackend()

        with patch.object(backend, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            with patch('apps.templates.workflow.handlers.backends.ras.lock_infobase_v2') as mock_lock:
                mock_lock.sync.return_value = mock_success_response

                result = backend.execute(
                    template=lock_operation_template,
                    rendered_data={},
                    target_databases=[str(database.id)],
                    context={'user_id': 'test_user'},
                    execution=workflow_execution,
                    mode=NodeExecutionMode.ASYNC  # Request ASYNC
                )

        # Should succeed but run as SYNC
        assert result.success is True
        assert result.mode == NodeExecutionMode.SYNC

    @pytest.mark.django_db
    def test_execute_lock_failure_with_error_response(
        self,
        database,
        lock_operation_template,
        workflow_execution,
        mock_error_response
    ):
        """Test lock execution with error response from RAS."""
        backend = RASBackend()

        with patch.object(backend, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            with patch('apps.templates.workflow.handlers.backends.ras.lock_infobase_v2') as mock_lock:
                mock_lock.sync.return_value = mock_error_response

                result = backend.execute(
                    template=lock_operation_template,
                    rendered_data={},
                    target_databases=[str(database.id)],
                    context={'user_id': 'test_user'},
                    execution=workflow_execution,
                    mode=NodeExecutionMode.SYNC
                )

        assert result.success is False
        assert result.output['failed'] == 1
        assert result.output['errors'] is not None
        assert len(result.output['errors']) == 1

    @pytest.mark.django_db
    def test_execute_with_missing_cluster_id(
        self,
        cluster,
        lock_operation_template,
        workflow_execution
    ):
        """Test execution fails when database has no cluster_id configured."""
        from apps.databases.models import Database

        # Create database without cluster_id
        db_no_cluster = Database.objects.create(
            id=str(uuid4()),
            name="NoClustersDB",
            cluster=cluster,
            ras_cluster_id=None,  # Missing cluster ID
            ras_infobase_id=uuid4(),
            username="admin",
            password="password",
            is_active=True
        )

        backend = RASBackend()

        result = backend.execute(
            template=lock_operation_template,
            rendered_data={},
            target_databases=[str(db_no_cluster.id)],
            context={'user_id': 'test_user'},
            execution=workflow_execution,
            mode=NodeExecutionMode.SYNC
        )

        assert result.success is False
        assert result.output['failed'] == 1
        assert 'cluster' in result.output['errors'][0]['error'].lower()

    @pytest.mark.django_db
    def test_execute_with_missing_infobase_id(
        self,
        cluster,
        lock_operation_template,
        workflow_execution
    ):
        """Test execution fails when database has no infobase_id configured."""
        from apps.databases.models import Database

        # Create database without infobase_id
        db_no_infobase = Database.objects.create(
            id=str(uuid4()),
            name="NoInfobaseDB",
            cluster=cluster,
            ras_cluster_id=cluster.ras_cluster_uuid,
            ras_infobase_id=None,  # Missing infobase ID
            username="admin",
            password="password",
            is_active=True
        )

        backend = RASBackend()

        result = backend.execute(
            template=lock_operation_template,
            rendered_data={},
            target_databases=[str(db_no_infobase.id)],
            context={'user_id': 'test_user'},
            execution=workflow_execution,
            mode=NodeExecutionMode.SYNC
        )

        assert result.success is False
        assert result.output['failed'] == 1
        assert 'infobase' in result.output['errors'][0]['error'].lower()

    @pytest.mark.django_db
    def test_execute_with_nonexistent_database(
        self,
        lock_operation_template,
        workflow_execution
    ):
        """Test execution fails when database doesn't exist."""
        backend = RASBackend()

        result = backend.execute(
            template=lock_operation_template,
            rendered_data={},
            target_databases=[str(uuid4())],  # Non-existent DB
            context={'user_id': 'test_user'},
            execution=workflow_execution,
            mode=NodeExecutionMode.SYNC
        )

        assert result.success is False
        assert result.output['failed'] == 1
        assert 'not found' in result.output['errors'][0]['error'].lower()

    @pytest.mark.django_db
    def test_execute_partial_failure(
        self,
        database,
        cluster,
        lock_operation_template,
        workflow_execution,
        mock_success_response,
        mock_error_response
    ):
        """Test execution with partial failure (some databases succeed, some fail)."""
        from apps.databases.models import Database

        db2 = Database.objects.create(
            id=str(uuid4()),
            name="BadDB",
            cluster=cluster,
            ras_cluster_id=None,  # Will fail
            ras_infobase_id=uuid4(),
            username="admin",
            password="password",
            is_active=True
        )

        backend = RASBackend()

        with patch.object(backend, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            with patch('apps.templates.workflow.handlers.backends.ras.lock_infobase_v2') as mock_lock:
                mock_lock.sync.return_value = mock_success_response

                result = backend.execute(
                    template=lock_operation_template,
                    rendered_data={},
                    target_databases=[str(database.id), str(db2.id)],
                    context={'user_id': 'test_user'},
                    execution=workflow_execution,
                    mode=NodeExecutionMode.SYNC
                )

        assert result.success is False
        assert result.output['total'] == 2
        assert result.output['completed'] == 1
        assert result.output['failed'] == 1

    @pytest.mark.django_db
    def test_execute_with_timeout_exception(
        self,
        database,
        lock_operation_template,
        workflow_execution
    ):
        """Test execution handles timeout exceptions."""
        import httpx

        backend = RASBackend(timeout=1)

        with patch.object(backend, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            with patch('apps.templates.workflow.handlers.backends.ras.lock_infobase_v2') as mock_lock:
                mock_lock.sync.side_effect = httpx.TimeoutException("Connection timeout")

                result = backend.execute(
                    template=lock_operation_template,
                    rendered_data={},
                    target_databases=[str(database.id)],
                    context={'user_id': 'test_user'},
                    execution=workflow_execution,
                    mode=NodeExecutionMode.SYNC
                )

        assert result.success is False
        assert result.output['failed'] == 1
        assert 'timed' in result.output['errors'][0]['error'].lower()

    @pytest.mark.django_db
    def test_execute_with_http_error(
        self,
        database,
        lock_operation_template,
        workflow_execution
    ):
        """Test execution handles HTTP errors."""
        import httpx

        backend = RASBackend()

        with patch.object(backend, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            with patch('apps.templates.workflow.handlers.backends.ras.lock_infobase_v2') as mock_lock:
                mock_lock.sync.side_effect = httpx.HTTPError("Connection refused")

                result = backend.execute(
                    template=lock_operation_template,
                    rendered_data={},
                    target_databases=[str(database.id)],
                    context={'user_id': 'test_user'},
                    execution=workflow_execution,
                    mode=NodeExecutionMode.SYNC
                )

        assert result.success is False
        assert result.output['failed'] == 1


class TestRASBackendInitialization:
    """Tests for RASBackend initialization."""

    def test_initialization_with_default_settings(self):
        """Test RASBackend initialization with default settings."""
        backend = RASBackend()

        assert backend.base_url == 'http://localhost:8188'
        assert backend.timeout == 30

    def test_initialization_with_custom_base_url(self):
        """Test RASBackend initialization with custom base URL."""
        backend = RASBackend(base_url='http://custom.host:9999')

        assert backend.base_url == 'http://custom.host:9999'

    def test_initialization_with_custom_timeout(self):
        """Test RASBackend initialization with custom timeout."""
        backend = RASBackend(timeout=60)

        assert backend.timeout == 60

    def test_base_url_trailing_slash_stripped(self):
        """Test that trailing slash is stripped from base_url."""
        backend = RASBackend(base_url='http://localhost:8188/')

        assert backend.base_url == 'http://localhost:8188'


class TestRASBackendErrorClass:
    """Tests for RASBackendError exception."""

    def test_error_creation_with_message_only(self):
        """Test RASBackendError creation with message only."""
        error = RASBackendError("Operation failed")

        assert str(error) == "Operation failed"
        assert error.database_id is None
        assert error.details is None

    def test_error_creation_with_all_fields(self):
        """Test RASBackendError creation with all fields."""
        db_id = str(uuid4())
        error = RASBackendError(
            "Operation failed",
            database_id=db_id,
            details="Connection timeout"
        )

        assert str(error) == "Operation failed"
        assert error.database_id == db_id
        assert error.details == "Connection timeout"
