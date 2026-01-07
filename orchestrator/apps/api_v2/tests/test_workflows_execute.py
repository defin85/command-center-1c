import pytest
from django.contrib.auth.models import User
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient

from unittest.mock import patch

from apps.operations.services import EnqueueResult
from apps.databases.models import PermissionLevel
from apps.templates.models import WorkflowTemplatePermission
from apps.templates.workflow.models import WorkflowExecution, WorkflowTemplate, WorkflowType


@pytest.fixture
def user():
    user = User.objects.create_user(username="workflow_user", password="pass")
    ct = ContentType.objects.get(app_label="templates", model="workflowtemplate")
    perm = Permission.objects.get(content_type=ct, codename="execute_workflow_template")
    user.user_permissions.add(perm)
    return user


@pytest.fixture
def client(user):
    api_client = APIClient()
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def workflow_template(user):
    template = WorkflowTemplate.objects.create(
        name="Test Workflow",
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure={
            "nodes": [
                {"id": "n1", "name": "Node 1", "type": "operation", "template_id": "tpl-test"},
            ],
            "edges": [],
        },
        is_valid=True,
        is_active=True,
        created_by=user,
    )
    WorkflowTemplatePermission.objects.create(
        user=user,
        workflow_template=template,
        level=PermissionLevel.OPERATE,
        notes="",
    )
    return template


@pytest.mark.django_db
def test_execute_workflow_async_uses_background_runner_when_go_engine_disabled(
    client,
    settings,
    workflow_template,
):
    settings.CELERY_ENABLED = False
    settings.ENABLE_GO_WORKFLOW_ENGINE = False

    with (
        patch(
            "apps.api_v2.views.workflows._start_async_workflow_execution",
            return_value=True,
        ) as start_bg,
        patch("apps.operations.services.OperationsService.enqueue_workflow_execution") as enqueue,
    ):
        resp = client.post(
            "/api/v2/workflows/execute-workflow/",
            {"workflow_id": str(workflow_template.id), "input_context": {}, "mode": "async"},
            format="json",
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["mode"] == "async"
    assert payload["status"] == "pending"
    execution = WorkflowExecution.objects.get(id=payload["execution_id"])
    assert execution.input_context["executed_by"] == "workflow_user"

    start_bg.assert_called_once()
    enqueue.assert_not_called()


@pytest.mark.django_db
def test_execute_workflow_async_uses_go_worker_when_flag_enabled(
    client,
    settings,
    workflow_template,
):
    settings.CELERY_ENABLED = False
    settings.ENABLE_GO_WORKFLOW_ENGINE = True

    fake_result = EnqueueResult(success=True, operation_id="op-123", status="queued")

    with (
        patch(
            "apps.api_v2.views.workflows._start_async_workflow_execution",
            return_value=True,
        ) as start_bg,
        patch(
            "apps.operations.services.OperationsService.enqueue_workflow_execution",
            return_value=fake_result,
        ) as enqueue,
    ):
        resp = client.post(
            "/api/v2/workflows/execute-workflow/",
            {"workflow_id": str(workflow_template.id), "input_context": {}, "mode": "async"},
            format="json",
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["mode"] == "async"
    assert payload["status"] == "pending"
    assert payload["operation_id"] == "op-123"

    execution = WorkflowExecution.objects.get(id=payload["execution_id"])
    assert execution.input_context["executed_by"] == "workflow_user"

    enqueue.assert_called_once()
    start_bg.assert_not_called()
