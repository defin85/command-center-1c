from typing import Optional

from django.db.models import Max, Q

from apps.databases.models import PermissionLevel
from apps.templates.models import (
    OperationTemplate,
    OperationTemplateGroupPermission,
    OperationTemplatePermission,
    WorkflowTemplatePermission,
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

        user_level = OperationTemplatePermission.objects.filter(
            user=user,
            template=template,
        ).values_list("level", flat=True).first()

        group_level = (
            OperationTemplateGroupPermission.objects.filter(
                group__user=user,
                template=template,
            )
            .aggregate(level=Max("level"))
            .get("level")
        )
        levels = [lvl for lvl in [user_level, group_level] if lvl is not None]
        return max(levels) if levels else None

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

        user_level = WorkflowTemplatePermission.objects.filter(
            user=user,
            workflow_template=workflow_template,
        ).values_list("level", flat=True).first()

        group_level = (
            WorkflowTemplateGroupPermission.objects.filter(
                group__user=user,
                workflow_template=workflow_template,
            )
            .aggregate(level=Max("level"))
            .get("level")
        )
        levels = [lvl for lvl in [user_level, group_level] if lvl is not None]
        return max(levels) if levels else None

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

        user_template_ids = OperationTemplatePermission.objects.filter(
            user=user,
            level__gte=min_level,
        ).values_list("template_id", flat=True)
        group_template_ids = OperationTemplateGroupPermission.objects.filter(
            group__user=user,
            level__gte=min_level,
        ).values_list("template_id", flat=True)
        return queryset.filter(Q(id__in=user_template_ids) | Q(id__in=group_template_ids))

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

        user_workflow_ids = WorkflowTemplatePermission.objects.filter(
            user=user,
            level__gte=min_level,
        ).values_list("workflow_template_id", flat=True)
        group_workflow_ids = WorkflowTemplateGroupPermission.objects.filter(
            group__user=user,
            level__gte=min_level,
        ).values_list("workflow_template_id", flat=True)
        return queryset.filter(Q(id__in=user_workflow_ids) | Q(id__in=group_workflow_ids))

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

        user_workflow_ids = WorkflowTemplatePermission.objects.filter(
            user=user,
            level__gte=min_level,
        ).values_list("workflow_template_id", flat=True)
        group_workflow_ids = WorkflowTemplateGroupPermission.objects.filter(
            group__user=user,
            level__gte=min_level,
        ).values_list("workflow_template_id", flat=True)
        return queryset.filter(
            Q(workflow_template_id__in=user_workflow_ids)
            | Q(workflow_template_id__in=group_workflow_ids)
        )
