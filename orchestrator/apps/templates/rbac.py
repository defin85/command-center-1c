from typing import Optional

from django.db.models import Max

from apps.databases.models import PermissionLevel
from apps.templates.models import (
    OperationTemplate,
    OperationTemplateGroupPermission,
    WorkflowTemplateGroupPermission,
)
from apps.templates.workflow.models import WorkflowExecution, WorkflowTemplate


class TemplatePermissionService:
    """
    Scope/level resolution for templates and workflows.

    This service does NOT check Django capabilities (user.has_perm).
    It only resolves "what objects this user can access" and at what PermissionLevel.
    """

    @classmethod
    def get_user_level_for_operation_template(
        cls,
        user,
        template: OperationTemplate,
    ) -> Optional[int]:
        if not user or not getattr(user, "is_authenticated", False):
            return None
        if getattr(user, "is_staff", False):
            return PermissionLevel.ADMIN

        level = (
            OperationTemplateGroupPermission.objects.filter(
                group__user=user,
                template=template,
            )
            .aggregate(level=Max("level"))
            .get("level")
        )
        return level

    @classmethod
    def get_user_level_for_workflow_template(
        cls,
        user,
        workflow_template: WorkflowTemplate,
    ) -> Optional[int]:
        if not user or not getattr(user, "is_authenticated", False):
            return None
        if getattr(user, "is_staff", False):
            return PermissionLevel.ADMIN

        level = (
            WorkflowTemplateGroupPermission.objects.filter(
                group__user=user,
                workflow_template=workflow_template,
            )
            .aggregate(level=Max("level"))
            .get("level")
        )
        return level

    @classmethod
    def get_user_level_for_workflow_execution(
        cls,
        user,
        execution: WorkflowExecution,
    ) -> Optional[int]:
        return cls.get_user_level_for_workflow_template(
            user, execution.workflow_template
        )

    @classmethod
    def has_operation_template_access(
        cls,
        user,
        template: OperationTemplate,
        required_level: int,
    ) -> bool:
        level = cls.get_user_level_for_operation_template(user, template)
        return level is not None and level >= required_level

    @classmethod
    def has_workflow_template_access(
        cls,
        user,
        workflow_template: WorkflowTemplate,
        required_level: int,
    ) -> bool:
        level = cls.get_user_level_for_workflow_template(user, workflow_template)
        return level is not None and level >= required_level

    @classmethod
    def filter_accessible_operation_templates(
        cls,
        user,
        queryset,
        min_level: int = None,
    ):
        if min_level is None:
            min_level = PermissionLevel.VIEW
        if not user or not getattr(user, "is_authenticated", False):
            return queryset.none()
        if getattr(user, "is_staff", False):
            return queryset

        template_ids = OperationTemplateGroupPermission.objects.filter(
            group__user=user,
            level__gte=min_level,
        ).values_list("template_id", flat=True)
        return queryset.filter(id__in=template_ids)

    @classmethod
    def filter_accessible_workflow_templates(
        cls,
        user,
        queryset,
        min_level: int = None,
    ):
        if min_level is None:
            min_level = PermissionLevel.VIEW
        if not user or not getattr(user, "is_authenticated", False):
            return queryset.none()
        if getattr(user, "is_staff", False):
            return queryset

        workflow_ids = WorkflowTemplateGroupPermission.objects.filter(
            group__user=user,
            level__gte=min_level,
        ).values_list("workflow_template_id", flat=True)
        return queryset.filter(id__in=workflow_ids)

    @classmethod
    def filter_accessible_workflow_executions(
        cls,
        user,
        queryset,
        min_level: int = None,
    ):
        if min_level is None:
            min_level = PermissionLevel.VIEW
        if not user or not getattr(user, "is_authenticated", False):
            return queryset.none()
        if getattr(user, "is_staff", False):
            return queryset

        workflow_ids = WorkflowTemplateGroupPermission.objects.filter(
            group__user=user,
            level__gte=min_level,
        ).values_list("workflow_template_id", flat=True)
        return queryset.filter(workflow_template_id__in=workflow_ids)

