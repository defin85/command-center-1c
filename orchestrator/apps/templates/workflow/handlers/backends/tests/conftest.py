"""
Pytest fixtures for backend tests.
"""

import pytest
from unittest.mock import Mock, MagicMock
from uuid import uuid4

from django.contrib.auth.models import User

from apps.databases.models import Database, Cluster
from apps.templates.models import OperationTemplate
from apps.templates.workflow.models import WorkflowTemplate, WorkflowExecution


@pytest.fixture
def admin_user(db):
    """Create admin user for tests."""
    User.objects.filter(username='testadmin').delete()
    return User.objects.create_user(
        username='testadmin',
        email='test@test.com',
        password='testpass123',
        is_staff=True,
        is_superuser=True
    )


@pytest.fixture
def cluster(db):
    """Create test cluster with RAS identifiers."""
    return Cluster.objects.create(
        name="Test Cluster",
        ras_cluster_uuid=uuid4(),
        ras_server="localhost:1545",
        cluster_service_url="http://localhost:8087",
        status="active"
    )


@pytest.fixture
def database(db, cluster):
    """Create test database with RAS identifiers."""
    return Database.objects.create(
        id=uuid4(),
        name="TestDB",
        cluster=cluster,
        ras_cluster_id=cluster.ras_cluster_uuid,
        ras_infobase_id=uuid4(),
        username="admin",
        password="password"
    )


@pytest.fixture
def workflow_template(db, admin_user):
    """Create workflow template for tests."""
    return WorkflowTemplate.objects.create(
        name="Test Workflow",
        workflow_type="sequential",
        dag_structure={
            "nodes": [
                {
                    "id": "node1",
                    "name": "Operation Node",
                    "type": "operation",
                    "template_id": str(uuid4())
                }
            ],
            "edges": []
        },
        created_by=admin_user,
        is_valid=True,
        is_active=True
    )


@pytest.fixture
def workflow_execution(db, workflow_template):
    """Create workflow execution for tests."""
    execution = workflow_template.create_execution({"input": "data"})
    execution.start()
    execution.save()
    return execution


@pytest.fixture
def lock_operation_template(db):
    """Create RAS lock_scheduled_jobs operation template."""
    return OperationTemplate.objects.create(
        id=str(uuid4()),
        name="Lock Scheduled Jobs",
        operation_type="lock_scheduled_jobs",
        target_entity="Infobase",
        template_data={
            "description": "Lock scheduled jobs for maintenance"
        }
    )


@pytest.fixture
def unlock_operation_template(db):
    """Create RAS unlock_scheduled_jobs operation template."""
    return OperationTemplate.objects.create(
        id=str(uuid4()),
        name="Unlock Scheduled Jobs",
        operation_type="unlock_scheduled_jobs",
        target_entity="Infobase",
        template_data={
            "description": "Unlock scheduled jobs"
        }
    )


@pytest.fixture
def create_operation_template(db):
    """Create OData create operation template."""
    return OperationTemplate.objects.create(
        id=str(uuid4()),
        name="Create Records",
        operation_type="create",
        target_entity="Users",
        template_data={
            "entity": "Users",
            "data": {"name": "{{ name }}", "email": "{{ email }}"}
        }
    )


@pytest.fixture
def update_operation_template(db):
    """Create OData update operation template."""
    return OperationTemplate.objects.create(
        id=str(uuid4()),
        name="Update Records",
        operation_type="update",
        target_entity="Users",
        template_data={
            "entity": "Users",
            "filter": "id = {{ id }}",
            "data": {"status": "{{ status }}"}
        }
    )


@pytest.fixture
def mock_ras_adapter_client():
    """Create mock RAS adapter client."""
    return MagicMock()


@pytest.fixture
def mock_success_response():
    """Create mock successful RAS response."""
    response = MagicMock()
    response.success = True
    response.message = "Operation successful"
    return response


@pytest.fixture
def mock_error_response():
    """Create mock error RAS response."""
    from apps.databases.clients.generated.ras_adapter_api_client.models import ErrorResponse
    response = Mock(spec=ErrorResponse)
    response.error = "Operation failed"
    response.details = "Connection timeout"
    return response


@pytest.fixture
def mock_terminate_sessions_response():
    """Create mock terminate sessions response."""
    response = MagicMock()
    response.success = True
    response.message = "Sessions terminated"
    response.terminated_count = 5
    return response
