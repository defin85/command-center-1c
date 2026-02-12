import pytest
from uuid import uuid4

from apps.databases.models import Database
from apps.templates.models import OperationDefinition, OperationExposure
from apps.templates.template_runtime import resolve_runtime_template
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
    template_id = "test_template_" + str(uuid4())[:8]
    definition = OperationDefinition.objects.create(
        tenant_scope="global",
        executor_kind=OperationDefinition.EXECUTOR_DESIGNER_CLI,
        executor_payload={
            "operation_type": "query",
            "target_entity": "Users",
            "template_data": {"query": "SELECT * FROM Users"},
        },
        contract_version=1,
        fingerprint=f"fp-{template_id}",
        status=OperationDefinition.STATUS_ACTIVE,
    )
    OperationExposure.objects.create(
        definition=definition,
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias=template_id,
        tenant=None,
        label="Test Operation Template",
        description="Test template for factory",
        is_active=True,
        capability="",
        contexts=[],
        display_order=0,
        capability_config={},
        status=OperationExposure.STATUS_PUBLISHED,
    )
    return resolve_runtime_template(template_alias=template_id)


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
