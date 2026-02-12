# orchestrator/apps/templates/tests/test_admin.py
"""
Tests for WorkflowTemplateAdmin OperationExposure reference panel.
"""

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from apps.templates.admin import WorkflowTemplateAdmin
from apps.templates.models import OperationDefinition, OperationExposure
from apps.templates.workflow.models import WorkflowTemplate


def _create_template_exposure(*, alias: str, label: str, operation_type: str, target_entity: str, is_active: bool = True, status: str = OperationExposure.STATUS_PUBLISHED):
    definition = OperationDefinition.objects.create(
        tenant_scope="global",
        executor_kind=OperationDefinition.EXECUTOR_DESIGNER_CLI,
        executor_payload={
            "operation_type": operation_type,
            "target_entity": target_entity,
            "template_data": {},
        },
        contract_version=1,
        fingerprint=f"fp-{alias}",
        status=OperationDefinition.STATUS_ACTIVE,
    )
    return OperationExposure.objects.create(
        definition=definition,
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias=alias,
        tenant=None,
        label=label,
        description="",
        is_active=is_active,
        capability="",
        contexts=[],
        display_order=0,
        capability_config={},
        status=status,
    )


@pytest.mark.django_db
class TestWorkflowTemplateAdminOperationExposureContext(TestCase):
    def setUp(self):
        self.admin_site = AdminSite()
        self.workflow_admin = WorkflowTemplateAdmin(WorkflowTemplate, self.admin_site)
        self.request_factory = RequestFactory()

        User.objects.filter(username="testadmin_admin").delete()
        self.admin_user = User.objects.create_user(
            username="testadmin_admin",
            email="testadmin@test.com",
            password="testpass123",
            is_staff=True,
        )

        self.workflow = WorkflowTemplate.objects.create(
            name="Test Workflow",
            workflow_type="sequential",
            dag_structure={
                "nodes": [
                    {
                        "id": "step1",
                        "name": "Step 1",
                        "type": "operation",
                        "template_id": "tpl-a",
                        "config": {"timeout_seconds": 30},
                    }
                ],
                "edges": [],
            },
            config={"timeout_seconds": 300},
            created_by=self.admin_user,
            is_valid=True,
            is_active=True,
        )

    def test_changeform_view_includes_only_active_published_template_exposures(self):
        _create_template_exposure(alias="tpl-a", label="Alpha", operation_type="backup", target_entity="infobase")
        _create_template_exposure(alias="tpl-b", label="Beta", operation_type="backup", target_entity="infobase")
        _create_template_exposure(
            alias="tpl-c",
            label="Inactive",
            operation_type="backup",
            target_entity="infobase",
            is_active=False,
        )
        _create_template_exposure(
            alias="tpl-d",
            label="Draft",
            operation_type="backup",
            target_entity="infobase",
            status=OperationExposure.STATUS_DRAFT,
        )

        request = self.request_factory.get(f"/admin/templates/workflowtemplate/{self.workflow.id}/change/")
        request.user = self.admin_user
        response = self.workflow_admin.changeform_view(request, str(self.workflow.id))

        assert response.status_code == 200
        rows = list(response.context_data["operation_templates"])
        assert [row.id for row in rows] == ["tpl-a", "tpl-b"]

    def test_operation_templates_are_sorted_by_type_then_name(self):
        _create_template_exposure(alias="tpl-z", label="Zulu", operation_type="zzz", target_entity="infobase")
        _create_template_exposure(alias="tpl-a2", label="Alpha 2", operation_type="aaa", target_entity="infobase")
        _create_template_exposure(alias="tpl-a1", label="Alpha 1", operation_type="aaa", target_entity="infobase")

        request = self.request_factory.get(f"/admin/templates/workflowtemplate/{self.workflow.id}/change/")
        request.user = self.admin_user
        response = self.workflow_admin.changeform_view(request, str(self.workflow.id))

        assert response.status_code == 200
        rows = list(response.context_data["operation_templates"])
        assert [row.id for row in rows] == ["tpl-a1", "tpl-a2", "tpl-z"]

    def test_add_view_and_changeform_view_have_same_templates(self):
        _create_template_exposure(alias="tpl-1", label="One", operation_type="sync", target_entity="infobase")
        _create_template_exposure(alias="tpl-2", label="Two", operation_type="sync", target_entity="infobase")

        request_change = self.request_factory.get(f"/admin/templates/workflowtemplate/{self.workflow.id}/change/")
        request_change.user = self.admin_user
        response_change = self.workflow_admin.changeform_view(request_change, str(self.workflow.id))

        request_add = self.request_factory.get("/admin/templates/workflowtemplate/add/")
        request_add.user = self.admin_user
        response_add = self.workflow_admin.add_view(request_add)

        change_ids = [item.id for item in response_change.context_data["operation_templates"]]
        add_ids = [item.id for item in response_add.context_data["operation_templates"]]
        assert change_ids == add_ids

    def test_extra_context_is_preserved(self):
        _create_template_exposure(alias="tpl-ctx", label="Ctx", operation_type="sync", target_entity="infobase")
        request = self.request_factory.get(f"/admin/templates/workflowtemplate/{self.workflow.id}/change/")
        request.user = self.admin_user

        response = self.workflow_admin.changeform_view(
            request,
            str(self.workflow.id),
            extra_context={"custom_key": "custom_value"},
        )

        assert response.status_code == 200
        assert response.context_data["custom_key"] == "custom_value"
