import pytest
from django.contrib.auth.models import Group, User

from apps.databases.models import PermissionLevel
from apps.templates.models import (
    OperationTemplate,
    OperationTemplateGroupPermission,
    OperationTemplatePermission,
    WorkflowTemplatePermission,
    WorkflowTemplateGroupPermission,
)
from apps.templates.rbac import TemplatePermissionService
from apps.templates.workflow.models import WorkflowTemplate


@pytest.mark.django_db
def test_group_workflow_template_permission_inherits_to_execution():
    group = Group.objects.create(name="wf_ops")
    user = User.objects.create_user(username="u", password="pass")
    user.groups.add(group)

    workflow = WorkflowTemplate.objects.create(
        name="WF",
        description="",
        workflow_type="sequential",
        dag_structure={
            "nodes": [
                {
                    "id": "start",
                    "name": "Start",
                    "type": "operation",
                    "template_id": "noop",
                    "config": {},
                }
            ],
            "edges": [],
        },
        config={},
        is_valid=True,
        is_active=True,
    )

    WorkflowTemplateGroupPermission.objects.create(
        group=group,
        workflow_template=workflow,
        level=PermissionLevel.OPERATE,
        notes="",
    )

    assert (
        TemplatePermissionService.get_user_level_for_workflow_template(user, workflow)
        == PermissionLevel.OPERATE
    )

    execution = workflow.create_execution({"k": "v"})
    assert (
        TemplatePermissionService.get_user_level_for_workflow_execution(user, execution)
        == PermissionLevel.OPERATE
    )

    accessible = TemplatePermissionService.filter_accessible_workflow_templates(
        user, WorkflowTemplate.objects.all(), min_level=PermissionLevel.VIEW
    )
    assert accessible.filter(id=workflow.id).exists()


@pytest.mark.django_db
def test_group_operation_template_permission_allows_access():
    group = Group.objects.create(name="tpl_ops")
    user = User.objects.create_user(username="u", password="pass")
    user.groups.add(group)

    template = OperationTemplate.objects.create(
        id="tpl-1",
        name="T1",
        description="",
        operation_type="noop",
        target_entity="db",
        template_data={},
        is_active=True,
    )

    OperationTemplateGroupPermission.objects.create(
        group=group,
        template=template,
        level=PermissionLevel.VIEW,
        notes="",
    )

    assert (
        TemplatePermissionService.get_user_level_for_operation_template(user, template)
        == PermissionLevel.VIEW
    )

    accessible = TemplatePermissionService.filter_accessible_operation_templates(
        user, OperationTemplate.objects.all(), min_level=PermissionLevel.VIEW
    )
    assert accessible.filter(id=template.id).exists()


@pytest.mark.django_db
def test_user_workflow_template_permission_inherits_to_execution():
    user = User.objects.create_user(username="u", password="pass")

    workflow = WorkflowTemplate.objects.create(
        name="WF",
        description="",
        workflow_type="sequential",
        dag_structure={
            "nodes": [
                {
                    "id": "start",
                    "name": "Start",
                    "type": "operation",
                    "template_id": "noop",
                    "config": {},
                }
            ],
            "edges": [],
        },
        config={},
        is_valid=True,
        is_active=True,
    )

    WorkflowTemplatePermission.objects.create(
        user=user,
        workflow_template=workflow,
        level=PermissionLevel.OPERATE,
        notes="",
    )

    assert (
        TemplatePermissionService.get_user_level_for_workflow_template(user, workflow)
        == PermissionLevel.OPERATE
    )

    execution = workflow.create_execution({"k": "v"})
    assert (
        TemplatePermissionService.get_user_level_for_workflow_execution(user, execution)
        == PermissionLevel.OPERATE
    )


@pytest.mark.django_db
def test_user_operation_template_permission_allows_access():
    user = User.objects.create_user(username="u", password="pass")

    template = OperationTemplate.objects.create(
        id="tpl-1",
        name="T1",
        description="",
        operation_type="noop",
        target_entity="db",
        template_data={},
        is_active=True,
    )

    OperationTemplatePermission.objects.create(
        user=user,
        template=template,
        level=PermissionLevel.VIEW,
        notes="",
    )

    assert (
        TemplatePermissionService.get_user_level_for_operation_template(user, template)
        == PermissionLevel.VIEW
    )

    accessible = TemplatePermissionService.filter_accessible_operation_templates(
        user, OperationTemplate.objects.all(), min_level=PermissionLevel.VIEW
    )
    assert accessible.filter(id=template.id).exists()


@pytest.mark.django_db
def test_effective_level_is_max_of_user_and_group():
    group = Group.objects.create(name="wf_ops")
    user = User.objects.create_user(username="u", password="pass")
    user.groups.add(group)

    workflow = WorkflowTemplate.objects.create(
        name="WF",
        description="",
        workflow_type="sequential",
        dag_structure={
            "nodes": [
                {
                    "id": "start",
                    "name": "Start",
                    "type": "operation",
                    "template_id": "noop",
                    "config": {},
                }
            ],
            "edges": [],
        },
        config={},
        is_valid=True,
        is_active=True,
    )

    WorkflowTemplateGroupPermission.objects.create(
        group=group,
        workflow_template=workflow,
        level=PermissionLevel.OPERATE,
        notes="",
    )
    user_perm = WorkflowTemplatePermission.objects.create(
        user=user,
        workflow_template=workflow,
        level=PermissionLevel.VIEW,
        notes="",
    )

    assert (
        TemplatePermissionService.get_user_level_for_workflow_template(user, workflow)
        == PermissionLevel.OPERATE
    )

    user_perm.level = PermissionLevel.MANAGE
    user_perm.save(update_fields=["level"])

    assert (
        TemplatePermissionService.get_user_level_for_workflow_template(user, workflow)
        == PermissionLevel.MANAGE
    )
