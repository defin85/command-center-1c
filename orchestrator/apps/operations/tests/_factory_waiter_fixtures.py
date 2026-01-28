import pytest
from uuid import uuid4

from apps.databases.models import Database
from apps.templates.models import OperationTemplate
from apps.templates.workflow.models import WorkflowTemplate


@pytest.fixture
def test_database(db):
    return Database.objects.create(
        id=str(uuid4())[:12],
        name="TestBase",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="test",
        password="test",
        status=Database.STATUS_ACTIVE,
    )


@pytest.fixture
def multiple_databases(db):
    databases = []
    for i in range(3):
        db_obj = Database.objects.create(
            id=str(uuid4())[:12],
            name=f"TestBase{i}",
            host=f"server_{i}",
            port=80 + i,
            odata_url=f"http://server_{i}/odata",
            username="test",
            password="test",
            status=Database.STATUS_ACTIVE,
        )
        databases.append(db_obj)
    return databases


@pytest.fixture
def operation_template(db):
    return OperationTemplate.objects.create(
        id="test_template_" + str(uuid4())[:8],
        name="Test Operation Template",
        operation_type="query",
        target_entity="Users",
        template_data={"query": "SELECT * FROM Users"},
        description="Test template for factory",
    )


@pytest.fixture
def workflow_template(db):
    return WorkflowTemplate.objects.create(
        id=str(uuid4()),
        name="Test Workflow Template",
        workflow_type="sequential",
        dag_structure={
            "nodes": [
                {
                    "id": "test_node",
                    "name": "Test Node",
                    "type": "operation",
                    "template_id": "test_template",
                }
            ],
            "edges": [],
        },
        is_valid=True,
        is_active=True,
    )


@pytest.fixture
def workflow_execution(db, workflow_template):
    return workflow_template.create_execution({"test": "data"})

